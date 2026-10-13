import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal

import pytest
from conftest import edits, form_values
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from gym_workouts.app import create_app
from gym_workouts.cli import migrate
from gym_workouts.config import Settings
from gym_workouts.contracts import SessionCommand, parse_note
from gym_workouts.database import create_database
from gym_workouts.importer import import_workouts
from gym_workouts.models import SourceRecord, VaultWrite, WorkoutSession
from gym_workouts.services import ConflictError, WorkoutService
from gym_workouts.vault import publish_note


def test_latest_defaults_are_scoped_and_missing_sets_do_not_shift(configured):
    _settings, _factory, service = configured
    assert service.state()["suggested"] == "B"
    b = service.start()
    assert b["routine"] == "B"
    assert b["sets"][0]["weight"] == "47.5"
    bench = [r for r in b["sets"] if r["name"] == "bench press"]
    assert [r["weight"] for r in bench] == ["25", "40"]
    assert "recorded order" in bench[0]["default_source"]
    assert bench[1]["default_source"] == "Template"
    front = next(r for r in b["sets"] if r["name"] == "front raise")
    assert (front["weight"], front["reps"]) == ("9", 7)
    assert {"leg raise", "left oblique raise", "right oblique raise", "physical therapy"} <= {
        r["name"] for r in b["sets"]
    }
    assert service.start("A")["id"] == b["id"]
    assert service.state()["suggested"] == "B"


def test_session_edit_remove_undo_and_stale_revision(configured):
    _settings, _factory, service = configured
    a = service.start("A")
    assert [r["weight"] for r in a["sets"][:2]] == ["27.5", "37.5"]
    payload = edits(a)
    payload["sets"][0].update(weight="23.125", reps=3, state="performed")
    saved = service.command(a["id"], SessionCommand(**payload))
    assert saved["sets"][0]["weight"] == "23.125"
    assert saved["sets"][0]["default_weight"] == "27.5"
    with pytest.raises(ConflictError):
        service.command(a["id"], SessionCommand(**payload))
    removed = service.command(
        a["id"], SessionCommand(**edits(saved, action=f"remove:{saved['sets'][0]['exercise_id']}"))
    )
    assert [r["state"] for r in removed["sets"][:2]] == ["removed", "removed"]
    restored = service.command(
        a["id"],
        SessionCommand(**edits(removed, action=f"restore:{saved['sets'][0]['exercise_id']}")),
    )
    assert restored["sets"][0]["state"] == "performed"
    assert restored["sets"][0]["weight"] == "23.125"
    assert service.state()["session"]["id"] == a["id"]


def test_single_set_removal_restores_values_and_rejects_foreign_ids(configured):
    _settings, _factory, service = configured
    workout = service.start("A")
    payload = edits(workout)
    payload["sets"][1].update(weight="32.125", reps=3, state="performed")
    saved = service.command(workout["id"], SessionCommand(**payload))
    row_id = saved["sets"][1]["id"]
    removal = edits(saved, action=f"remove-set:{row_id}")
    removed = service.command(workout["id"], SessionCommand(**removal))
    assert [r["state"] for r in removed["sets"][:2]] == ["pending", "removed"]
    with pytest.raises(ConflictError):
        service.command(workout["id"], SessionCommand(**removal))
    restored = service.command(
        workout["id"], SessionCommand(**edits(removed, action=f"restore-set:{row_id}"))
    )
    assert restored["sets"][1]["state"] == "performed"
    assert (restored["sets"][1]["weight"], restored["sets"][1]["reps"]) == ("32.125", 3)
    for action in ("remove-set:foreign-row", "restore-set:foreign-row"):
        with pytest.raises(ValueError, match="Set is not in this session"):
            service.command(workout["id"], SessionCommand(**edits(restored, action=action)))
    assert service.get(workout["id"])["revision"] == restored["revision"]


