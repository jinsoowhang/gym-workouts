import json
from dataclasses import replace

import pytest
from alembic import command
from alembic.config import Config
from conftest import edits, form_values
from pydantic import ValidationError
from sqlalchemy import func, select, text

from gym_workouts.app import exercise_groups
from gym_workouts.cli import migrate
from gym_workouts.config import ROOT
from gym_workouts.contracts import SessionCommand, parse_note
from gym_workouts.database import create_database
from gym_workouts.importer import import_workouts
from gym_workouts.models import RoutineSet
from gym_workouts.services import ConflictError, WorkoutService


def test_extra_set_copies_current_values_groups_and_does_not_change_template(configured):
    _settings, factory, service = configured
    workout = service.start()
    bench = [row for row in workout["sets"] if row["name"] == "bench press"]
    payload = edits(workout, action=f"add-set:{bench[-1]['exercise_id']}")
    next(row for row in payload["sets"] if row["id"] == bench[-1]["id"]).update(
        weight="35.125", reps=9
    )
    added = service.command(workout["id"], SessionCommand(**payload))
    extra = added["sets"][-1]
    assert (extra["name"], extra["occurrence"], extra["weight"], extra["reps"]) == (
        "bench press",
        3,
        "35.125",
        9,
    )
    assert extra["template_key"] is None and extra["state"] == "pending"
    assert len({row["position"] for row in added["sets"]}) == len(added["sets"])
    groups = exercise_groups(added["sets"])
    assert len(groups) == 7
    assert len(next(group for group in groups if group["title"] == "Bench Press")["rows"]) == 3
    with factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(RoutineSet)
                .where(RoutineSet.exercise_id == extra["exercise_id"], RoutineSet.routine == "B")
            )
            == 2
        )
    with pytest.raises(ConflictError):
        service.command(workout["id"], SessionCommand(**payload))
    with pytest.raises(ValueError, match="Exercise is not in this session"):
        service.command(workout["id"], SessionCommand(**edits(added, action="add-set:foreign")))
    assert service.get(workout["id"])["revision"] == added["revision"]


def test_added_set_removal_and_readdition_keep_distinct_occurrences(client, configured):
    settings, _factory, service = configured
    workout = client.post("/api/v1/sessions", json={}).json()
    bench = next(row for row in workout["sets"] if row["name"] == "bench press")
    url = f"/sessions/{workout['id']}/command"
    response = client.post(url, data=form_values(workout, f"add-set:{bench['exercise_id']}"))
    assert response.status_code == 200
    added = service.get(workout["id"])
    extra = added["sets"][-1]
    removed = service.command(
        workout["id"], SessionCommand(**edits(added, action=f"remove-set:{extra['id']}"))
    )
    added = service.command(
        workout["id"], SessionCommand(**edits(removed, action=f"add-set:{bench['exercise_id']}"))
    )
    assert added["sets"][-1]["occurrence"] == 4
    assert client.post(url, data=form_values(added, "finish")).status_code == 200
    parsed = parse_note((settings.workout_dir / "2026-10-11 Workout B.md").read_text())
    recorded = [row for row in parsed.rows if row.name == "bench press"]
    assert [row.occurrence for row in recorded] == [1, 2, 3, 4]
    assert [row.state for row in recorded] == ["performed", "performed", "removed", "performed"]
    rebuilt = replace(
        settings, database_path=settings.database_path.parent / "rebuilt-added.sqlite3"
    )
    migrate(rebuilt)
    engine, factory = create_database(rebuilt.database_path)
    try:
        assert not import_workouts(factory, rebuilt.workout_dir)["issues"]
        restored = WorkoutService(factory, rebuilt).get(workout["id"])
        bench_rows = [row for row in restored["sets"] if row["name"] == "bench press"]
        assert [row["occurrence"] for row in bench_rows] == [1, 2, 3, 4]
        assert bench_rows[-1]["template_key"] is None
    finally:
        engine.dispose()
    service.today = lambda: "2026-10-12"
    fresh = service.start("B")
    assert len([row for row in fresh["sets"] if row["name"] == "bench press"]) == 2


