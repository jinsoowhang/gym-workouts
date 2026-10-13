import duckdb
import pytest
from conftest import edits
from sqlalchemy import text

from gym_workouts.analytics import extract_snapshot, load_snapshot
from gym_workouts.contracts import SessionCommand


def test_snapshot_is_idempotent_and_manifest_counts_match(configured):
    settings, _factory, _service = configured
    first = load_snapshot(settings.database_path, settings.warehouse_path)
    second = load_snapshot(settings.database_path, settings.warehouse_path)
    assert second["unchanged"] and second["snapshot_id"] == first["snapshot_id"]
    with duckdb.connect(str(settings.warehouse_path)) as db:
        assert db.execute("SELECT count(*) FROM gym_raw.raw_snapshot_manifest").fetchone()[0] == 1
        for name, count in first["row_counts"].items():
            assert db.execute(f"SELECT count(*) FROM gym_raw.raw_{name}").fetchone()[0] == count
        columns = [r[0] for r in db.execute("DESCRIBE gym_raw.raw_source_records").fetchall()]
        assert "original_text" not in columns
        columns = [r[0] for r in db.execute("DESCRIBE gym_raw.raw_workout_sessions").fetchall()]
        assert "therapy_areas" not in columns
        columns = [r[0] for r in db.execute("DESCRIBE gym_raw.raw_workout_sets").fetchall()]
        assert "activity_area" not in columns


def test_changed_operational_state_creates_new_complete_snapshot(configured):
    settings, _factory, service = configured
    first = load_snapshot(settings.database_path, settings.warehouse_path)
    workout = service.start()
    payload = edits(workout)
    payload["sets"][0].update(weight="42.125", reps=2)
    service.command(workout["id"], SessionCommand(**payload))
    second = load_snapshot(settings.database_path, settings.warehouse_path)
    assert first["snapshot_id"] != second["snapshot_id"]
    with duckdb.connect(str(settings.warehouse_path)) as db:
        actual = db.execute(
            "SELECT weight FROM gym_raw.raw_workout_sets WHERE id = ? AND snapshot_id = ?",
            [workout["sets"][0]["id"], second["snapshot_id"]],
        ).fetchone()[0]
        assert str(actual) == "42.1250"


def test_operational_drift_is_rejected(configured):
    settings, factory, _service = configured
    with factory.begin() as db:
        db.execute(text("ALTER TABLE exercises ADD COLUMN unexpected TEXT"))
    with pytest.raises(ValueError, match="schema drift"):
        extract_snapshot(settings.database_path)


def test_warehouse_drift_rolls_back_partial_snapshot(configured):
    settings, _factory, _service = configured
    with duckdb.connect(str(settings.warehouse_path)) as db:
        db.execute("CREATE SCHEMA gym_raw")
        db.execute("CREATE TABLE gym_raw.raw_workout_sets (unexpected VARCHAR)")
    with pytest.raises(ValueError, match="Warehouse schema drift"):
        load_snapshot(settings.database_path, settings.warehouse_path)
    with duckdb.connect(str(settings.warehouse_path)) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_name = 'raw_snapshot_manifest'"
            ).fetchone()[0]
            == 0
        )