@pytest.mark.parametrize("configured", [4], indirect=True)
def test_form_finishes_three_of_four_sets_and_new_session_restores_plan(client, configured):
    settings, _factory, service = configured
    workout = client.post("/api/v1/sessions", json={}).json()
    bench = [row for row in workout["sets"] if row["name"] == "bench press"]
    values = form_values(workout, action=f"remove-set:{bench[-1]['id']}")
    response = client.post(f"/sessions/{workout['id']}/command", data=values)
    assert response.status_code == 200
    removed = client.get(f"/api/v1/sessions/{workout['id']}").json()
    assert [row["state"] for row in removed["sets"] if row["name"] == "bench press"] == [
        "pending",
        "pending",
        "pending",
        "removed",
    ]
    values = form_values(removed, action="finish")
    values[f"weight_{bench[2]['id']}"] = "35.125"
    response = client.post(f"/sessions/{workout['id']}/command", data=values)
    assert response.status_code == 200 and "Saved to Obsidian" in response.text
    parsed = parse_note((settings.workout_dir / "2026-10-11 Workout B.md").read_text())
    recorded = [row for row in parsed.rows if row.name == "bench press"]
    assert [row.state for row in recorded] == ["performed"] * 3 + ["removed"]
    assert recorded[2].weight == Decimal("35.125")
    service.today = lambda: "2026-10-12"
    fresh = service.start("B")
    bench = [row for row in fresh["sets"] if row["name"] == "bench press"]
    assert [row["state"] for row in bench] == ["pending"] * 4
    assert [row["weight"] for row in bench] == ["25", "40", "35.125", "40"]


def test_finish_is_idempotent_and_roundtrips_set_mapping(configured):
    settings, factory, service = configured
    a = service.start("A")
    removed = service.command(
        a["id"], SessionCommand(**edits(a, action=f"remove:{a['sets'][0]['exercise_id']}"))
    )
    payload = edits(removed, action="finish", notes="A synthetic test.\nNo source data.")
    for row in payload["sets"]:
        if row["state"] != "removed":
            row["state"] = "performed"
    completed = service.command(a["id"], SessionCommand(**payload))
    assert completed["status"] == "completed" and completed["vault_saved"]
    assert service.state()["suggested"] == "B"
    note = settings.workout_dir / "2026-10-11 Workout A.md"
    parsed = parse_note(note.read_text())
    assert parsed.metadata["weight_unit"] == "lb"
    assert parsed.rows[0].state == "removed"
    assert parsed.rows[0].template_key
    before = note.read_bytes()
    service.command(a["id"], SessionCommand(**payload))
    assert note.read_bytes() == before
    assert import_workouts(factory, settings.workout_dir)["imported"] == 0
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(WorkoutSession)) == 3
        assert db.get(VaultWrite, a["id"]).attempts == 1
    service.today = lambda: "2026-10-12"
    fresh = service.start("A")
    assert fresh["sets"][0]["state"] == "pending"
    assert fresh["sets"][0]["weight"] == "30"  # removed previously; template fallback


