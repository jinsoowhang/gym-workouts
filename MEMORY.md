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
- The Physical Therapy card links to Laina Health in a new tab. User-specified
  label capitalization belongs in private runtime data and initial settings.
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

Hosted Start workout was fixed on 2026-10-19 after reproducing a same-origin
POST rejection through the public proxy chain. With authentication enabled,
mutation Origin checks use the configured HTTPS `GYM_PUBLIC_URL`, because the
upstream connection may be HTTP after TLS termination. Local mode still uses the
request origin; host checks and foreign-origin rejection remain enforced.
Regression tests cover authenticated workout creation over HTTP/HTTPS upstreams
and rejection of incorrect Origin schemes, hosts, and ports. Verification passed
56 scoped tests and both browser workflows. The rebuilt VPS app is healthy and
public same-origin requests now reach authentication instead of being rejected
by the origin boundary. Actual owner recording and note sync still need confirmation.

The selected hosting design now uses direct Google sign-in in the app behind the
VPS's existing Nginx Proxy Manager. Cloudflare Access/Tailscale is not required.
`deploy/compose.yml` joins the existing proxy network without publishing a host
port, with persistent SQLite and the synced workout folder. The hosted app admits
only the verified email in private settings. Local mode keeps its existing flow.

Direct Google OAuth is implemented and deployed as of 2026-10-18. It uses
Authlib OIDC validation, PKCE, secure session cookies, hashed
server-side sessions, a fixed 24-hour expiry, and logout revocation. Missing Google
credentials fail closed. A new Alembic migration adds login sessions; apply it
before running the updated app. All 66 Python/browser tests, Ruff, formatting,
whitespace checks, and the public-file policy passed at this checkpoint.

The VPS now runs the current app on the proxy's private Docker network with no
published app port. An HTTPS proxy route and managed certificate are installed.
The existing Syncthing vault includes the workout folder and can sync completed
notes back to the PC. The approved Gmail address and Google Web application
credentials are saved only in private settings. The local server was confirmed
stopped before a consistent SQLite snapshot replaced the older staging database;
all remote completed workouts were present in that snapshot. Never sync live SQLite.
Deployment details are recorded in the ignored `.secrets/vps-deployment-status.json`;
see `docs/vps-deployment.md` for the portable setup. Actual owner sign-in and an
authenticated recording with note sync still need user verification.

The published VPS changes passed an independent GitHub clone audit of all six
reachable commits and 106 distinct file versions: no private deployment identifiers,
no secrets found by Gitleaks, and no private login address in commit metadata.

The local recorder remains stopped after the VPS database cutover. Use the hosted
app for subsequent recording once owner sign-in is confirmed; do not record into
both databases. The Windows launcher still opens local mode pending authenticated
recording and note-sync verification. Keep the GitHub noreply identity and private
settings out of publication.

## Account ownership — 2026-10-18

The deployed schema now has users and required user ownership on workout sessions,
personal routine sets, and login sessions. The migration assigns all existing
workouts and drafts to the configured owner, preserves original workout data,
and revokes old login sessions. The first fresh verified Google login binds the
owner's stable Google subject; changing the configured email cannot transfer data.
Owner identity stays in private settings and is not hardcoded in source or notes.

Repositories, defaults, active drafts, history, dashboard queries, review actions,
and session commands are scoped to the authenticated user. Foreign workout IDs
return not found. Obsidian import/publication/recovery and analytics extracts are
exclusive to the vault owner. Snapshots exclude other users' sessions, sets,
templates, publications, and exercises, and retain compatible warehouse columns
without user emails, Google subjects, or account IDs.

Registration remains closed. The accepted future direction is invitations and
editable generic starter routines with empty history; invitation flows, routine
editing, and website-only completion for additional users remain future work.
Do not enable additional accounts before those workflows are implemented.

The local inactive database and hosted database were backed up and migrated
independently. The live server has exactly one account and all sessions/templates
belong to it. Migration rehearsal on a private copy and live before/after row
comparisons preserved preexisting data. Verification passed 103 Python/browser
tests, eight dbt models and 35 data tests, Ruff, formatting, SQLFluff, compilation,
whitespace, public-file policy, and live HTTPS/authentication-boundary checks.
The owner must sign in again after this migration; actual owner sign-in and
authenticated recording with note sync remain manual checks.

## Login design options — 2026-10-18

The user requested design research and options for a professional, pleasant login
page, then selected Quiet focus. The previous login reused `.start-panel` with
only one child in its narrow first grid column. The deployed page now uses its
own centered ivory/sage card and dedicated `login.css`, leaving workout styling
scoped to its existing pages.

Research and interactive previews are in `notes/Login Design Research 2026-10-18.md`
and `notes/Login Design Options 2026-10-18.html`. Three directions are Quiet focus
(recommended, centered ivory/sage), Training journal (warm split editorial), and
After hours (charcoal/mint). Google-button branding, readable contrast, one clear
action, visible focus, mobile sizing, truthful access notes, and no public owner
data guide the options. Screenshots live in ignored reports. Preview controls,
375px overflow, 48px buttons, and JavaScript errors were checked in Chromium.
Quiet focus is implemented and deployed. The Google button uses the current
official downloaded SVG logo/outlined label with a responsive 48px link boundary;
the logo colors and label artwork are unchanged. The base template exposes small
blocks for page styling, body class, navigation, skip label, and footer. Login
error/status announcements and the existing OAuth redirect are retained.

Verification passed 34 authentication/configuration tests and both existing
browser recording workflows. Ready, OAuth-error, and unavailable states were
checked at 1440/375/320px, including focus, target size, asset loading, and overflow.
All checked normal-size text pairs exceed 4.5:1 contrast. Live desktop/mobile
Chromium screenshots, asset hashes, health and anonymous API protection passed.
Deployment source/image rollback backups and screenshots remain private/ignored.

## Workout warm-up — 2026-10-16

Ready and draft workouts show a warm-up video card before the routine/exercises
for both A and B. It embeds the supplied YouTube video using youtube-nocookie.com
and offers a new-tab YouTube link. The player has no autoplay; warm-up is a visual
guide, without a separate recorded completion state. Completed history is unchanged.
CSP permits frames only from the embed host. The stylesheet URL is versioned to
refresh cached styles. All 95 Python/browser tests passed; synthetic A/B desktop
and mobile checks verified placement, reloads, and no horizontal overflow. Actual
external YouTube playback was not exercised by verification.

For interactive use, start the Windows `Start Gym Workouts.bat` launcher through
Windows Start-Process. A server backgrounded inside an agent shell stopped after
the chat turn despite nohup. The Windows launcher gives the server its own window;
verify `/health` and the workout page from Windows, and keep that window open.

## Weight and rep indicators — 2026-10-16

Each numeric field compares its current value with its own saved session default.
Green up arrows indicate increases and red down arrows indicate decreases; equal,
blank, invalid, and removed fields show no arrow. Indicators update immediately
and reinitialize after HTMX replacements and reloads, including completed results.
Indicators include the signed difference and unit below the field (an invented
12 → 15 lb example shows ↑ +3 lb), rounded to the supported four decimal places
without floating-point noise. Accessible descriptions identify the amount,
baseline, and unit. This is presentation only;
default values, autosave requests, and stored workout results retain their behavior.

Publication preparation passed all 95 Python/browser tests, eight dbt models and
35 data tests, Ruff, JavaScript syntax, compilation, SQLFluff, and public-file
checks. Warm-up and numeric-indicator commits each passed 45 scoped tests from
independent staged source snapshots. Private settings and runtime data stay local.

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
