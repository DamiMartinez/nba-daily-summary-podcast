# Agent guidance: nba-daily-summary-podcast

## Scope and architecture

This repository publishes the **NBA Daily Summary** RSS feed and cover artwork
through GitHub Pages. It does not collect NBA results, call LLMs, generate audio,
or upload audio to GCS. Those responsibilities belong to
[`DamiMartinez/nba-agents`](https://github.com/DamiMartinez/nba-agents).

Read `README.md`, `.github/workflows/publish_podcast.yml`, and the relevant tests
before making changes. The publisher's executable Python currently lives inside
the workflow heredoc, not in a standalone application. Tests extract and execute
that actual code, with mocked HTTP and temporary feed files.

Important paths:

- `podcast/rss.xml`: production feed, including historical episodes.
- `podcast/*.png`: hosted cover artwork; resolve the active filename from RSS.
- `.github/workflows/publish_podcast.yml`: upload polling, WAV metadata, RSS update,
  secret scanning, and automated feed commit/push.
- `.github/workflows/tests.yml`: standard-library tests on Python 3.11 and 3.12.
- `tests/`: date, feed-building, failure-path, and any artwork regression tests.

## Date and scheduling contract

- ALL episode dates, canonical audio filenames, game-time references, and RSS
  publication timestamps use **`America/New_York`**. Never use the host's local
  date or UTC date to choose an episode. Use `zoneinfo`, not fixed offsets.
- An Eastern edition dated D recaps Eastern date D-1 and previews Eastern date D.
  Content generation is owned by the producer repository.
- **`Europe/Madrid` is only the automation scheduling timezone.** Both daily
  workflows start at **11:00 Madrid time** via native cron `timezone` support.
  Keep that distinct from the Eastern editorial/edition timezone.
- The publisher waits up to 90 minutes for its matching audio. Its job timeout
  must exceed this wait plus download, validation, scanning, and commit overhead.
- Scheduled starts can be delayed. Do not promise publication exactly at 11:00.
- Keep explicit `edition_date` backfills consistent across both repositories.
  Freeze the date before waiting; do not change filenames if a wait crosses midnight.

## Feed and audio invariants

- Canonical audio is public WAV at
  `https://storage.googleapis.com/nba_daily_summary_podcast_audios/nba_daily_summary_podcast_YYYY-MM-DD.wav`.
- Do not publish a missing, invalid, or empty audio file. Only HTTP 404 enters the
  missing-audio wait loop; other HTTP failures must remain visible failures.
- Bound network calls, clean up temporary downloads, and fail when the upload
  deadline expires. Tests must not actually wait for the polling interval.
- Enclosure `length` is the actual downloaded byte count, not zero or duration.
  MIME type is `audio/wav`; iTunes duration comes from WAV frames/sample rate.
- Preserve namespaces, channel metadata, existing episode dates/GUIDs/enclosures,
  and historical ordering. Do not bulk-rewrite or prettify the feed for unrelated
  changes. Insert a newly published episode before existing episodes.
- Re-running an existing edition must not create a duplicate or rewrite its item.
  Do not change the duplicate policy or replace published audio without approval.
- Never use a staging filename or test URL in the live feed.

## Artwork changes

- Validate square artwork, RGB, no transparency, and 1400–3000 pixels per side
  for RSS podcast compatibility. Preserve the supplied design and original file.
- Use a new/versioned asset URL to help clients detect an update. Retain prior
  assets for cached feeds unless removal is explicitly approved.
- Update BOTH the RSS channel artwork reference and the workflow's `podcast_image`
  configuration. Inspect handling of existing image metadata; changing the
  configured default alone may not update an existing feed.
- Check the image file header/dimensions, referenced URL, and episode preservation.
  Do not introduce an imaging dependency solely for tests if standard-library PNG
  header inspection suffices. Actual resizing may use a local image tool.

## Development and validation

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
git diff --check
```

Optional, if installed:

```bash
actionlint .github/workflows/publish_podcast.yml .github/workflows/tests.yml
```

Tests require Python 3.11+ and only the standard library. They must not download
real audio, edit the real feed, publish an episode, or invoke Git. Mock HTTP and
use temporary directories. Add regression tests for changed date/DST behavior,
polling/failure paths, metadata, duplicate handling, and artwork as appropriate.
No local application build step or package installation is defined in this repo.

For an RSS-only change, parse the XML and compare all existing `<item>` elements
before and after; an artwork edit must not alter episode contents. For a live
staging test, use an isolated feed copy and an unmistakable staging audio object,
never the live RSS path. Clearly distinguish mocked checks, staging validation,
workflow completion, Pages deployment, and confirmation in the public feed.

## Git, credentials, and production safety

- Work as GitHub user `DamiMartinez`. Start task branches from up-to-date `main`;
  do not discard or move uncommitted user work. Preserve the user's Git identity.
- Keep changes scoped. Stage explicit paths, never `.env*`, service-account JSON,
  keys/certificates, tokens, caches, temporary WAV files, or local system files.
- Use the mandatory fail-closed secret gate: inspect staged paths and patch, then
  scan the exact staged content with redacted Gitleaks output before every commit.
  A supported staged command is `gitleaks git --staged --redact --verbose`.
  Scan the entire outgoing range before every push, for example
  `gitleaks git --redact --log-opts="origin/main..HEAD"` on a task branch.
  Keep staging and committing in separate tool calls. Never bypass findings or
  use `--no-verify`; report only safe paths/types, not suspected secret values.
- The publisher uses its scoped automatic `GITHUB_TOKEN`, not a manually stored
  GCP key or cross-repository PAT. Preserve its necessary `contents: write`
  permission, concurrency, checksum-verified scanner installation, and scans.
- Do not run or extract the workflow's inline publisher against the working feed
  as a local test: it can change production RSS. Dispatching the real workflow
  publishes and can lead to an automated commit and Pages deployment.
- Ask before real publication, overwriting/deleting cloud objects, merging PRs,
  enabling/disabling workflows, or changing repository settings/schedules unless
  the user has explicitly authorized that action. Never force-push unrequested.
- Open focused PRs with validation results. Do not merge merely because tests pass.
  Documentation/artwork changes do not require regenerating the podcast.
