# Project Memory

## Goal and status

Desktop workout recording and Analytics Engineering practice. The local app and
SQLite/DuckDB/dbt pipeline are implemented; hosted analytics remains future work.

## Behavior and ownership

- A/B advances after successful completion and Markdown publication.
- Defaults use latest completed same-routine results in lb, with template fallbacks.
- Drafts autosave, resume, reject stale revisions, and preserve edits at Finish.
- Exercise and individual-set removal are session-only with Undo. All planned sets,
  core, and therapy return in new sessions.
- The web UI has no per-set status column. Finish records remaining sets/activities
  as performed; removed rows retain their planned positions in note metadata.
  API clients still submit explicit states. Cards use inline SVG exercise icons.
- Physical Therapy has separate autosaving muscle/area rows (`activity_area`),
  each with ×/Undo and an Add area button. Labels carry across routines from the
  latest completed session, including session-only removals, with optional
  comma-separated `GYM_THERAPY_AREAS` for initial defaults. Old combined fields are
  converted to rows; unlabeled historical activities remain unlabeled. Labels are
  excluded from analytics; session `therapy_areas` is a compatibility summary.
- Add set creates a session-only numeric row using the latest included set's values.
  Added rows have new IDs, increasing occurrence numbers, appended positions, and
  no template key. Cards group them under their exercise; notes retain their order
  and identity. New sessions restore the routine template's numeric set count.
- Cancel workout confirms before ending a draft, using the existing discarded
  state. It bypasses invalid unfinished form fields, preserves completed history,
  publishes no note, and keeps A/B based on the last completion. Stale cancellation
  and cancellation of completed/finalizing workouts are rejected.
- Dashboard reads live operational data with date/exercise/metric filters. It
  shows completed sessions, training days, performed numeric sets, load volume,
  weekly frequency, and exercise weight/reps/volume trends. Top-set weight/reps
  stay paired; drafts, cancellations, unreviewed imports, skipped/removed rows,
  and therapy are excluded from numeric exercise metrics. No dbt refresh is needed.
- SQLite owns lifecycle/results. Obsidian supplies imports and completed-note mirrors.
- Durable writes recover after errors/restarts; differing existing notes are conflicts.
- Unmarked imports require review unless an explicit historical cutoff is supplied.
- Analytics refresh is explicit; recording has no cloud or request-time dbt dependency.

## Stack and checks

Python 3.12/uv, FastAPI/Jinja/HTMX, SQLAlchemy/SQLite/Alembic, dbt/DuckDB,
pytest/HTTPX/Playwright, Ruff, SQLFluff, pre-commit, and GitHub Actions.
Eight dbt models and 35 data tests. Synthetic fixtures and private warehouse files
are separate; never seed the private warehouse. Run `bash scripts/check.sh`.

## Public sharing

- Public code and documentation contain no real workout history or machine paths.
- Tests/seeds are invented. Runtime files, local settings, reports, and backups are ignored.
- Personal email addresses and OAuth credential files are rejected by the public-file
  check, including files already staged. Private allowlists stay in ignored settings.
- Configure a checkout using `.env.example`; launch with `uv run --env-file .env gym-web`.
  The Windows/WSL launcher automatically loads local `.env` when present.
- Initial publication uses clean history and GitHub's noreply commit identity.
- Original private documentation/history is retained only in an ignored local backup.
- Repository: `https://github.com/jinsoowhang/gym-workouts` (public).
- GitHub profile entry belongs immediately after `fc-clubs` in Current Projects.
- Publication checks passed for Python/browser workflows, portable configuration,
  all eight dbt models and 35 data tests, linting, and private-file policy.
  Gitleaks found no secrets in the audited code.

See README and `docs/hosted-analytics-roadmap.md` for setup and remaining milestones.

Independent clone audit passed: clean reachable history, no private runtime files
or known personal identifiers, and no secrets found by Gitleaks. GitHub publication
and the profile placement are authorized; machine data remains local.

GitHub CI pins setup-uv to the verified official v10.3.0 commit. The initial
workflow referenced an unavailable v9 major tag and failed before running checks.

Browser checks must wait for `#workout.htmx-settling` to disappear after a form
replacement before editing or submitting it. HTMX attaches listeners during
settling; visible fields alone are insufficient on fast CI runners. The browser
workflow covers both the default 20 ms and a longer 200 ms settle delay.

The Windows launcher explicitly selects `Ubuntu-22.04`, configurable through the
Windows `GYM_WSL_DISTRO` environment variable. Relying on WSL's default can launch
Docker's distribution instead of the environment with Python and uv. The Desktop
launcher calls the project launcher, so fixes apply to both entry points.

## VPS hosting

