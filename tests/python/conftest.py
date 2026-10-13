"""Invented test workouts; never copied from the private vault."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gym_workouts.app import create_app
from gym_workouts.cli import migrate
from gym_workouts.config import Settings
from gym_workouts.database import create_database
from gym_workouts.importer import import_workouts
from gym_workouts.services import WorkoutService


@pytest.fixture
def configured(tmp_path: Path, request):
    vault = tmp_path / "workout"
    vault.mkdir()
    (vault / "_workout-a.md").write_text(
        "squat 30 8\nsquat 40 5\nrow 20 8\nleg raise 0 12\n"
        "left oblique raise 0 10\nright oblique raise 0 10\n"
    )
    (vault / "_workout-b.md").write_text(
        "deadlift 50 8\nbench press 30 8\n"
        + "bench press 40 5\n" * (getattr(request, "param", 2) - 1)
        + "front raise 10 6\nleg raise 0 12\n"
        "left oblique raise 0 10\nright oblique raise 0 10\n"
    )
    archive = vault / "workout-archived"
    archive.mkdir()
    (archive / "2026-10-09 Workout B.md").write_text(
        "# Test B\n\ndeadlift 47.5 7\nbench press 25 6\nfront raise 9 7\nphysical therapy\n"
    )
    (vault / "2026-10-10 Workout A.md").write_text(
        "# Test A\n\nsquat 27.5 7\nsquat 37.5 4\nrow 18 9\n"
    )
    settings = Settings(tmp_path / "gym.sqlite3", vault, tmp_path / "gym.duckdb")
    migrate(settings)
    engine, factory = create_database(settings.database_path)
    import_workouts(factory, vault, legacy_through="2026-10-10")
    service = WorkoutService(factory, settings)
    service.today = lambda: "2026-10-11"
    yield settings, factory, service
    engine.dispose()


@pytest.fixture
def client(configured):
    settings, _factory, _service = configured
    app = create_app(settings)
    app.state.service.today = lambda: "2026-10-11"
    with TestClient(app) as client:
        yield client


def edits(workout, action="save", **overrides):
    payload = {
        "revision": workout["revision"],
        "action": action,
        "notes": workout["notes"],
        "therapy_areas": workout["therapy_areas"],
        "sets": [
            {key: row[key] for key in ("id", "weight", "reps", "state")} for row in workout["sets"]
        ],
    }
    payload.update(overrides)
    return payload


def form_values(workout, action="save"):
    values = {
        "revision": str(workout["revision"]),
        "notes": workout["notes"],
        "therapy_areas": workout["therapy_areas"],
        "action": action,
    }
    for row in workout["sets"]:
        values[f"state_{row['id']}"] = row["state"]
        if row["type"] == "weight_reps":
            values[f"weight_{row['id']}"] = row["weight"]
            values[f"reps_{row['id']}"] = str(row["reps"])
        else:
            values[f"area_{row['id']}"] = row["activity_area"]
    return values
