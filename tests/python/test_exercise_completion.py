import pytest
from conftest import edits, form_values

from gym_workouts.app import exercise_groups
from gym_workouts.contracts import SessionCommand, parse_note
from gym_workouts.models import Exercise
from gym_workouts.services import ConflictError


@pytest.mark.parametrize("name", ["bench press", "physical therapy"])
def test_complete_exercise_saves_edits_and_preserves_removed_rows(client, configured, name):
    settings, _factory, service = configured
    workout = service.start()
    target = next(row for row in workout["sets"] if row["name"] == name)
    workout = service.command(
        workout["id"],
        SessionCommand(**edits(workout, action=f"add-set:{target['exercise_id']}")),
    )
    extra = workout["sets"][-1]
    workout = service.command(
        workout["id"], SessionCommand(**edits(workout, action=f"remove-set:{target['id']}"))
    )
    values = form_values(workout, f"complete:{target['exercise_id']}")
    values["notes"] = "Exercise finished"
    if name == "bench press":
        values[f"weight_{extra['id']}"] = "36.125"
        values[f"reps_{extra['id']}"] = "9"
    else:
        values[f"area_{extra['id']}"] = "Wrist"
    response = client.post(f"/sessions/{workout['id']}/command", data=values)
    assert response.status_code == 200
    assert response.headers["hx-retarget"] == "#workout"
    saved = service.get(workout["id"])
    assert saved["status"] == "draft" and saved["notes"] == "Exercise finished"
    assert not (settings.workout_dir / "2026-10-11 Workout B.md").exists()
    for row in saved["sets"]:
        assert row["state"] == (
            "removed"
            if row["id"] == target["id"]
            else "performed"
            if row["exercise_id"] == target["exercise_id"]
            else "pending"
        )
    assert saved["sets"][-1]["weight"] == ("36.125" if name == "bench press" else None)
    assert saved["sets"][-1]["activity_area"] == ("Wrist" if name == "physical therapy" else "")
    page = client.get(f"/workouts/{workout['id']}").text
    assert f'aria-label="Completed {name.title()}"' in page
    body_id = f"exercise-{workout['id']}-{target['exercise_id']}"
    assert f'id="{body_id}" hidden' in page
    # Autosave retains performed states, and Finish still publishes the whole workout.
    assert (
        client.post(f"/sessions/{workout['id']}/command", data=form_values(saved)).status_code
        == 200
    )
    saved = service.get(workout["id"])
    assert (
        client.post(
            f"/sessions/{workout['id']}/command", data=form_values(saved, "finish")
        ).status_code
        == 200
    )
    parsed = parse_note((settings.workout_dir / "2026-10-11 Workout B.md").read_text())
    assert next(row for row in parsed.rows if row.name == name).state == "removed"
    assert parsed.rows[-1].state == "performed"


def test_complete_combined_arms_card(client, configured):
    _settings, factory, service = configured
    workout = service.start()
    with factory.begin() as db:
        for old, new in (("deadlift", "skull crusher"), ("bench press", "bicep curl bar")):
            exercise_id = next(row["exercise_id"] for row in workout["sets"] if row["name"] == old)
            db.get(Exercise, exercise_id).name = new
    workout = service.get(workout["id"])
    arms = next(group for group in exercise_groups(workout["sets"]) if group["title"] == "Arms")
    ids = ",".join(exercise["id"] for exercise in arms["exercises"])
    assert f'value="complete:{ids}"' in client.get(f"/workouts/{workout['id']}").text
    saved = service.command(workout["id"], SessionCommand(**edits(workout, f"complete:{ids}")))
    groups = exercise_groups(saved["sets"])
    assert next(group for group in groups if group["title"] == "Arms")["completed"]
    assert not next(group for group in groups if group["title"] == "Physical Therapy")["completed"]


def test_complete_rejects_foreign_targets_stale_edits_and_invalid_values(client, configured):
    _settings, _factory, service = configured
    workout = service.start()
    row = workout["sets"][0]
    for target in ("foreign", f"{row['exercise_id']},foreign", ""):
        with pytest.raises(ValueError, match="Exercise is not in this session"):
            service.command(workout["id"], SessionCommand(**edits(workout, f"complete:{target}")))
        assert service.get(workout["id"]) == workout
    values = form_values(workout, f"complete:{row['exercise_id']}")
    values[f"weight_{row['id']}"] = "-1"
    response = client.post(f"/sessions/{workout['id']}/command", data=values)
    assert response.status_code == 422
    assert service.get(workout["id"]) == workout
    payload = SessionCommand(**edits(workout, f"complete:{row['exercise_id']}"))
    saved = service.command(workout["id"], payload)
    with pytest.raises(ConflictError):
        service.command(workout["id"], payload)
    assert service.get(workout["id"]) == saved
    removed = service.command(
        workout["id"],
        SessionCommand(**edits(saved, f"remove:{row['exercise_id']}")),
    )
    group = exercise_groups(removed["sets"])[0]
    assert not group["included"] and not group["completed"]
    restored = service.command(
        workout["id"],
        SessionCommand(**edits(removed, f"restore:{row['exercise_id']}")),
    )
    assert exercise_groups(restored["sets"])[0]["completed"]
    added = service.command(
        workout["id"],
        SessionCommand(**edits(restored, f"add-set:{row['exercise_id']}")),
    )
    assert not exercise_groups(added["sets"])[0]["completed"]
