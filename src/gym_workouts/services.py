from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, text, update
from sqlalchemy.orm import object_session

from gym_workouts.contracts import SessionCommand, format_weight
from gym_workouts.importer import checksum
from gym_workouts.models import ImportBatch, SourceRecord, VaultWrite, WorkoutSession, WorkoutSet
from gym_workouts.repositories import WorkoutRepository
from gym_workouts.vault import publish_note


class ConflictError(ValueError):
    pass


class WorkoutService:
    def __init__(self, factory, settings):
        self.factory = factory
        self.settings = settings

    def today(self):
        return datetime.now(ZoneInfo(self.settings.timezone)).date().isoformat()

    def state(self):
        with self.factory() as db:
            repo = WorkoutRepository(db)
            last = repo.latest_completed()
            active = repo.active()
            visible = active or repo.latest_completed(on_date=self.today())
            review = list(
                db.scalars(select(WorkoutSession).where(WorkoutSession.status == "review"))
            )
            return {
                "today": self.today(),
                "suggested": "B" if last and last.routine == "A" else "A",
                "last": {"routine": last.routine, "date": last.session_date} if last else None,
                "session": session_view(visible) if visible else None,
                "review": [
                    {"id": w.id, "date": w.session_date, "routine": w.routine} for w in review
                ],
                "ready": bool(repo.template("A") and repo.template("B")),
            }

    def get(self, session_id):
        with self.factory() as db:
            return session_view(WorkoutRepository(db).get(session_id))

    def start(self, routine=None):
        with self.factory() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            repo = WorkoutRepository(db)
            active = repo.active()
            if active:
                return session_view(active)
            last = repo.latest_completed()
            chosen = routine or ("B" if last and last.routine == "A" else "A")
            if chosen not in ("A", "B"):
                raise ValueError("Choose Workout A or B")
            completed_today = repo.latest_completed(routine=chosen, on_date=self.today())
            if completed_today:
                return session_view(completed_today)
            template = repo.template(chosen)
            if not template:
                raise ValueError("Import your workout templates first: uv run gym-init")
            prior = repo.latest_completed(routine=chosen)
            by_key = (
                {r.template_key: r for r in prior.rows if r.state == "performed"} if prior else {}
            )
            # Legacy notes retain recorded set order even when planned identity is unknown.
            legacy_order = (
                {
                    (r.exercise_id, r.occurrence): r
                    for r in prior.rows
                    if r.state == "performed" and r.template_key is None
                }
                if prior
                else {}
            )
            workout = WorkoutSession(
                id=str(uuid4()),
                routine=chosen,
                session_date=self.today(),
                created_at=datetime.now(UTC).isoformat(),
                status="draft",
                notes="",
            )
            db.add(workout)
            db.flush()
            for planned in template:
                old = by_key.get(planned.id) or legacy_order.get(
                    (planned.exercise_id, planned.occurrence)
                )
                workout.rows.append(
                    WorkoutSet(
                        id=str(uuid4()),
                        exercise_id=planned.exercise_id,
                        template_key=planned.id,
                        position=planned.position,
                        occurrence=planned.occurrence,
                        weight=old.weight if old else planned.weight,
                        reps=old.reps if old else planned.reps,
                        state="pending",
                        default_weight=old.weight if old else planned.weight,
                        default_reps=old.reps if old else planned.reps,
                        default_source=(
                            f"Last {chosen} · {prior.session_date}"
                            + (" (recorded order)" if old and old.template_key is None else "")
                        )
                        if old
                        else "Template",
                    )
                )
            db.commit()
            return session_view(repo.get(workout.id))

    def command(self, session_id: str, command: SessionCommand):
        retry = False
        with self.factory.begin() as db:
            repo = WorkoutRepository(db)
            workout = repo.get(session_id)
            if workout.status == "completed" and command.action in ("finish", "retry"):
                return session_view(workout)
            if command.action == "retry":
                if workout.status != "finalizing":
                    raise ValueError("Only an unfinished vault save can be retried")
                retry = True
            else:
                if workout.status != "draft":
                    raise ConflictError("This workout is no longer editable. Reload the page.")
                claimed = db.execute(
                    update(WorkoutSession)
                    .where(
                        WorkoutSession.id == session_id, WorkoutSession.revision == command.revision
                    )
                    .values(revision=command.revision + 1)
                    .execution_options(synchronize_session=False)
                )
                if claimed.rowcount != 1:
                    raise ConflictError("A newer edit exists. Reload before changing this workout.")
                workout.revision = command.revision + 1
                if command.action != "discard":
                    self._apply_edits(workout, command)
                if command.action.startswith(("remove:", "restore:")):
                    action, exercise_id = command.action.split(":", 1)
                    matching = [r for r in workout.rows if r.exercise_id == exercise_id]
                    if not matching:
                        raise ValueError("Exercise is not in this session")
                    for row in matching:
                        if action == "remove" and row.state != "removed":
                            row.previous_state, row.state = row.state, "removed"
                        elif action == "restore" and row.state == "removed":
                            row.state = row.previous_state or "pending"
                            row.previous_state = None
                elif command.action == "mark-all":
                    for row in workout.rows:
                        if row.state == "pending":
                            row.state = "performed"
                elif command.action == "discard":
                    workout.status = "discarded"
                elif command.action == "finish":
                    if any(r.state in ("pending", "unknown") for r in workout.rows):
                        raise ValueError(
                            "Mark every remaining set Done or Skipped before finishing."
                        )
                    if not any(r.state == "performed" for r in workout.rows):
                        raise ValueError("Complete at least one set or activity before finishing.")
                    workout.status = "finalizing"
                    workout.completed_at = datetime.now(UTC).isoformat()
                    content = serialize_note(workout)
                    db.add(
                        VaultWrite(
                            session_id=workout.id,
                            target_name=f"{workout.session_date} Workout {workout.routine}.md",
                            content=content,
                            checksum=checksum(content),
                            status="pending",
                        )
                    )
                    retry = True
                elif command.action != "save":
                    raise ValueError("Unknown session action")
        if retry:
            self.retry_write(session_id)
        return self.get(session_id)

    def _apply_edits(self, workout, command):
        submitted = {edit.id: edit for edit in command.sets}
        if len(submitted) != len(command.sets) or set(submitted) != {r.id for r in workout.rows}:
            raise ValueError("Submit exactly the sets belonging to this workout")
        for row in workout.rows:
            edit = submitted[row.id]
            if row.state == "removed":
                continue
            if edit.state not in ("pending", "performed", "skipped"):
                raise ValueError("Use the exercise removal action to remove sets")
            if row.exercise.measurement_type == "weight_reps":
                if edit.weight is None or edit.reps is None:
                    raise ValueError("Every numeric set needs weight and reps")
                row.weight, row.reps = edit.weight, edit.reps
            elif edit.weight is not None or edit.reps is not None:
                raise ValueError("Physical therapy does not have a weight or reps")
            row.state = edit.state
        workout.notes = command.notes

    def retry_write(self, session_id):
        with self.factory() as db:
            write = db.get(VaultWrite, session_id)
            if write is None or write.status == "saved":
                return
            target_name, content = write.target_name, write.content
        error = None
        try:
            publish_note(self.settings.workout_dir, target_name, content)
        except OSError as exc:
            error = str(exc)
        with self.factory() as db:
            # Serialize acknowledgements if two tabs or restart recovery retry together.
            db.execute(text("BEGIN IMMEDIATE"))
            write = db.get(VaultWrite, session_id)
            if write.status == "saved":
                return
            write.attempts += 1
            write.error = error
            write.status = "failed" if error else "saved"
            if error is None:
                workout = WorkoutRepository(db).get(session_id)
                workout.status = "completed"
                workout.completed_at = workout.completed_at or datetime.now(UTC).isoformat()
                workout.source_path = target_name
                batch = ImportBatch(
                    id=str(uuid4()),
                    imported_at=workout.completed_at,
                    report=json.dumps({"exported_session": session_id}),
                )
                db.add(batch)
                db.flush()
                if not db.get(SourceRecord, target_name):
                    db.add(
                        SourceRecord(
                            path=target_name,
                            checksum=checksum(content),
                            original_text=content,
                            issues="[]",
                            batch_id=batch.id,
                        )
                    )
            db.commit()

    def recover_writes(self):
        with self.factory() as db:
            pending = list(
                db.scalars(select(VaultWrite.session_id).where(VaultWrite.status != "saved"))
            )
        for session_id in pending:
            self.retry_write(session_id)

    def approve_import(self, session_id):
        with self.factory.begin() as db:
            workout = WorkoutRepository(db).get(session_id)
            if workout.status != "review":
                raise ValueError("This note does not need completion review")
            workout.status = "completed"


