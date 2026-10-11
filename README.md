# Gym Workouts

A local desktop workout logger with alternating A/B routines, editable lb/reps,
automatic Obsidian saving, and a dbt analytics pipeline. Built with Python,
FastAPI, SQLite, DuckDB, and dbt for Analytics Engineering practice.

## What it does

- Suggests A/B after each completed workout; defaults come from the latest
  completed session of the same routine, with template fallbacks.
- Autosaves drafts and resumes after reload. Record Done/Skip, remove an exercise
  for a session, or undo removal. New sessions restore the routine's items.
- Supports core exercises and a nonnumeric physical-therapy completion/notes item.
- Publishes finished workouts as dated Markdown notes in your configured folder.
  Failed writes remain retryable; existing differing notes are never overwritten.
- Provides workout history and an explicit SQLite → DuckDB → dbt refresh.

Desktop Chrome is the primary target. The app runs locally while its server is open.

## Setup

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). No hosting account is required.

```bash
uv sync --locked --all-groups
cp .env.example .env
```

Edit `.env`: set `GYM_WORKOUT_DIR` to your own Obsidian workout folder and
`GYM_TIMEZONE` to your IANA timezone. Relative paths resolve inside this checkout.
Without an override, workout notes live in the ignored `data/raw/workout` folder.
Use native paths with native Python or WSL paths with WSL Python.

Create `_workout-a.md` and `_workout-b.md` in that folder. Each must contain at
least one numeric set row, formatted as `exercise name weight reps`. Repeat an
exercise on consecutive rows for multiple sets. For example, these **invented**
values illustrate the format:

```text
example exercise 12.5 8
example exercise 15 6
leg raise 0 10
left oblique raise 0 10
right oblique raise 0 10
```

Choose your own exercises and values for each template. Physical therapy is added
as an activity automatically when absent. Templates remain unchanged during use.

Existing dated notes use `YYYY-MM-DD Workout A.md` or `... B.md`; archive folders
are included. Unmarked imported notes require completion review in `/history`.
Optionally set `GYM_LEGACY_THROUGH` to a reviewed ISO date or pass
`--legacy-through YYYY-MM-DD` during initialization/import to confirm older notes.
App-written notes carry explicit completion metadata.

```bash
uv run --env-file .env gym-init
uv run --env-file .env gym-web
```

Open **http://127.0.0.1:8010**. On Windows with WSL, double-click
**Start Gym Workouts.bat** after setup; it loads `.env` and opens the default port.
Keep its server window open. Do not share a `.venv` between Windows and WSL Python.
The launcher selects `Ubuntu-22.04`; set the Windows environment variable
`GYM_WSL_DISTRO` to use a different distribution where you installed the app.
For a custom port, use the command-line launch and open its printed URL.

## Record a workout

1. Start the suggested routine or choose A/B. Edit weights and reps in lb.
2. Select Done/Skip, or confirm **Mark remaining done**. Valid edits autosave.
3. Use ×/Undo for session-only removal; add session or activity notes as needed.
4. Select **Finish workout**. A/B advances after successful Markdown publication.

Reloading resumes drafts. Same-date/same-routine requests reopen the existing
session. Legacy defaults follow recorded order and label that assumption; uncertain
historical planned-set identities remain unknown. Rescan notes with
`uv run --env-file .env gym-import`; changed imported files are reported as conflicts.

## Analytics Engineering

| Layer | Tools |
| --- | --- |
| Runtime | Python 3.12, uv, locked dependencies |
| App | FastAPI/Uvicorn, Jinja2, vendored HTMX |
| Operational data | SQLite, SQLAlchemy, Alembic |
| Analytics | dbt Core, dbt-duckdb, DuckDB |
| Quality | pytest/HTTPX/Playwright, Ruff, SQLFluff, pre-commit, GitHub Actions |

A consistent SQLite extract publishes content-addressed snapshots and a manifest
in DuckDB. Eight dbt models build staging → intermediate → facts/dimensions, with
35 data tests. Numeric facts exclude therapy and removed/skipped/unfinished sets.
Recorded load-volume means external lb × performed reps; bodyweight effort,
duration, adherence, and fitness outcomes are not inferred.

For your local private workout data:

```bash
uv run --env-file .env gym-snapshot
GYM_USE_SYNTHETIC=false GYM_DBT_DATABASE_PATH=data/warehouse/gym.duckdb uv run dbt build --profiles-dir .
GYM_USE_SYNTHETIC=false GYM_DBT_DATABASE_PATH=data/warehouse/gym.duckdb uv run dbt docs generate --profiles-dir .
```

Use those environment variables with `uv run dbt docs serve --profiles-dir .
--host 127.0.0.1 --port 8081` to explore local lineage and documentation.
Analytics refresh is explicit and does not block workout recording.

Follow `stg_operational__workout_sets` → `int_completed_workout_sets` →
`fct_workout_sets`, then inspect `models/schema.yml` and `tests/dbt/` to practice
status filtering, grains, relationships, and metric definitions.

Synthetic CI uses a separate `data/warehouse/gym_ci.duckdb`. Never seed the private
warehouse: seeding overwrites raw fixture relations. Hosted BigQuery/dbt Platform
is a future milestone; see [the roadmap](docs/hosted-analytics-roadmap.md).

## Privacy and verification

The repository contains source code and invented test/seed data. Your workout
notes, results, databases, generated dbt docs, screenshots, reports, credentials,
and machine configuration stay local and are ignored by Git. Keep real notes in
your configured vault or ignored `data/raw` directory. Never paste private data
into tracked docs, fixtures, or issue reports.

```bash
bash scripts/check.sh
```

This runs Python checks, workflow tests, compilation, dbt checks, SQLFluff, and
public-file policy checks with synthetic fixtures. For browser verification:

```bash
uv run playwright install --with-deps chromium
GYM_BROWSER_TESTS=1 bash scripts/check.sh
```

`GYM_CHROMIUM_PATH` can select an existing Chromium executable. Tests use temporary
databases and vaults. Back up local SQLite with your vault; stop the web process
before copying SQLite so no WAL writes remain outstanding.

## Project record

- [Architecture](docs/architecture.md)
- [Data contract and metrics](docs/data-contract.md)
- [Research and plan](notes/Research%20and%20Plan%202026-10-10.md)
- [Project memory](MEMORY.md)
- [Implementation session](notes/Session%20Notes%202026-10-10.md)
- [Publication preparation](notes/Session%20Notes%202026-10-11.md)
