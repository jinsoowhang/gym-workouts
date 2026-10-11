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

`deploy/compose.yml` runs the app in Docker on host loopback with persistent
SQLite and a mounted, synced workout folder. `GYM_ALLOWED_HOSTS` accepts only
explicit hostnames; local defaults and mutation-origin checks remain active.
The optional Cloudflare Tunnel connector validates Access JWTs before forwarding
requests. Google authentication belongs in Cloudflare Access with a specific
email allowlist; Desktop Google OAuth credentials cannot supply web sign-in.

A private VPS staging instance is running. The existing Syncthing vault includes
the workout folder and can sync completed notes back to the PC. Public routing,
Google provider configuration, the user's allowed Gmail address, and final
database cutover remain pending. Private deployment details are recorded in the
ignored `.secrets/vps-deployment-status.json`; see `docs/vps-deployment.md` for
the portable setup. Stop the local recorder and take a final consistent SQLite
backup before switching active recording to the VPS. Never sync live SQLite.
