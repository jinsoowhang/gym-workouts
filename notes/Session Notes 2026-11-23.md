# Session Notes — 2026-11-23

## Exercise completion check

Added a green check beside each draft exercise card's Minimize and removal
controls. Selecting it saves current form values, marks the card's included
sets/activities performed, and minimizes the card after the server confirms the
save. Removed rows remain removed. Combined Arms cards complete both exercises;
Physical Therapy completes its included area rows.

Completion is derived from existing persisted set states, with no migration.
Completed cards show a label and reload collapsed. Expand allows review and
editing; explicit expand/minimize choices survive subsequent form replacements.
Adding a pending row makes its card incomplete again. Invalid values, stale
revisions, and exercise IDs outside the session reject the command without
saving completion. Finish continues to publish the entire workout to Obsidian.

The check uses inline SVG to avoid missing emoji fonts. Asset cache versions and
recording instructions were updated. Private workout records were not changed.

## Verification

- Full application suite: 127 passed; two opt-in browser cases ran separately.
- Browser workflows at 20 ms and 200 ms HTMX settling passed. They cover keyboard
  completion, current edits, removed sets, autosave, reload persistence, therapy,
  explicit expansion across replacements, invalid input, and Finish.
- Four completion regressions cover numeric/therapy rows, combined Arms, foreign
  targets, stale edits, invalid values, removal/restore, new pending rows, and
  publication after completion.
- Desktop, 375 px, and 320 px browser checks found no horizontal overflow.
  Synthetic desktop/mobile screenshots are stored in ignored reports.
- Ruff, formatting, JavaScript syntax, whitespace, and public-file policy passed.

## Publication and hosted deployment

Full publication checks passed all 129 Python/browser tests, eight dbt models,
35 data tests, Ruff, formatting, compilation, SQLFluff, whitespace, and the
public-file policy. Implementation, tests, recording instructions, memory, and
these session notes are grouped as one atomic feature commit using the GitHub
noreply identity.

The hosted release applies only this feature's six application files to the
existing hosted source, preserving its Dashboard. All 70 scoped candidate tests
passed, including both Chromium workflows. The previous image and source files
and a consistent SQLite backup were retained privately before replacing the app
container. No schema migration was required.

The container is healthy and installed source hashes match the tested release.
Read-only installed-template checks verify the check action, completion label,
and collapsed completed card without submitting a real workout. Public HTTPS
health and login return 200, anonymous home redirects to login, and the state API
returns 401; no-store caching remains enforced. Public script and stylesheet
hashes and cache versions match the release. Workout sessions, sets, routine
templates, and publication records match the backup; SQLite integrity is healthy.
Private settings, deployment metadata, backups, and reports remain ignored.