def test_therapy_areas_are_independent_and_undo_preserves_labels(configured):
    settings, factory, original = configured
    service = WorkoutService(factory, replace(settings, therapy_areas="Ankle, elbow"))
    service.today = original.today
    workout = service.start()
    areas = [row for row in workout["sets"] if row["type"] == "activity"]
    assert [row["activity_area"] for row in areas] == ["Ankle", "elbow"]
    removed = service.command(
        workout["id"], SessionCommand(**edits(workout, action=f"remove-set:{areas[0]['id']}"))
    )
    assert removed["therapy_areas"] == "elbow"
    assert [row["state"] for row in removed["sets"] if row["type"] == "activity"] == [
        "removed",
        "pending",
    ]
    restored = service.command(
        workout["id"], SessionCommand(**edits(removed, action=f"restore-set:{areas[0]['id']}"))
    )
    assert restored["therapy_areas"] == "Ankle, elbow"
    added = service.command(
        workout["id"],
        SessionCommand(**edits(restored, action=f"add-set:{areas[0]['exercise_id']}")),
    )
    extra = added["sets"][-1]
    assert extra["activity_area"] == "" and extra["occurrence"] == 3
    payload = edits(added)
    for row in payload["sets"]:
        current = next(item for item in added["sets"] if item["id"] == row["id"])
        if current["type"] == "activity":
            row["activity_area"] = "Wrist" if row["id"] == extra["id"] else current["activity_area"]
    saved = service.command(workout["id"], SessionCommand(**payload))
    assert saved["therapy_areas"] == "Ankle, elbow, Wrist"
    removed = service.command(
        workout["id"], SessionCommand(**edits(saved, action=f"remove-set:{areas[0]['id']}"))
    )
    payload = edits(removed, action="finish")
    for row in payload["sets"]:
        if row["state"] != "removed":
            row["state"] = "performed"
    service.command(workout["id"], SessionCommand(**payload))
    parsed = parse_note((settings.workout_dir / "2026-10-11 Workout B.md").read_text())
    recorded = [row for row in parsed.rows if row.name == "physical therapy"]
    assert [(row.activity_area, row.state) for row in recorded] == [
        ("Ankle", "removed"),
        ("elbow", "performed"),
        ("Wrist", "performed"),
    ]
    service.today = lambda: "2026-10-12"
    fresh = service.start("A")
    assert [row["activity_area"] for row in fresh["sets"] if row["type"] == "activity"] == [
        "Ankle",
        "elbow",
        "Wrist",
    ]


@pytest.mark.parametrize("area", ["a" * 501, "Ankle\nElbow"])
def test_invalid_row_area_is_rejected_without_saving(configured, area):
    _settings, _factory, service = configured
    workout = service.start()
    payload = edits(workout)
    payload["sets"][-1]["activity_area"] = area
    with pytest.raises(ValidationError):
        SessionCommand(**payload)
    assert service.get(workout["id"])["revision"] == 0
    payload["sets"][-1]["activity_area"] = ""
    payload["sets"][0]["activity_area"] = "Ankle"
    with pytest.raises(ValueError, match="Only physical therapy"):
        service.command(workout["id"], SessionCommand(**payload))
    assert service.get(workout["id"])["revision"] == 0


def test_older_combined_therapy_note_imports_as_separate_rows(configured):
    settings, factory, service = configured
    metadata = {
        "status": "completed",
        "therapy_areas": "Ankle, elbow",
        "gym_sets": [
            {
                "name": "physical therapy",
                "position": 0,
                "occurrence": 1,
                "weight": None,
                "reps": None,
                "state": "performed",
                "template_key": None,
            }
        ],
    }
    content = "---\n" + "\n".join(f"{key}: {json.dumps(value)}" for key, value in metadata.items())
    content += "\n---\nphysical therapy\n"
    path = settings.workout_dir / "2026-10-11 Workout B.md"
    path.write_text(content)
    parsed = parse_note(content)
    assert [row.activity_area for row in parsed.rows] == ["Ankle", "elbow"]
    report = import_workouts(factory, settings.workout_dir)
    assert report["imported"] == 1 and not report["issues"]
    workout = service.state()["session"]
    assert [row["activity_area"] for row in workout["sets"]] == ["Ankle", "elbow"]
    assert path.read_text() == content


def test_custom_area_label_is_carried_without_splitting(configured):
    _settings, _factory, service = configured
    workout = service.start()
    payload = edits(workout, action="finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    payload["sets"][-1]["activity_area"] = "Shoulder, left"
    service.command(workout["id"], SessionCommand(**payload))
    service.today = lambda: "2026-10-12"
    fresh = service.start("A")
    areas = [row["activity_area"] for row in fresh["sets"] if row["type"] == "activity"]
    assert areas == ["Shoulder, left"]


@pytest.mark.parametrize("state", ["pending", "performed", "removed"])
def test_migration_splits_existing_areas_and_preserves_row_state(configured, state):
    settings, factory, service = configured
    workout = service.start()
    therapy = next(row for row in workout["sets"] if row["type"] == "activity")
    alembic_config = Config(str(ROOT / "alembic.ini"))
    alembic_config.attributes["database_path"] = settings.database_path
    command.downgrade(alembic_config, "b7d52ac918f3")
    with factory.begin() as db:
        db.execute(
            text("UPDATE workout_sessions SET therapy_areas = :areas WHERE id = :id"),
            {"areas": "Ankle, elbow", "id": workout["id"]},
        )
        db.execute(
            text("UPDATE workout_sets SET state = :state WHERE id = :id"),
            {"state": state, "id": therapy["id"]},
        )
    migrate(settings)
    migrated = service.get(workout["id"])
    areas = [row for row in migrated["sets"] if row["type"] == "activity"]
    assert [row["activity_area"] for row in areas] == ["Ankle", "elbow"]
    assert [row["state"] for row in areas] == [state, state]
    assert areas[0]["id"] == therapy["id"]
    assert len({row["position"] for row in migrated["sets"]}) == len(migrated["sets"])
    migrate(settings)
    assert len(service.get(workout["id"])["sets"]) == len(migrated["sets"])