The selected hosting design now uses direct Google sign-in in the app behind the
VPS's existing Nginx Proxy Manager. Cloudflare Access/Tailscale is not required.
`deploy/compose.yml` joins the existing proxy network without publishing a host
port, with persistent SQLite and the synced workout folder. The hosted app admits
only the verified email in private settings. Local mode keeps its existing flow.

Direct Google OAuth is implemented; hosted deployment is still pending. It uses
Authlib OIDC validation, PKCE, secure session cookies, hashed
server-side sessions, a fixed 24-hour expiry, and logout revocation. Missing Google
credentials fail closed. A new Alembic migration adds login sessions; apply it
before running the updated app. All 66 Python/browser tests, Ruff, formatting,
whitespace checks, and the public-file policy passed at this checkpoint.

A private VPS staging instance is running. The existing Syncthing vault includes
the workout folder and can sync completed notes back to the PC. The approved Gmail
address is saved only in private settings. That staging instance still runs the
earlier loopback-only deployment; no public app route has been added. A Google
Web application OAuth client is required next; existing Desktop OAuth credentials
cannot supply web sign-in. Public routing, real Google sign-in verification, and
final database cutover remain pending. Deployment details are recorded in the
ignored `.secrets/vps-deployment-status.json`; see `docs/vps-deployment.md` for
the portable setup. Stop the local recorder and take a final consistent SQLite
backup before switching active recording to the VPS. Never sync live SQLite.

The published VPS changes passed an independent GitHub clone audit of all six
reachable commits and 106 distinct file versions: no private deployment identifiers,
no secrets found by Gitleaks, and no private login address in commit metadata.

Local recording remains active while Google Web OAuth setup and the VPS cutover
are pending. Keep the GitHub noreply identity and private settings out of publication.

## Local UI testing — 2026-10-12

The local database was backed up using SQLite's backup API before applying the
login-session migration. The local app runs at `http://127.0.0.1:8010` with its
configured workout folder and authentication disabled. Windows localhost access
was verified and the default browser opened. Server logs and its process ID are
stored in ignored `data/reports/local-ui-server.log` and `local-ui-server.pid`.

Both desktop browser workflows passed (20 ms and 200 ms HTMX settling), along
with 30 configuration/authentication tests. This WSL environment lacks system
NSS/NSPR libraries; browser tests passed by exposing the existing Playwright
Firefox libraries through `LD_LIBRARY_PATH`. A standard setup can install the
Chromium dependencies using the README instructions. Browser tests use temporary
workouts; no test session was recorded in the configured workout folder.

The simplified recording UI passed all 68 Python/browser tests, including
three-of-four-set recording, set Undo, reload persistence, fresh-session defaults,
and both HTMX settling delays. Synthetic desktop/mobile previews showed no
horizontal overflow at 1440 px and 375 px. Restart the local server after Python
changes; refresh the browser to load updated UI assets.

The therapy-area field and abdominal oblique icons passed all 73 Python/browser
tests, Ruff, formatting, whitespace, and public-file checks. Export/import retains
therapy text independently of session notes. A consistent backup preceded the
therapy-area migration; initial defaults live only in ignored local settings.
The existing draft's blank area field was prefilled without changing workout
results. Historical therapy updates await the user's date-range choice.

Separate therapy rows and extra numeric sets passed all 83 Python/browser tests,
including live-browser additions/removal/Undo at both HTMX settle delays and
export/import of unplanned sets. Numeric-looking area names remain compatible
with the legacy note reader. A consistent backup preceded the row migration;
live home/history/health and the split draft labels were verified. Synthetic
desktop/mobile views had no horizontal overflow.

Cancellation and Dashboard passed all 95 Python/browser tests, including
confirmation dismiss/accept with an invalid input, all three metrics, empty and
filtered history, bodyweight zeros, precision, and authenticated access. SVG charts
fit desktop/mobile widths without cropping; the table scrolls inside its panel.
The local app was restarted and health/workout/history/dashboard plus reps/volume
filters returned HTTP 200. Read-only verification preserved the current draft.

## GitHub publication — 2026-10-12

Changes are grouped into independently verified commits for Google sign-in/VPS
hosting, workout set/therapy row controls, and cancellation/dashboard insights.
The complete release passed 95 Python/browser tests, eight dbt models and 35 data
tests, Ruff, compilation, SQLFluff, whitespace, and public-file checks. Intermediate
commits passed their 66-test and 83-test suites. Publication candidates passed
Gitleaks scans and retain the GitHub noreply identity. Local settings, databases,
screenshots, backups, and generated dbt `.user.yml` remain ignored. Publication
does not deploy or cut over the VPS; local recording remains active.
