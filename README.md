# NBA Daily Summary Podcast

Public podcast RSS feed and cover artwork for the NBA Daily Summary.

- Feed: https://damimartinez.github.io/nba-daily-summary-podcast/podcast/rss.xml
- Audio producer: https://github.com/DamiMartinez/nba-agents

## Artwork

The current cover is [`podcast/NBA_daily_summary_cover_v2.png`](podcast/NBA_daily_summary_cover_v2.png),
a 1400 × 1400 RGB PNG without transparency, prepared from the supplied NBA Daily
Summary design. Both RSS and the publisher configuration use its versioned URL
so podcast apps can detect the update. The prior image remains available for
cached feeds. App artwork refresh times vary after deployment.

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
episodes. Temporary downloads are cleaned up, and publisher runs are serialized.
GitHub Pages then serves the feed. Existing historical RSS items are preserved.

Both workflows start daily at **11:10 AM Europe/Madrid**, using GitHub's native
IANA `timezone` setting to follow Madrid DST. The scheduling timezone is the only
Madrid-based setting: all episode and game dates/times remain **Eastern**.

The publisher polls for the canonical audio upload for up to **90 minutes** before
updating RSS. Publication therefore follows successful generation, not exactly
11:10; GitHub can also delay scheduled starts. The offset avoids the top-of-hour
load peak, but scheduled runs remain best-effort. A missing upload after the deadline
fails visibly. Non-404 HTTP failures do not enter the missing-file wait loop.
Manual runs accept `edition_date` as an Eastern YYYY-MM-DD date; use the same
explicit date in both repositories for backfills.

Scheduled execution requires both workflows to be enabled in their repositories'
Actions settings. Scheduled runs use each repository's default branch, so merge
approved changes before activating a new schedule. Feed commits and outgoing
changes must pass redacted Gitleaks scans; the pinned scanner download is
checksum-verified. The publisher uses its automatic `GITHUB_TOKEN` with
`contents: write`, not a GCP service-account key or cross-repository PAT.

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

## Repository layout

```text
.github/workflows/
  publish_podcast.yml   # Poll for audio, build RSS, scan, and publish changes
  tests.yml            # Python 3.11/3.12 regression tests on pushes and PRs
podcast/
  rss.xml              # Live channel metadata and episode history
  *.png                # Public podcast cover artwork
tests/                 # Mocked workflow/date/feed/artwork checks
AGENTS.md              # Repository-specific guidance for coding agents
README.md
```

The audio files are hosted in GCS, not checked into this repository. Google AI
models, credentials, score collection, and narration belong to the
[producer repository](https://github.com/DamiMartinez/nba-agents).

## Working locally

Requirements:

- Python 3.11+ with IANA timezone data available to `zoneinfo`.
- Git; GitHub CLI (`gh`) is optional for workflow management.
- No credentials or additional packages are needed for the unit tests.

```bash
git clone git@github.com:DamiMartinez/nba-daily-summary-podcast.git
cd nba-daily-summary-podcast
python3 -m unittest discover -s tests -v
git diff --check
```

There is no local application server, package manifest, or build command.
The production workflow installs its pinned `requests` dependency itself.
Do not execute its extracted inline publisher against the real working feed to
try it locally: it can change `podcast/rss.xml`. Use the mocked tests or an
isolated feed copy instead. Agent contributors should also read [AGENTS.md](AGENTS.md).

## Manual publication and backfills

**These commands run production workflows.** They may incur generation costs,
upload audio, change the feed, and deploy Pages. Obtain approval first and replace
the example date with the intended **Eastern edition date**.

Run the producer first, unless the reviewed canonical audio already exists:

```bash
gh workflow run daily-agent.yml \
  --repo DamiMartinez/nba-agents --ref main \
  -f edition_date=2026-10-21
```

Then run the publisher with the same date; it can wait while generation finishes:

```bash
gh workflow run publish_podcast.yml \
  --repo DamiMartinez/nba-daily-summary-podcast --ref main \
  -f edition_date=2026-10-21
```

Do not substitute a staging filename into the live feed. A rerun of an already
listed edition skips adding a duplicate; it is not a correction/replacement
mechanism for published audio. Agree on any correction policy before overwriting
an object or altering an existing GUID or enclosure.

## Monitoring and troubleshooting

```bash
gh run list --repo DamiMartinez/nba-agents --workflow daily-agent.yml
gh run list --repo DamiMartinez/nba-daily-summary-podcast --workflow publish_podcast.yml
# Use the run ID returned above:
gh run watch RUN_ID --repo DamiMartinez/nba-daily-summary-podcast --exit-status
```

| Symptom | Check |
| --- | --- |
| Waiting for audio / 404 | Producer run status, matching Eastern date, canonical object name. The publisher waits up to 90 minutes, then fails. |
| HTTP 403 or another non-404 error | Public object accessibility and cloud permissions in the producer; do not commit credentials here. |
| Invalid or empty WAV | Validate the generated file before publication; do not hand-edit its duration to hide a bad download. |
| No feed change on a rerun | The edition may already exist; check its title, GUID, and enclosure URL. |
| Workflow succeeded, public feed still old | Check the separate `pages-build-deployment` run, allow deployment/cache propagation, then inspect the public RSS. |
| Spotify artwork/episode still old | Confirm the public feed and assets first; podcast clients refresh on their own schedule. |
| No scheduled run | Check that the workflow is enabled and the 11:10 `Europe/Madrid` schedule is on the default branch. GitHub can delay starts. |

Successful publication means the public feed contains one intended episode with
the correct audio URL, nonzero enclosure byte size, and iTunes WAV duration.
Workflow success alone does not confirm that every podcast client has refreshed.

## Artwork maintenance

1. Prepare square RGB PNG/JPEG artwork, without transparency, at 1400–3000 pixels
   per side. Keep the original supplied file untouched.
2. Add a new/versioned asset under `podcast/` rather than reusing a cached URL.
3. Update the RSS channel's `itunes:image` URL **and** `podcast_image` in the
   publisher workflow. Inspect handling of existing metadata; changing a default
   alone may not replace a cover already in RSS.
4. Verify dimensions/format, URL consistency, and that historical episode entries
   are unchanged. Keep prior artwork available for clients with cached feeds.
5. Submit a PR. After approved merge and Pages deployment, check the public image
   URL and feed. App refreshes may take longer than deployment.

## Contributing and safety

- Use a task branch from up-to-date `main`, with focused changes and tests.
- Preserve existing RSS items and namespaces. Do not reformat the entire feed
  for a metadata-only edit, remove episode history, or change GUIDs casually.
- Never add secrets, service-account JSON, `.env` files, private keys, temporary
  audio, or local caches. Review staged paths and content, run a redacted staged
  Gitleaks scan before every commit, and scan the outgoing range before pushing.
- Publishing, workflow/schedule changes, and merging PRs require approval.
- Test workflows run on pushes/PRs without Google credentials, cloud downloads,
  real waiting, or live feed writes.

## Author and license

Author: [DamiMartinez](https://github.com/DamiMartinez) (Damian Martínez Carmona).
Contributions are welcome through focused pull requests.
No license file is currently included in this repository.