def test_therapy_areas_preserve_notes_roundtrip_and_carry_to_next_routine(configured, tmp_path):
    settings, _factory, service = configured
    workout = service.start()
    payload = edits(workout, notes="Keep this session note.", therapy_areas="Ankle, elbow")
    saved = service.command(workout["id"], SessionCommand(**payload))
    assert saved["therapy_areas"] == "Ankle, elbow"
    old_client = edits(saved)
    del old_client["therapy_areas"]
    saved = service.command(workout["id"], SessionCommand(**old_client))
    assert saved["therapy_areas"] == "Ankle, elbow"
    payload = edits(saved, action="finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    service.command(workout["id"], SessionCommand(**payload))
    content = (settings.workout_dir / "2026-10-11 Workout B.md").read_text()
    parsed = parse_note(content)
    assert parsed.metadata["therapy_areas"] == "Ankle, elbow"
    assert parsed.notes == "Keep this session note."
    assert "> Area: Ankle" in content and "> Area: elbow" in content
    assert not parsed.issues
    rebuilt = replace(settings, database_path=tmp_path / "rebuilt-therapy.sqlite3")
    migrate(rebuilt)
    engine, factory = create_database(rebuilt.database_path)
    try:
        assert not import_workouts(factory, rebuilt.workout_dir)["issues"]
        new_service = WorkoutService(factory, rebuilt)
        new_service.today = lambda: "2026-10-12"
        assert new_service.get(workout["id"])["therapy_areas"] == "Ankle, elbow"
        assert new_service.start("A")["therapy_areas"] == "Ankle, elbow"
    finally:
        engine.dispose()


@pytest.mark.parametrize("areas", ["a" * 501, "Ankle\nElbow", "Ankle\rElbow"])
def test_invalid_therapy_areas_are_rejected(configured, areas):
    _settings, _factory, service = configured
    workout = service.start()
    with pytest.raises(ValidationError):
        SessionCommand(**edits(workout, therapy_areas=areas))
    assert service.get(workout["id"])["therapy_areas"] == ""


def test_local_therapy_default_does_not_change_historical_sessions(configured):
    settings, factory, service = configured
    local_service = WorkoutService(factory, replace(settings, therapy_areas="Ankle, elbow"))
    local_service.today = service.today
    assert local_service.start()["therapy_areas"] == "Ankle, elbow"
    assert local_service.state()["last"]["date"] == "2026-10-10"
    with factory() as db:
        historical = db.scalars(select(WorkoutSession).where(WorkoutSession.status == "completed"))
        assert all(workout.therapy_areas == "" for workout in historical)


def test_failed_save_recovery_preserves_files_and_does_not_advance(configured):
    settings, factory, service = configured
    b = service.start()
    payload = edits(b, action="finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    collision = settings.workout_dir / "2026-10-11 Workout B.md"
    collision.write_text("An unrelated Obsidian note.\n")
    failed = service.command(b["id"], SessionCommand(**payload))
    assert failed["status"] == "finalizing" and "different" in failed["error"]
    assert collision.read_text() == "An unrelated Obsidian note.\n"
    assert service.state()["suggested"] == "B"
    collision.unlink()  # Only the synthetic temporary-vault collision is removed.
    recovered = WorkoutService(factory, settings)
    recovered.recover_writes()
    assert recovered.get(b["id"])["status"] == "completed"
    assert recovered.state()["suggested"] == "A"
    with factory() as db:
        assert db.get(VaultWrite, b["id"]).attempts == 2


def test_crash_after_file_publication_retries_without_duplicate(configured):
    settings, factory, service = configured
    workout = service.start()
    payload = edits(workout, action="finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    original = service.retry_write
    service.retry_write = lambda _id: None
    service.command(workout["id"], SessionCommand(**payload))
    with factory() as db:
        write = db.get(VaultWrite, workout["id"])
        publish_note(settings.workout_dir, write.target_name, write.content)
        before = (settings.workout_dir / write.target_name).read_bytes()
    service.retry_write = original
    service.recover_writes()
    assert service.get(workout["id"])["vault_saved"]
    assert (settings.workout_dir / "2026-10-11 Workout B.md").read_bytes() == before


@pytest.mark.parametrize("weight", ["-1", "NaN", "Infinity", "0.00001", "100000000"])
def test_invalid_weights_rejected_without_mutation(configured, weight):
    _settings, _factory, service = configured
    workout = service.start()
    payload = edits(workout)
    payload["sets"][0]["weight"] = weight
    with pytest.raises(ValidationError):
        SessionCommand(**payload)
    assert service.get(workout["id"])["revision"] == 0


def test_pending_finish_and_wrong_set_ids_roll_back(configured):
    _settings, _factory, service = configured
    workout = service.start()
    with pytest.raises(ValueError, match="Done or Skipped"):
        service.command(workout["id"], SessionCommand(**edits(workout, action="finish")))
    payload = edits(workout)
    payload["sets"][0]["id"] = "foreign-row"
    with pytest.raises(ValueError, match="exactly"):
        service.command(workout["id"], SessionCommand(**payload))
    assert service.get(workout["id"])["revision"] == 0


def test_import_preserves_unknown_notes_and_flags_new_notes(configured):
    settings, factory, _service = configured
    path = settings.workout_dir / "2026-10-12 Workout A.md"
    path.write_text("# Prefilled\n> Warning: not an exercise\nsquat 31.25 4\n+\nphysical therapy\n")
    report = import_workouts(factory, settings.workout_dir)
    assert report["review"] == [path.name]
    assert report["issues"]
    with factory() as db:
        assert db.get(SourceRecord, path.name).original_text == path.read_text()
    path.write_text(path.read_text() + "Changed manually\n")
    assert import_workouts(factory, settings.workout_dir)["conflicts"]


def test_concurrent_start_returns_one_active_session(configured):
    _settings, _factory, service = configured
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.start(), range(4)))
    assert len({result["id"] for result in results}) == 1


def test_populated_migration_is_repeatable(configured):
    settings, factory, service = configured
    session = service.start()
    migrate(settings)
    assert service.get(session["id"])["routine"] == "B"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(WorkoutSession)) == 3


