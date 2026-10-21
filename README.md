# NBA Daily Summary Podcast

Public podcast RSS feed and cover artwork for the NBA Daily Summary.

- Feed: https://damimartinez.github.io/nba-daily-summary-podcast/podcast/rss.xml
- Audio producer: https://github.com/DamiMartinez/nba-agents

## Eastern Time policy

All episode dates use **America/New_York**, including the audio filename selected
from GCS, the episode title/date, and the RSS publication timestamp. US daylight
saving is automatic: EST in winter, EDT in summer. Host/UTC dates must not choose
the episode.

The producer generates a morning edition dated D covering Eastern date D-1's
results and date D's upcoming games. It uploads
`nba_daily_summary_podcast_YYYY-MM-DD.wav` to the existing public GCS bucket.

`.github/workflows/publish_podcast.yml` checks for that object, downloads it with
bounded timeouts, computes WAV duration and actual enclosure byte size, updates
`podcast/rss.xml` if the edition is absent, and commits/pushes the change.
Non-404 HTTP errors and invalid audio fail instead of being treated as missing
episodes. Temporary downloads are cleaned up, and publisher runs are serialized. GitHub Pages then serves the feed. Existing historical RSS items are
not rewritten by the timezone change.

Both workflows start daily at **11:00 AM Europe/Madrid**, using GitHub's native
IANA `timezone` setting to follow Madrid DST. The scheduling timezone is the only
Madrid-based setting: all episode and game dates/times remain **Eastern**.

The publisher polls for the canonical audio upload for up to **90 minutes** before
updating RSS. Publication therefore follows successful generation, not exactly
11:00; GitHub can also delay scheduled starts. A missing upload after the deadline
fails visibly. Non-404 HTTP failures do not enter the missing-file wait loop.
Manual runs accept `edition_date` as an Eastern YYYY-MM-DD date; use the same
explicit date in both repositories for backfills.

The publisher and producer workflows were both manually disabled when reviewed.
Merge both task PRs with approval before enabling them; otherwise GitHub would run
old default-branch code. Feed commits and outgoing changes must pass redacted
Gitleaks scans; the pinned scanner download is checksum-verified. No extra
cross-repository token is required for the GCS handoff.

## Local checks (no network or feed writes)

Python 3.11+ is required by the workflow. The date tests use only the standard library:

```bash
python3 -m unittest discover -s tests -v
```

Tests execute the workflow's inline Python with mocked HTTP and isolated files.
They cover UTC/New York midnight boundaries, explicit backfill dates, EST/EDT
offsets, real WAV duration/byte-size metadata, preserving prior episodes,
duplicate-run behavior, upload polling/deadline handling, HTTP errors, and invalid
audio. `.github/workflows/tests.yml` runs these checks on pushes and pull requests.

Author: [DamiMartinez](https://github.com/DamiMartinez).
No license file is currently included in this repository.
