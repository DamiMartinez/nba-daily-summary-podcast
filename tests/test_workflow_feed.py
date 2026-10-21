"""Exercise the actual RSS workflow builder with isolated files and fake HTTP."""

from contextlib import redirect_stdout
from email.utils import parsedate_to_datetime
import io
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
    def execute(self, payload, head_status=200, twice=False, initially_missing=False):
        head = MagicMock()
        head.status_code = head_status
        if head_status >= 400:
            head.raise_for_status.side_effect = RuntimeError("HTTP failure")
        download = MagicMock()
        download.__enter__.return_value = download
        download.iter_content.return_value = [payload]
        fake_requests = SimpleNamespace(
            head=MagicMock(return_value=head), get=MagicMock(return_value=download)
        )
        if initially_missing:
            fake_requests.head.side_effect = [SimpleNamespace(status_code=404), head]
        previous_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory(prefix="nba-feed-unit-") as temp:
                os.chdir(temp)
                Path("podcast").mkdir()
                path = Path("podcast/rss.xml")
                path.write_text(INITIAL_FEED)
                with patch.dict("sys.modules", {"requests": fake_requests}), patch.dict(
                    os.environ,
                    {
                        "EDITION_DATE": "2026-10-21",
                        "AUDIO_WAIT_SECONDS": "60" if initially_missing else "0",
                    },
                ), patch("time.sleep", return_value=None), redirect_stdout(
                    io.StringIO()
                ):
                    try:
                        exec(compile(workflow_python(), "rss_workflow", "exec"), {})
                    except Exception:
                        self.assertEqual(path.read_text(), INITIAL_FEED)
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
        self.assertIn("2026-10-21", item.findtext("title"))
        self.assertIsNotNone(
            parsedate_to_datetime(item.findtext("pubDate")).utcoffset()
        )
        self.assertEqual(items[1].findtext("guid"), "previous")
        self.assertEqual(requests.head.call_args.kwargs["timeout"], (5, 30))
        self.assertEqual(requests.get.call_args.kwargs["timeout"], (5, 60))

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

    def test_invalid_audio_does_not_publish(self):
        with self.assertRaises((wave.Error, EOFError)):
            self.execute(b"not audio")


if __name__ == "__main__":
    unittest.main()
