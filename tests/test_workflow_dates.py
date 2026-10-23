"""Exercise the workflow's actual inline Python without network or RSS writes."""

import datetime
from email.utils import format_datetime
import io
import os
from pathlib import Path
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from zoneinfo import ZoneInfo

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/publish_podcast.yml"


def workflow_python():
    text = WORKFLOW.read_text()
    block = text.split("python <<'PYCODE'\n", 1)[1].split("          PYCODE", 1)[0]
    return textwrap.dedent(block)


class EasternEditionTests(unittest.TestCase):
    def run_date_selection(self, instant, requested=""):
        class Clock(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz)

        requested_urls = []
        fake_requests = SimpleNamespace(
            head=lambda url, **kwargs: (
                requested_urls.append(url) or SimpleNamespace(status_code=404)
            )
        )
        fake_datetime = SimpleNamespace(datetime=Clock, date=datetime.date)
        namespace = {}
        with patch.dict(
            "sys.modules", {"requests": fake_requests, "datetime": fake_datetime}
        ):
            with patch.dict(
                os.environ, {"EDITION_DATE": requested, "AUDIO_WAIT_SECONDS": "0"}
            ), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "Audio not available"):
                    exec(compile(workflow_python(), str(WORKFLOW), "exec"), namespace)
        return namespace, requested_urls

    def test_utc_midnight_is_previous_new_york_date(self):
        namespace, urls = self.run_date_selection(
            datetime.datetime.fromisoformat("2026-01-02T03:30+00:00")
        )
        self.assertEqual(namespace["today"], "2026-01-01")
        self.assertTrue(urls[0].endswith("nba_daily_summary_podcast_2026-01-01.wav"))

    def test_summer_eastern_midnight_boundary(self):
        for instant, expected in [
            ("2026-07-02T03:59+00:00", "2026-07-01"),
            ("2026-07-02T04:00+00:00", "2026-07-02"),
        ]:
            with self.subTest(instant=instant):
                namespace, _ = self.run_date_selection(
                    datetime.datetime.fromisoformat(instant)
                )
                self.assertEqual(namespace["today"], expected)

    def test_backfill_uses_same_explicit_date_as_generator(self):
        namespace, urls = self.run_date_selection(
            datetime.datetime.fromisoformat("2026-07-02T12:00+00:00"), "2026-01-02"
        )
        self.assertEqual(namespace["today"], "2026-01-02")
        self.assertTrue(urls[0].endswith("2026-01-02.wav"))

    def test_external_dispatch_is_available_without_builtin_schedule(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("edition_date:", workflow)
        self.assertNotIn("\n  schedule:", workflow)
        self.assertNotIn("cron:", workflow)

    def test_publication_date_uses_eastern_offset(self):
        expression = next(
            line.strip().split(" = ", 1)[1]
            for line in workflow_python().splitlines()
            if line.strip().startswith("pub_date = ")
        )
        for instant, offset in [
            ("2026-01-02T12:00+00:00", "-0500"),
            ("2026-07-02T12:00+00:00", "-0400"),
        ]:
            with self.subTest(instant=instant):
                fixed = datetime.datetime.fromisoformat(instant)
                clock = SimpleNamespace(now=lambda tz: fixed.astimezone(tz))
                value = eval(
                    expression,
                    {
                        "format_datetime": format_datetime,
                        "datetime": SimpleNamespace(datetime=clock),
                        "eastern": ZoneInfo("America/New_York"),
                    },
                )
                self.assertTrue(value.endswith(offset), value)


if __name__ == "__main__":
    unittest.main()
