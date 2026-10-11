# Session Notes — 2026-10-11

## Request and changes

Prepare the project for public GitHub sharing and add its profile entry immediately
after `fc-clubs`. Audit source, fixtures, docs, runtime exclusions, and Git history.

- Replaced private machine defaults and personal workout observations with generic setup docs.
- Kept machine configuration in ignored `.env`; the desktop launcher loads it.
- Made historical completion cutoff explicit instead of encoding a private baseline.
- Expanded runtime/credential exclusions and public-file policy checks.
- Preserved original private history/docs in an ignored local backup.
- Prepared clean publication history with a GitHub noreply identity.

## Verification

- Full check suite passed: Python/browser workflows, Ruff, compilation, dbt debug/
  parse/seed/build, eight models and 35 data tests, SQLFluff, and public-file policy.
- Scoped configuration checks passed after normalizing relative workout paths.
- Public-file regression checks reject tracked environment settings, credential
  files, database exports, private home paths, and nested runtime documentation.
- Gitleaks 8.30.1 found no credentials in the original history or sanitized files.
- Known private identifiers and workout summaries are absent from publishable files.
- Ignored local settings still reach the existing vault/database without data writes.
- Profile entry appears once, immediately after `fc-clubs`; other entries are unchanged.

Publication target: https://github.com/jinsoowhang/gym-workouts . Only clean,
sanitized history is publishable; original private history stays in a local backup.
A clean-history scan and independent clone audit gate the initial push.

## Publication verification

Published the public repository after an independent clone passed the file policy,
known-private-identifier checks, and Gitleaks across all reachable history. The
initial public commit has no private parent; commit metadata uses GitHub noreply.
Private configuration, runtime data, source docs, and history backup remain ignored.
The profile README change is scoped to one entry directly after `fc-clubs`.

## Hosted CI correction

GitHub's first runs failed during action resolution: `astral-sh/setup-uv@v9`
does not exist. Verified the current official release and action inputs through
the GitHub API, then pinned the action to the v10.3.0 commit. The application and
dependency lock are unchanged. YAML validation and public-file checks passed;
the corrected workflow runs the previously passing local suite on GitHub.

## Browser CI timing correction

The next GitHub run passed setup and 32 Python tests, but browser autosave never
advanced the revision. Reproduced the failure locally with the same locked
Chromium build: Playwright edited the newly visible form before HTMX's settle
phase attached its input listener. A second edit after settling saved normally.

The browser test now waits for settling to finish after starting, removing,
restoring, and marking sets done. It runs at both the default 20 ms delay and
a longer 200 ms delay to verify synchronization. Autosave, reload persistence,
and finishing with an immediately edited weight remain required assertions.

Verification: all 34 Python/browser tests passed; the browser checks also passed
with the longer delay retained after reload. The complete check script passed
Ruff, compilation, dbt debug/parse/seed/build (eight models and 35 data tests),
SQLFluff, and the public-file policy. The CI correction is limited to test
synchronization and these project notes.

## Desktop launcher correction

The Desktop launcher called the project batch file correctly, but WSL's default
distribution was Docker's environment. The project batch file now explicitly
selects `Ubuntu-22.04`, with a `GYM_WSL_DISTRO` override for other installations.
README setup instructions document this choice. The Desktop entry continues to
call the project launcher, so it receives the fix automatically.

Verification: launched the actual Desktop batch file from Windows with the old
test server stopped, then confirmed the application health response and homepage
HTTP 200 using Windows PowerShell. Left the launched server running for use.
Shell syntax, whitespace, and public-file policy checks passed. No workout or
analytics actions were performed during launcher verification.

## Private VPS staging and Google sign-in preparation

Prepared Docker deployment with locked production dependencies, persistent
SQLite, the existing synced workout folder, a loopback-only listener, and an
optional Cloudflare Tunnel connector that requires validated Access tokens.
Added explicit hosted-hostname configuration while preserving local defaults
and same-origin mutation protection. Added deployment instructions for Google
as the Cloudflare identity provider and an email-specific Access policy.

Confirmed Ubuntu 24.04/Docker and the existing Syncthing send/receive vault on
the VPS. Built the image there and started a private staging instance from a
consistent SQLite backup. The synced folder has no pending files or errors.
Private infrastructure identifiers and deployment settings remain untracked.

Verification: all 41 Python/browser tests passed, including hosted HTTPS and
origin/host rejection checks. Ruff, formatting, whitespace, public-file policy,
Docker build, Compose validation, database integrity/table-count comparisons,
workout-folder permissions, health, and hosted Host handling passed. The app
port listens on loopback and cannot be reached through the VPS public address.

The public login URL is not activated. Cloudflare account credentials and a
Google Web OAuth client were not available; no connected Cloudflare plugin was
found. The allowed Gmail address and account setup path were requested. Keep
local recording active until these are supplied, then stop it, take a final
SQLite backup, and complete cutover and authenticated browser checks.
