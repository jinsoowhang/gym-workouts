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
