import sqlite3
from dataclasses import replace
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from conftest import edits
from sqlalchemy import select

from gym_workouts.analytics import extract_snapshot
from gym_workouts.cli import migrate
from gym_workouts.config import ROOT
from gym_workouts.contracts import SessionCommand
from gym_workouts.dashboard import dashboard_data
from gym_workouts.models import Exercise, RoutineSet, User, WorkoutSession
from gym_workouts.services import WorkoutService


@pytest.fixture
def other_service(configured):
    _settings, factory, service = configured
    user_id = str(uuid4())
    with factory.begin() as db:
        db.add(User(id=user_id, email="guest@example.com"))
        db.flush()
        for row in db.scalars(select(RoutineSet)).all():
            db.add(
                RoutineSet(
                    id=str(uuid4()),
                    user_id=user_id,
                    routine=row.routine,
                    position=row.position,
                    exercise_id=row.exercise_id,
                    occurrence=row.occurrence,
                    weight=1 if row.weight is not None else None,
                    reps=1 if row.reps is not None else None,
                )
            )
        db.add(
            Exercise(
                id="guest-exercise", name="Guest private exercise", measurement_type="weight_reps"
            )
        )
        db.flush()
        db.add(
            RoutineSet(
                id="guest-only-template",
                user_id=user_id,
                routine="A",
                position=99,
                exercise_id="guest-exercise",
                occurrence=1,
                weight=1,
                reps=1,
            )
        )
    scoped = service.for_user(user_id)
    scoped.settings = replace(scoped.settings, therapy_areas="Private owner defaults")
    return scoped


def test_users_have_separate_drafts_defaults_and_session_commands(configured, other_service):
    settings, _factory, owner = configured
    guest = other_service
    assert guest.state()["last"] is None
    assert guest.state()["review"] == []
    first = guest.start("A")
    assert first["sets"][0]["weight"] == "1"
    assert first["therapy_areas"] == ""
    assert owner.state()["session"] is None
    second = owner.start("B")
    assert second["id"] != first["id"]
    assert second["sets"][0]["weight"] == "47.5"
    assert guest.state()["session"]["id"] == first["id"]
    assert owner.state()["session"]["id"] == second["id"]
    for actor, foreign in [(guest, second), (owner, first)]:
        with pytest.raises(LookupError):
            actor.get(foreign["id"])
        with pytest.raises(LookupError):
            actor.command(foreign["id"], SessionCommand(**edits(foreign, "cancel")))
        with pytest.raises(LookupError):
            actor.approve_import(foreign["id"])
        with pytest.raises(LookupError):
            actor.retry_write(foreign["id"])
    payload = edits(first, "finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    with pytest.raises(ValueError, match="Obsidian publication"):
        guest.command(first["id"], SessionCommand(**payload))
    assert guest.get(first["id"])["status"] == "draft"
    assert not (settings.workout_dir / "2026-10-11 Workout A.md").exists()


def test_dashboard_and_snapshot_exclude_other_users(configured, other_service):
    settings, factory, owner = configured
    foreign = other_service.start("A")
    with factory.begin() as db:
        workout = db.get(WorkoutSession, foreign["id"])
        workout.status = "completed"
        for row in workout.rows:
            row.state = "performed"
    assert dashboard_data(factory, owner.today(), user_id=owner.user_id)["session_count"] == 2
    assert (
        dashboard_data(factory, owner.today(), user_id=other_service.user_id)["session_count"] == 1
    )
    assert owner.state()["suggested"] == "B"
    assert other_service.state()["suggested"] == "B"
    snapshot, _checksum = extract_snapshot(settings.database_path)
    sessions = snapshot["tables"]["workout_sessions"]
    assert len(sessions["rows"]) == 2
    assert foreign["id"] not in {row[sessions["columns"].index("id")] for row in sessions["rows"]}
    sets = snapshot["tables"]["workout_sets"]
    assert foreign["id"] not in {row[sets["columns"].index("session_id")] for row in sets["rows"]}
    assert "users" not in snapshot["tables"]
    assert all("user_id" not in table["columns"] for table in snapshot["tables"].values())
    assert "Guest private exercise" not in str(snapshot)


def test_changing_configured_email_cannot_transfer_existing_workouts(configured):
    settings, factory, _service = configured
    owner = WorkoutService(factory, replace(settings, allowed_email="owner@example.com"))
    with pytest.raises(ValueError, match="existing workout owner"):
        WorkoutService(factory, replace(settings, allowed_email="another@example.com"))
    with factory() as db:
        assert db.get(User, owner.user_id).email == "owner@example.com"


def test_ownership_migration_preserves_existing_rows_and_foreign_keys(configured):
    settings, _factory, service = configured
    service.start("A")
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_path"] = settings.database_path
    command.downgrade(config, "c9e42b801d65")
    tables = ["workout_sessions", "routine_sets", "workout_sets", "source_records", "vault_writes"]
    with sqlite3.connect(settings.database_path) as db:
        before = {
            name: db.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall() for name in tables
        }
        columns = {
            name: [r[1] for r in db.execute(f"PRAGMA table_info({name})")] for name in tables
        }
        db.execute(
            "INSERT INTO login_sessions VALUES "
            "('old-session', 'old-subject', 'owner@example.com', 9999999999)"
        )
    migrate(replace(settings, allowed_email="owner@example.com"))
    with sqlite3.connect(settings.database_path) as db:
        owner_id, email = db.execute("SELECT id,email FROM users WHERE vault_owner=1").fetchone()
        assert email == "owner@example.com"
        for table in tables:
            names = ",".join(columns[table])
            assert db.execute(f"SELECT {names} FROM {table} ORDER BY 1").fetchall() == before[table]
        assert db.execute("SELECT DISTINCT user_id FROM workout_sessions").fetchall() == [
            (owner_id,)
        ]
        assert db.execute("SELECT DISTINCT user_id FROM routine_sets").fetchall() == [(owner_id,)]
        assert db.execute("SELECT count(*) FROM login_sessions").fetchone()[0] == 0
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        for table in ("workout_sessions", "routine_sets"):
            assert next(r for r in db.execute(f"PRAGMA table_info({table})") if r[1] == "user_id")[
                3
            ]
        # Table reconstruction retains the original status and numeric checks.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE workout_sessions SET status = 'invalid'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE routine_sets SET weight = -1")