def session_view(workout):
    if workout is None:
        return None
    write = object_session(workout).get(VaultWrite, workout.id)
    return {
        "id": workout.id,
        "routine": workout.routine,
        "date": workout.session_date,
        "status": workout.status,
        "revision": workout.revision,
        "notes": workout.notes,
        "error": write.error if write else None,
        "vault_saved": bool(write and write.status == "saved"),
        "source_path": workout.source_path,
        "sets": [
            {
                "id": row.id,
                "exercise_id": row.exercise_id,
                "name": row.exercise.name,
                "type": row.exercise.measurement_type,
                "template_key": row.template_key,
                "position": row.position,
                "occurrence": row.occurrence,
                "weight": format_weight(row.weight) if row.weight is not None else None,
                "reps": row.reps,
                "state": row.state,
                "previous_state": row.previous_state,
                "default_weight": format_weight(row.default_weight),
                "default_reps": row.default_reps,
                "default_source": row.default_source,
            }
            for row in workout.rows
        ],
    }


def serialize_note(workout):
    view = session_view(workout)
    metadata = {
        "gym_workouts_version": 1,
        "session_id": workout.id,
        "status": "completed",
        "workout": workout.routine,
        "session_date": workout.session_date,
        "completed_at": workout.completed_at,
        "weight_unit": "lb",
        "notes": workout.notes,
        "gym_sets": [
            {
                k: row[k]
                for k in (
                    "name",
                    "position",
                    "occurrence",
                    "weight",
                    "reps",
                    "state",
                    "template_key",
                    "previous_state",
                )
            }
            for row in view["sets"]
        ],
    }
    # The existing Templater parses numeric prefixes on every line, including YAML.
    # Encode spaces in the notes scalar so it cannot masquerade as a set.
    encoded_notes = json.dumps(workout.notes).replace(" ", r"\u0020")
    header = "---\n" + "\n".join(
        f"{key}: {encoded_notes if key == 'notes' else json.dumps(value)}"
        for key, value in metadata.items()
    )
    lines = [header, "---", f"# {workout.session_date} Workout {workout.routine}", ""]
    for row in view["sets"]:
        if row["state"] == "performed":
            lines.append(
                row["name"]
                if row["type"] == "activity"
                else f"{row['name']} {row['weight']} {row['reps']}"
            )
    if workout.notes:
        lines.extend(
            [
                "",
                "## Notes",
                *(f"> {line} <!-- session note -->" for line in workout.notes.splitlines()),
            ]
        )
    return "\n".join(lines) + "\n"
