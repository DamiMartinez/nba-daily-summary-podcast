"""Exercise the actual RSS workflow builder with isolated files and fake HTTP."""

from contextlib import redirect_stdout
from email.utils import parsedate_to_datetime
import io
import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import wave
import xml.etree.ElementTree as ET

from test_workflow_dates import workflow_python

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
INITIAL_FEED = '<rss version="2.0"><channel><title>NBA</title><item><title>Previous</title><guid>previous</guid></item></channel></rss>'


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\x00\x00" * 60000)  # 2.5 seconds
    return buffer.getvalue()


class FeedBuilderTests(unittest.TestCase):
    def execute(
        self,
        payload,
        head_status=200,
        twice=False,
        initially_missing=False,
        initial_feed=INITIAL_FEED,
        metadata_changes=None,
        metadata_status=200,
        metadata_initially_missing=False,
    ):
        head = MagicMock()
        head.status_code = head_status
        if head_status >= 400:
            head.raise_for_status.side_effect = RuntimeError("HTTP failure")
        download = MagicMock()
        download.__enter__.return_value = download
        download.iter_content.return_value = [payload]
        metadata = {
            "edition_date": "2026-10-21",
            "title": "Boston & New York deliver a gripping NBA finish",
            "description": (
                "Boston Celtics and New York Knicks set the tone for a busy night of basketball. "
                "Catch the verified NBA results and the key performances across the rest of the slate. "
                "Then look ahead to the upcoming matchups and their Eastern Time tip-offs."
            ),
            "audio_sha256": hashlib.sha256(payload).hexdigest(),
        }
        metadata.update(metadata_changes or {})
        metadata_response = MagicMock(status_code=metadata_status)
        metadata_response.json.return_value = metadata
        if metadata_status >= 400:
            metadata_response.raise_for_status.side_effect = RuntimeError("HTTP failure")
        metadata_calls = 0

        def get(url, **kwargs):
            nonlocal metadata_calls
            if url.endswith(".metadata.json"):
                metadata_calls += 1
                if metadata_initially_missing and metadata_calls == 1:
                    return SimpleNamespace(status_code=404)
                return metadata_response
            return download

        fake_requests = SimpleNamespace(
            head=MagicMock(return_value=head), get=MagicMock(side_effect=get)
        )
        if initially_missing:
            fake_requests.head.side_effect = [SimpleNamespace(status_code=404), head]
        previous_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory(prefix="nba-feed-unit-") as temp:
                os.chdir(temp)
                Path("podcast").mkdir()
                path = Path("podcast/rss.xml")
                path.write_text(initial_feed)
                with patch.dict("sys.modules", {"requests": fake_requests}), patch.dict(
                    os.environ,
                    {
                        "EDITION_DATE": "2026-10-21",
                        "AUDIO_WAIT_SECONDS": "60" if initially_missing or metadata_initially_missing else "0",
                    },
                ), patch("time.sleep", return_value=None), redirect_stdout(
                    io.StringIO()
                ):
                    try:
                        exec(compile(workflow_python(), "rss_workflow", "exec"), {})
                    except Exception:
                        self.assertEqual(path.read_text(), initial_feed)
                        raise
                    first = path.read_bytes()
                    if twice:
                        with self.assertRaises(SystemExit) as status:
                            exec(compile(workflow_python(), "rss_workflow", "exec"), {})
                        self.assertEqual(status.exception.code, 0)
                        self.assertEqual(path.read_bytes(), first)
                return ET.fromstring(first), fake_requests
        finally:
            os.chdir(previous_cwd)

    def test_enclosure_uses_actual_bytes_and_duration(self):
        payload = wav_bytes()
        root, requests = self.execute(payload)
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 2)
        item = items[0]
        enclosure = item.find("enclosure")
        self.assertEqual(int(enclosure.get("length")), len(payload))
        self.assertEqual(enclosure.get("type"), "audio/wav")
        self.assertTrue(enclosure.get("url").endswith("2026-10-21.wav"))
        self.assertEqual(item.findtext("guid"), enclosure.get("url"))
        self.assertEqual(item.findtext(ITUNES + "duration"), "00:00:02")
        self.assertEqual(item.findtext("title"), "Boston & New York deliver a gripping NBA finish — 2026-10-21")
        self.assertIn("Boston Celtics", item.findtext("description"))
        self.assertEqual(item.findtext("description"), item.findtext(ITUNES + "summary"))
        self.assertIsNotNone(
            parsedate_to_datetime(item.findtext("pubDate")).utcoffset()
        )
        self.assertEqual(items[1].findtext("guid"), "previous")
        self.assertEqual(requests.head.call_args.kwargs["timeout"], (5, 30))
        self.assertEqual(requests.get.call_args_list[0].kwargs["timeout"], (5, 60))

    def test_existing_artwork_updates_to_configured_cover(self):
        feed = INITIAL_FEED.replace(
            '<rss version="2.0">',
            '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
        ).replace(
            "<title>NBA</title>",
            '<title>NBA</title><itunes:image href="https://example.com/old-cover.png" />',
        )
        root, _ = self.execute(wav_bytes(), initial_feed=feed)
        image = root.find("./channel/" + ITUNES + "image")
        self.assertTrue(image.get("href").endswith("/NBA_daily_summary_cover_v2.png"))

    def test_second_run_does_not_duplicate_or_rewrite(self):
        root, _ = self.execute(wav_bytes(), twice=True)
        self.assertEqual(len(root.findall("./channel/item")), 2)

    def test_http_failure_is_not_treated_as_missing_audio(self):
        with self.assertRaises(RuntimeError):
            self.execute(wav_bytes(), head_status=500)

    def test_waits_for_generator_before_publishing(self):
        root, requests = self.execute(wav_bytes(), initially_missing=True)
        self.assertEqual(requests.head.call_count, 2)
        self.assertEqual(len(root.findall("./channel/item")), 2)
        self.assertEqual(
            requests.head.call_args_list[0].args, requests.head.call_args_list[1].args
        )

    def test_missing_audio_deadline_fails_without_feed_changes(self):
        with self.assertRaisesRegex(RuntimeError, "Audio not available"):
            self.execute(wav_bytes(), head_status=404)

    def test_metadata_failure_does_not_publish(self):
        for changes in [
            {"edition_date": "2026-10-20"},
            {"audio_sha256": "stale"},
            {"title": "Short"},
            {"title": None},
            {"title": "A long enough title\nwith newline"},
            {"description": "Generic recap"},
            {"description": "D" * 1001},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.execute(wav_bytes(), metadata_changes=changes)

    def test_metadata_http_failure_does_not_publish(self):
        with self.assertRaisesRegex(RuntimeError, "HTTP failure"):
            self.execute(wav_bytes(), metadata_status=500)

    def test_missing_metadata_does_not_publish_generic_copy(self):
        with self.assertRaisesRegex(RuntimeError, "Episode metadata not available"):
            self.execute(wav_bytes(), metadata_status=404)

    def test_waits_for_metadata_uploaded_after_audio(self):
        root, requests = self.execute(wav_bytes(), metadata_initially_missing=True)
        self.assertEqual(requests.get.call_count, 3)
        self.assertEqual(len(root.findall("./channel/item")), 2)

    def test_duplicate_detected_by_guid_without_date_in_title(self):
        url = "https://storage.googleapis.com/nba_daily_summary_podcast_audios/nba_daily_summary_podcast_2026-10-21.wav"
        feed = INITIAL_FEED.replace("previous</guid>", url + "</guid>")
        with self.assertRaises(SystemExit) as status:
            self.execute(wav_bytes(), initial_feed=feed, metadata_status=404)
        self.assertEqual(status.exception.code, 0)

    def test_invalid_audio_does_not_publish(self):
        with self.assertRaises((wave.Error, EOFError)):
            self.execute(b"not audio")


if __name__ == "__main__":
    unittest.main()
