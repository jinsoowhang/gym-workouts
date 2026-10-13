from decimal import Decimal

import pytest
from conftest import edits, form_values
from sqlalchemy import update

from gym_workouts.contracts import SessionCommand
from gym_workouts.dashboard import dashboard_data, exercise_chart
from gym_workouts.models import VaultWrite, WorkoutSession
from gym_workouts.services import ConflictError


def test_dashboard_uses_completed_performed_numeric_sets(configured):
    _settings, factory, service = configured
    data = dashboard_data(factory, service.today())
    assert (data["session_count"], data["training_days"], data["set_count"]) == (2, 2, 6)
    assert (data["routine_a"], data["routine_b"], data["volume_display"]) == (1, 1, "1,050")
    assert data["selected_name"] == "Bench Press"
    assert (data["latest"], data["best"], data["change"]) == ("25", "25", None)
    assert data["chart"]["points"][0]["top_reps"] == 6
    assert sum(week["count"] for week in data["weeks"]) == 2
    draft = service.start()
    assert dashboard_data(factory, service.today())["volume_display"] == "1,050"
    service.command(draft["id"], SessionCommand(revision=draft["revision"], action="cancel"))
    assert dashboard_data(factory, service.today())["session_count"] == 2


def test_dashboard_metrics_pair_weight_reps_and_exclude_removed_and_skipped(configured):
    _settings, factory, service = configured
    workout = service.start()
    front = next(row for row in workout["sets"] if row["name"] == "front raise")
    removed = service.command(
        workout["id"], SessionCommand(**edits(workout, f"remove-set:{front['id']}"))
    )
    payload = edits(removed, "finish")
    for row in payload["sets"]:
        source = next(item for item in removed["sets"] if item["id"] == row["id"])
        if row["state"] != "removed":
            row["state"] = "skipped"
        if source["name"] == "deadlift":
            row.update(weight="50", reps=8, state="performed")
        elif source["name"] == "bench press" and source["occurrence"] == 1:
            row.update(weight="30", reps=6, state="performed")
        elif source["name"] == "bench press":
            row.update(weight="100", reps=99)
        elif source["name"] == "leg raise":
            row.update(reps=15, state="performed")
        elif source["type"] == "activity":
            row["state"] = "performed"
    service.command(workout["id"], SessionCommand(**payload))
    data = dashboard_data(factory, service.today())
    assert (data["session_count"], data["set_count"], data["volume_display"]) == (3, 9, "1,630")
    assert (data["latest"], data["change"]) == ("30", "+5")
    assert data["chart"]["points"][-1]["top_display"] == "30 lb × 6"
    volume = dashboard_data(factory, service.today(), metric="volume")
    assert (volume["latest"], volume["change"]) == ("180", "+30")
    reps = dashboard_data(factory, service.today(), metric="reps")
    assert (reps["latest"], reps["change"]) == ("6", "0")
    bodyweight = next(item["id"] for item in data["exercises"] if item["name"] == "Leg Raise")
    zero = dashboard_data(factory, service.today(), exercise_id=bodyweight)
    assert zero["latest"] == "0"
    assert zero["chart"]["points"][0]["y"] == 226
    assert (
        dashboard_data(factory, service.today(), exercise_id=bodyweight, metric="reps")["latest"]
        == "15"
    )


def test_dashboard_date_range_is_inclusive_and_options_survive_empty_ranges(configured):
    _settings, factory, _service = configured
    data = dashboard_data(factory, "2026-11-08", days=30)
    assert data["session_count"] == 1 and data["volume_display"] == "504.5"
    assert data["chart"] is not None and data["exercises"]
    assert sum(week["count"] for week in data["weeks"]) == 1
    assert dashboard_data(factory, "2026-11-08", days=0)["session_count"] == 2
    empty = dashboard_data(factory, "2026-12-01", days=30)
    assert empty["session_count"] == 0 and empty["chart"] is None and empty["exercises"]


