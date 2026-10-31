# Session Notes 2026-10-30

Added an exercise list to Up next on the Workout page so the selected routine is
visible before starting. Lists use the authenticated user's saved templates,
preserve exercise order, deduplicate repeated sets, and include core and physical
therapy. Selecting A or B updates the preview, heading, and routine letter without
creating a draft. Existing start, autosave, and completion behavior is retained.

The preview uses two columns on desktop and one on mobile. Narrow screens use a
smaller routine letter and heading to keep the start panel within its padding.
Stylesheet and script cache versions were updated. No migration is required.

Verification: 49 scoped workflow, ownership, and session-row tests passed, plus
both Chromium recording workflows with 20 ms and 200 ms HTMX settling. Browser
checks cover A/B switching at 1440, 375, and 320 px, no preview-created draft,
completion return, and cancellation replacements. User-specific template
visibility is covered by the existing ownership check. Scoped Ruff lint and
formatting, JavaScript syntax, whitespace, and public-file checks passed.
Synthetic desktop/mobile screenshots were inspected; the final 320 px spacing
adjustment was also checked in Chromium. Screenshots remain ignored in reports.

## Hosted deployment

Deployed the five routine-preview application files after all 51 scoped checks
passed against a candidate based on the hosted source. The release preserves the
hosted Dashboard; its unrelated local highlights changes remain undeployed.

Preserved the previous image, changed source files, and a consistent SQLite
backup privately before replacing the container. No schema migration was needed.
The container is healthy and installed file hashes match the validated release.
Workout sessions, sets, routine templates, and publication records exactly match
the backup; SQLite integrity is healthy. Live template rendering verifies both
routine lists and the suggested routine's visible preview without creating a
session or changing workout data.

Public HTTPS health and login return 200, anonymous home redirects to login, and
the anonymous state API returns 401. These endpoints retain no-store caching.
Public stylesheet and script hashes match the release, and the login HTML uses
their updated cache versions. Public probes used a browser User-Agent because
the CDN rejected Python's default User-Agent. Backup and deployment metadata
remain in ignored private storage. Owner sign-in was not automated.

## GitHub publication

Prepared the routine preview, verification updates, project memory, and session
notes as one atomic commit. Full publication verification passed 110 Python/browser
tests, eight dbt models and 35 data tests, Ruff, formatting, compilation, SQLFluff,
whitespace, and public-file policy. The GitHub noreply identity is retained;
private deployment scripts, backups, runtime data, and reports remain ignored.
