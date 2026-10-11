# Gym Workouts — Research and Plan

Status: local desktop app and analytics implemented; hosted analytics deferred.
This public plan describes product contracts without private workout records.

## Requirements

- Desktop A/B recording with editable lb/reps and latest completed same-routine defaults.
- Autosaving drafts, completion-based alternation, Done/Skip, session-only ×/Undo.
- Core exercises and a physical-therapy activity with notes and no invented measurements.
- Automatic completed-note publication to a configured local Obsidian workout folder.
- Preserve template/source order, including interleaved sets and irregular historical rows.
- An operational/analytical split suitable for Analytics Engineering practice.

## Architecture

Python 3.12/uv; FastAPI/Jinja/HTMX; SQLAlchemy/SQLite/Alembic; consistent snapshots
into DuckDB; dbt staging/intermediate/marts; pytest/browser/data-quality checks.
SQLite owns drafts/results. Completed Markdown mirrors use durable, retryable,
no-clobber publication. Cloud services are never needed for recording.

Unknown legacy set identities remain unknown. Defaults reuse observed values in
recorded order with a visible assumption; extra sets fall back to templates.
Unmarked notes require completion review unless a user supplies a reviewed cutoff.

## Delivery and verification

1. Contracts, schema, configuration, and invented fixtures.
2. Idempotent source import and ordered defaults.
3. Desktop recording, autosave, stale-revision checks, and draft recovery.
4. Durable vault publication, conflicts, retries, and restart recovery.
5. Consistent snapshots, eight dbt models, 35 data tests, and local documentation.
6. Future hosted BigQuery/dbt Platform setup with isolated configuration and parity checks.

Verify import fidelity, missing sets, removals, completion order, current-input
Finish, duplicate prevention, write recovery, populated migrations, snapshot
rollback, fact grains, arithmetic, relationships, and private-file exclusion.
Use temporary vaults and synthetic data for automation.

Phone support, permanent routine editing, historical TSV classification, and
additional dashboard screens remain deferred.

## Reference documentation

- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [HTMX triggers](https://htmx.org/attributes/hx-trigger/)
- [dbt project structure](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)
- [Python filesystem operations](https://docs.python.org/3/library/os.html)