def test_parser_decimal_zero_and_therapy():
    parsed = parse_note("# Invented\nstanding row 31.25 7\nleg raise 0 11\nphysical therapy\n")
    assert parsed.rows[0].weight == Decimal("31.25")
    assert parsed.rows[1].weight == 0
    assert parsed.rows[2].state == "unknown"


def test_finishing_an_older_draft_advances_from_that_completion(configured):
    _settings, factory, service = configured
    workout = service.start("B")
    with factory.begin() as db:
        db.get(WorkoutSession, workout["id"]).session_date = "2024-01-01"
    workout = service.get(workout["id"])
    payload = edits(workout, action="finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    service.command(workout["id"], SessionCommand(**payload))
    assert service.state()["suggested"] == "A"


def test_same_day_same_routine_reopens_existing_session(configured):
    _settings, _factory, service = configured
    service.today = lambda: "2026-10-10"
    reopened = service.start("A")
    assert reopened["status"] == "completed" and reopened["date"] == "2026-10-10"


def test_mark_all_preserves_skipped_and_removed_rows(configured):
    _settings, _factory, service = configured
    workout = service.start()
    payload = edits(workout)
    payload["sets"][0]["state"] = "skipped"
    saved = service.command(workout["id"], SessionCommand(**payload))
    removed = service.command(
        workout["id"],
        SessionCommand(**edits(saved, action=f"remove:{saved['sets'][-1]['exercise_id']}")),
    )
    all_done = service.command(workout["id"], SessionCommand(**edits(removed, action="mark-all")))
    assert all_done["sets"][0]["state"] == "skipped"
    assert all_done["sets"][-1]["state"] == "removed"
    assert all_done["sets"][1]["state"] == "performed"


def test_completed_note_body_must_match_metadata(configured):
    settings, _factory, service = configured
    workout = service.start()
    payload = edits(workout, action="finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    service.command(workout["id"], SessionCommand(**payload))
    content = (settings.workout_dir / "2026-10-11 Workout B.md").read_text()
    with pytest.raises(ValueError, match="external edits"):
        parse_note(content.replace("deadlift 47.5 7", "deadlift 11.5 7"))


def test_vault_filename_and_symlink_boundaries(configured, tmp_path):
    settings, _factory, _service = configured
    with pytest.raises(ValueError):
        publish_note(settings.workout_dir, "../outside.md", "Test")
    outside = tmp_path / "outside.md"
    outside.write_text("Keep this file")
    target = settings.workout_dir / "2026-10-11 Workout B.md"
    target.symlink_to(outside)
    with pytest.raises(OSError, match="symlink"):
        publish_note(settings.workout_dir, target.name, "Test")
    assert outside.read_text() == "Keep this file"


def test_note_rebuild_preserves_same_day_completion_order(configured, tmp_path):
    settings, _factory, service = configured
    for routine in ("A", "B"):
        workout = service.start(routine)
        payload = edits(workout, action="finish")
        for row in payload["sets"]:
            row["state"] = "performed"
        service.command(workout["id"], SessionCommand(**payload))
    rebuilt = Settings(
        tmp_path / "rebuilt.sqlite3", settings.workout_dir, tmp_path / "rebuilt.duckdb"
    )
    migrate(rebuilt)
    engine, factory = create_database(rebuilt.database_path)
    try:
        report = import_workouts(factory, rebuilt.workout_dir)
        assert report["imported"] == 4 and not report["issues"]
        new_service = WorkoutService(factory, rebuilt)
        assert new_service.state()["suggested"] == "A"
    finally:
        engine.dispose()


def test_legacy_templater_does_not_parse_numeric_notes_as_sets(configured):
    settings, _factory, service = configured
    workout = service.start()
    notes = "A reminder ending in 12 3\nAnother reminder ending in 4 9"
    payload = edits(workout, action="finish", notes=notes, therapy_areas="Ankle 12 3")
    for row in payload["sets"]:
        row["state"] = "performed"
    service.command(workout["id"], SessionCommand(**payload))
    content = (settings.workout_dir / "2026-10-11 Workout B.md").read_text()
    assert parse_note(content).notes == notes
    assert parse_note(content).metadata["therapy_areas"] == "Ankle 12 3"
    legacy_rows = []
    # Independent compatibility check for the existing permissive JS parseFloat/parseInt reader.
    for line in content.splitlines():
        tokens = line.split()
        if len(tokens) < 3:
            continue
        weight = re.match(r"^[+-]?\d+(?:\.\d+)?", tokens[-2])
        reps = re.match(r"^[+-]?\d+", tokens[-1])
        if weight and reps:
            legacy_rows.append(" ".join(tokens[:-2]))
    assert legacy_rows == [r["name"] for r in workout["sets"] if r["type"] == "weight_reps"]


def test_api_cannot_mutate_completed_results(client):
    workout = client.post("/api/v1/sessions", json={}).json()
    payload = edits(workout, action="finish")
    for row in payload["sets"]:
        row["state"] = "performed"
    completed = client.post(f"/api/v1/sessions/{workout['id']}/command", json=payload).json()
    assert completed["status"] == "completed"
    payload = edits(completed)
    payload["sets"][0]["weight"] = "11"
    assert client.post(f"/api/v1/sessions/{workout['id']}/command", json=payload).status_code == 409


def test_api_html_save_and_local_boundary(client):
    assert client.get("/").status_code == 200
    workout = client.post("/api/v1/sessions", json={}).json()
    values = form_values(workout)
    first_id = workout["sets"][0]["id"]
    values[f"weight_{first_id}"] = "41.25"
    response = client.post(
        f"/sessions/{workout['id']}/command", data=values, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200 and 'value="1"' in response.text
    assert client.get(f"/api/v1/sessions/{workout['id']}").json()["sets"][0]["weight"] == "41.25"
    stale = client.post(f"/api/v1/sessions/{workout['id']}/command", json=edits(workout))
    assert stale.status_code == 409
    assert (
        client.post(
            "/api/v1/sessions", json={}, headers={"Origin": "https://other.example"}
        ).status_code
        == 403
    )
    assert client.get("/", headers={"Host": "other.example"}).status_code == 400
    assert client.get("/api/v1/sessions/missing").status_code == 404


def test_hosted_https_requests_keep_host_and_origin_boundaries(configured):
    settings, _factory, _service = configured
    app = create_app(replace(settings, allowed_hosts=("gym.example.com", "127.0.0.1")))
    with TestClient(app, base_url="https://gym.example.com") as hosted:
        assert hosted.get("/").status_code == 200
        assert hosted.get("/", headers={"Host": "other.example.com"}).status_code == 400
        assert (
            hosted.post(
                "/api/v1/sessions", json={}, headers={"Origin": "https://other.example.com"}
            ).status_code
            == 403
        )
        assert (
            hosted.post(
                "/api/v1/sessions", json={}, headers={"Origin": "http://gym.example.com"}
            ).status_code
            == 403
        )
        assert (
            hosted.post(
                "/api/v1/sessions", json={}, headers={"Origin": "https://gym.example.com"}
            ).status_code
            == 200
        )


def test_unmarked_historical_import_requires_explicit_cutoff(configured):
    settings, factory, _service = configured
    path = settings.workout_dir / "2020-01-01 Workout A.md"
    path.write_text("squat 10 2\n")
    report = import_workouts(factory, settings.workout_dir)
    assert path.name in report["review"]
    with factory() as db:
        record = db.scalar(select(WorkoutSession).where(WorkoutSession.source_path == path.name))
        assert record.status == "review"

    confirmed = settings.workout_dir / "2020-01-02 Workout B.md"
    confirmed.write_text("deadlift 12 3\n")
    report = import_workouts(factory, settings.workout_dir, legacy_through="2020-01-02")
    assert confirmed.name not in report["review"]
    with factory() as db:
        record = db.scalar(
            select(WorkoutSession).where(WorkoutSession.source_path == confirmed.name)
        )
        assert record.status == "completed"
