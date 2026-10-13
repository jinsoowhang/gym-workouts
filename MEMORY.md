# Project Memory

## Goal and status

Desktop workout recording and Analytics Engineering practice. The local app and
SQLite/DuckDB/dbt pipeline are implemented; hosted analytics remains future work.

## Behavior and ownership

- A/B advances after successful completion and Markdown publication.
- Defaults use latest completed same-routine results in lb, with template fallbacks.
- Drafts autosave, resume, reject stale revisions, and preserve edits at Finish.
- Exercise removal is session-only with Undo. Core and therapy return in new sessions.
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

Direct Google OAuth is implemented and ready for publication; hosted deployment
is still pending. It uses Authlib OIDC validation, PKCE, secure session cookies, hashed
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

Google sign-in publication is prepared with private credentials and machine settings
excluded. Synthetic authentication/browser verification accompanies the implementation.
Hosted Google account setup, public routing, and database cutover remain pending.