def test_dashboard_empty_state_and_review_notice(client, configured):
    _settings, factory, _service = configured
    with factory.begin() as db:
        db.execute(update(WorkoutSession).values(status="review"))
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "No completed workouts in this range" in response.text
    assert "2 imported workouts in this range await completion review" in response.text
    data = dashboard_data(factory, "2026-10-11")
    assert data["set_count"] == 0 and data["volume_display"] == "0"
    assert data["chart"] is None and not data["summaries"]


@pytest.mark.parametrize("query", ["days=17", "metric=unknown", "exercise=unknown"])
def test_dashboard_rejects_invalid_filters(client, query):
    assert client.get(f"/dashboard?{query}").status_code == 422


def test_dashboard_page_navigation_and_metric_filters(client, configured):
    _settings, factory, service = configured
    exercise = dashboard_data(factory, service.today())["selected_id"]
    response = client.get(f"/dashboard?days=0&exercise={exercise}&metric=volume")
    assert response.status_code == 200
    assert 'href="/dashboard" aria-current="page"' in response.text
    assert "Bench Press: Load volume over time" in response.text
    assert "150 lb × reps" in response.text
    assert "Content-Security-Policy" in response.headers


def test_cancel_bypasses_invalid_edits_preserves_history_and_can_restart(client, configured):
    settings, factory, service = configured
    workout = client.post("/api/v1/sessions", json={}).json()
    values = form_values(workout, "cancel")
    values[f"weight_{workout['sets'][0]['id']}"] = "invalid"
    values["notes"] = "n" * 10001
    values["therapy_areas"] = "Ankle\nElbow"
    response = client.post(
        f"/sessions/{workout['id']}/command", data=values, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200 and "Workout cancelled" in response.text
    assert service.get(workout["id"])["status"] == "discarded"
    assert service.state()["session"] is None and service.state()["suggested"] == "B"
    assert not (settings.workout_dir / "2026-10-11 Workout B.md").exists()
    with factory() as db:
        assert db.get(VaultWrite, workout["id"]) is None
    assert workout["id"] not in client.get("/history").text
    next_workout = service.start()
    assert next_workout["id"] != workout["id"] and next_workout["routine"] == "B"


def test_stale_cancel_and_completed_cancel_are_rejected(configured):
    settings, _factory, service = configured
    workout = service.start()
    saved = service.command(workout["id"], SessionCommand(**edits(workout, notes="Keep me")))
    with pytest.raises(ConflictError):
        service.command(
            workout["id"], SessionCommand(revision=workout["revision"], action="cancel")
        )
    assert service.get(workout["id"])["status"] == "draft"
    payload = edits(saved, "finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    completed = service.command(workout["id"], SessionCommand(**payload))
    before = (settings.workout_dir / "2026-10-11 Workout B.md").read_bytes()
    with pytest.raises(ConflictError):
        service.command(
            workout["id"], SessionCommand(revision=completed["revision"], action="cancel")
        )
    assert (settings.workout_dir / "2026-10-11 Workout B.md").read_bytes() == before
    assert dashboard_data(_factory, service.today())["session_count"] == 3


def test_dashboard_keeps_decimal_weight_precision(configured):
    _settings, factory, service = configured
    workout = service.start()
    payload = edits(workout, "finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    payload["sets"][1]["weight"] = "45.125"
    payload["sets"][1]["reps"] = 7
    service.command(workout["id"], SessionCommand(**payload))
    data = dashboard_data(factory, service.today())
    assert data["chart"]["points"][-1]["weight"] == Decimal("45.125")
    assert data["chart"]["points"][-1]["top_reps"] == 7
    assert data["latest"] == "45.125"


def test_chart_keeps_small_nonzero_weights_visible():
    chart = exercise_chart([{"date": "2026-10-11", "weight": Decimal("0.0001")}], "weight")
    assert [tick["label"] for tick in chart["ticks"]] == ["0.0001", "0.00005", "0"]
    assert chart["points"][0]["y"] == 20
