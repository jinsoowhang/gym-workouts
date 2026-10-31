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

## Check-in weight guidance

Kept “Small steps. Steady progress.” and added a draft-only guidance panel showing
the date of the latest completed same-routine workout and the elapsed days.
Under 7 days suggests considering a small increase if the previous sets felt
comfortable. Exactly 7 through 13 days suggests maintaining; exactly 14 days or
more suggests considering lighter weights. Without completed same-routine history,
the panel suggests establishing a comfortable baseline. Guidance is advisory and
does not adjust saved weights, default values, or recorded results.

History is scoped to the current user and routine, ordered by workout date,
and excludes unfinished and future sessions. Resuming a draft uses the current
local day, so guidance changes as time passes. Completed and finalizing views
omit the panel. No migration or new frontend behavior is needed; the stylesheet
cache version is updated.

Scoped verification passed 60 guidance/workflow/ownership/session-row tests and
both existing Chromium recording workflows. Boundary cases include exactly 7
and 14 days, missing history, older resumed drafts, foreign accounts, future dates,
unfinished sessions, and out-of-order completions. Three advice states were
checked visually at 1440 px and 320 px with no overflow or JavaScript errors;
rendering left the draft unchanged. Screenshots remain ignored in reports.

Full publication verification also passed all 121 Python/browser tests, eight
dbt models, 35 data tests, Ruff, formatting, compilation, SQLFluff, whitespace,
and public-file policy. Private runtime data and deployment scripts remain ignored.

Deployed only the six guidance application files, preserving the hosted Dashboard.
The previous image, source files, and a consistent SQLite backup are retained
privately. The container is healthy; installed file hashes and the publicly served
stylesheet match the release. Live A/B history and guidance rendering passed
without sending recording requests. Workout sessions, sets, routine templates,
and publication records match the backup, and SQLite integrity is healthy.
Public health/login return 200, anonymous home redirects to login, and the
anonymous state API returns 401; no-store caching and the new stylesheet cache
version were verified. The feature and these notes form one publication change.

## Return home immediately after Finish

Successful Finish and Obsidian retry submissions now navigate to the home screen
with the next routine ready to start. Standard forms use a 303 redirect; HTMX
uses a full-page redirect. Failed publication retains the existing retry screen.
History and explicit completed-workout URLs remain available.

The browser acknowledges the edits saved by a successful completion response
before HTMX redirects. This prevents the unsaved-edit guard from blocking a
successful Finish when the latest input has not autosaved yet. Other navigation
still retains the guard. The script cache version is updated; no schema change
is required.

Verification covered both A/B directions, regular and HTMX submissions, failed
publication and successful retry, note content, and completed History views.
Both Chromium workflows passed with 20 ms and 200 ms HTMX settling, starting
Finish from a saved workout URL and checking the actual return to the root URL
without an unsaved-changes dialog. The workflows retain immediate-before-Finish
weight and therapy edits. Browser tests block the external warm-up iframe so
page navigation checks do not depend on YouTube availability.

Full publication verification passed all 125 Python/browser tests, eight dbt
models, 35 data tests, Ruff, formatting, compilation, SQLFluff, whitespace, and
public-file policy. JavaScript syntax validation also passed.

Deployed the three application files after preserving the previous image, source,
and a consistent SQLite backup. The container is healthy and the installed files
match the tested release. Read-only handler checks confirm regular and HTMX
Finish/retry redirects without submitting a real workout. Public health/login
return 200, anonymous home redirects to login, and the state API returns 401.
The served script hash and updated cache version match the release. Workout
sessions, sets, routine templates, and publication records match the backup;
SQLite integrity is healthy. This change and its session notes are published
as one atomic commit.
