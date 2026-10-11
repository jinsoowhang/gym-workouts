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
