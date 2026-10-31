from datetime import date, timedelta

import pytest
from sqlalchemy import select

from gym_workouts.models import WorkoutSession


@pytest.mark.parametrize(
    ("days", "heading"),
    [
        (1, "Consider a small increase"),
        (6, "Consider a small increase"),
        (7, "Maintain your weights"),
        (13, "Maintain your weights"),
        (14, "Consider starting lighter"),
        (30, "Consider starting lighter"),
    ],
)
def test_check_in_weight_guidance_boundaries(client, configured, days, heading):
    _settings, factory, service = configured
    today = date(2026, 10, 30)
    previous = (today - timedelta(days=days)).isoformat()
    client.app.state.service.today = lambda: today.isoformat()
    with factory.begin() as db:
        workout = db.scalar(select(WorkoutSession).where(WorkoutSession.routine == "B"))
        workout.session_date = previous
    started = client.post("/api/v1/sessions", json={"routine": "B"}).json()
    response = client.get(f"/workouts/{started['id']}")
    assert response.status_code == 200
    assert "Small steps.<br>Steady progress." in response.text
    assert f'<h3 id="weight-guidance-title">{heading}</h3>' in response.text
    assert f'Last Workout B: <time datetime="{previous}">{previous}</time>' in response.text
    assert f"{days} {'day' if days == 1 else 'days'} ago." in response.text
    assert started["sets"][0]["weight"] == "47.5"
    assert service.get(started["id"]) == started


def test_check_in_without_same_routine_history(client, configured):
    _settings, factory, _service = configured
    with factory.begin() as db:
        previous = db.scalar(select(WorkoutSession).where(WorkoutSession.routine == "B"))
        previous.status = "review"
    started = client.post("/api/v1/sessions", json={"routine": "B"}).json()
    response = client.get(f"/workouts/{started['id']}")
    assert '<h3 id="weight-guidance-title">Build your baseline</h3>' in response.text
    assert "No completed Workout B yet." in response.text
    assert 'class="guidance-history"' not in response.text


def test_check_in_ignores_unfinished_future_and_out_of_order_history(configured):
    _settings, factory, service = configured
    with factory.begin() as db:
        for index, (status, day) in enumerate(
            [
                ("draft", "2026-10-11"),
                ("finalizing", "2026-10-11"),
                ("discarded", "2026-10-11"),
                ("review", "2026-10-11"),
                ("completed", "2026-10-12"),
                ("completed", "2026-10-08"),
            ]
        ):
            db.add(
                WorkoutSession(
                    id=f"guidance-history-{index}",
                    user_id=service.user_id,
                    routine="B",
                    session_date=day,
                    created_at="2026-10-11T12:00:00+00:00",
                    completed_at="2026-10-11T12:00:00+00:00" if status == "completed" else None,
                    status=status,
                )
            )
    guidance = service.weight_guidance("B")
    assert guidance["previous_date"] == "2026-10-09"
    assert guidance["days_since"] == 2
    assert guidance["level"] == "increase"


def test_resumed_draft_guidance_uses_current_day_without_changing_results(client, configured):
    _settings, _factory, service = configured
    started = client.post("/api/v1/sessions", json={"routine": "B"}).json()
    for today, heading in [
        ("2026-10-11", "Consider a small increase"),
        ("2026-10-16", "Maintain your weights"),
        ("2026-10-23", "Consider starting lighter"),
    ]:
        client.app.state.service.today = lambda day=today: day
        response = client.get("/")
        assert f'<h3 id="weight-guidance-title">{heading}</h3>' in response.text
        assert service.get(started["id"]) == started


@pytest.mark.parametrize("status", ["completed", "finalizing"])
def test_finished_workouts_have_no_weight_guidance(client, configured, status):
    _settings, factory, _service = configured
    started = client.post("/api/v1/sessions", json={"routine": "B"}).json()
    with factory.begin() as db:
        db.get(WorkoutSession, started["id"]).status = status
    response = client.get(f"/workouts/{started['id']}")
    assert response.status_code == 200
    assert "Small steps.<br>Steady progress." in response.text
    assert 'class="weight-guidance"' not in response.text
