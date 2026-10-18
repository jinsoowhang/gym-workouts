from __future__ import annotations

import json
from copy import copy
from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, text, update
from sqlalchemy.orm import object_session

from gym_workouts.contracts import SessionCommand, format_weight, split_therapy_areas
from gym_workouts.importer import checksum
from gym_workouts.models import ImportBatch, SourceRecord, VaultWrite, WorkoutSession, WorkoutSet
from gym_workouts.repositories import WorkoutRepository
from gym_workouts.users import owner_user_id
from gym_workouts.vault import publish_note


class ConflictError(ValueError):
    pass


class WorkoutService:
    def __init__(self, factory, settings):
        self.factory = factory
        self.settings = settings
        self.vault_owner_id = owner_user_id(factory, settings.allowed_email)
        self.user_id = self.vault_owner_id

    def for_user(self, user_id):
        if not user_id:
            raise ValueError("A workout owner is required")
        scoped = copy(self)
        scoped.user_id = user_id
        return scoped

    def today(self):
        return datetime.now(ZoneInfo(self.settings.timezone)).date().isoformat()

    def state(self):
        with self.factory() as db:
            repo = WorkoutRepository(db, self.user_id)
            last = repo.latest_completed()
            active = repo.active()
            visible = active or repo.latest_completed(on_date=self.today())
            review = list(
                db.scalars(
                    select(WorkoutSession).where(
                        WorkoutSession.status == "review", WorkoutSession.user_id == self.user_id
                    )
                )
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
            return session_view(WorkoutRepository(db, self.user_id).get(session_id))

    def start(self, routine=None):
        with self.factory() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            repo = WorkoutRepository(db, self.user_id)
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
            areas = [r.activity_area for r in last.rows if r.activity_area] if last else []
            if not areas and self.user_id == self.vault_owner_id:
                areas = split_therapy_areas(self.settings.therapy_areas)
            workout = WorkoutSession(
                id=str(uuid4()),
                user_id=self.user_id,
                routine=chosen,
                session_date=self.today(),
                created_at=datetime.now(UTC).isoformat(),
                status="draft",
                notes="",
                therapy_areas=", ".join(areas),
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
                        exercise=planned.exercise,
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
            self._set_therapy_areas(workout, areas)
            db.commit()
            return session_view(repo.get(workout.id))

    def command(self, session_id: str, command: SessionCommand):
        retry = False
        with self.factory.begin() as db:
            repo = WorkoutRepository(db, self.user_id)
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
                        WorkoutSession.id == session_id,
                        WorkoutSession.user_id == self.user_id,
                        WorkoutSession.revision == command.revision,
                    )
                    .values(revision=command.revision + 1)
                    .execution_options(synchronize_session=False)
                )
                if claimed.rowcount != 1:
                    raise ConflictError("A newer edit exists. Reload before changing this workout.")
                workout.revision = command.revision + 1
                if command.action not in ("discard", "cancel"):
                    self._apply_edits(workout, command)
                if command.action.startswith(
                    ("remove:", "restore:", "remove-set:", "restore-set:")
                ):
                    action, target_id = command.action.split(":", 1)
                    by_set = action.endswith("-set")
                    matching = [
                        r for r in workout.rows if (r.id if by_set else r.exercise_id) == target_id
                    ]
                    if not matching:
                        raise ValueError(
                            "Set is not in this session"
                            if by_set
                            else "Exercise is not in this session"
                        )
                    for row in matching:
                        if action.startswith("remove") and row.state != "removed":
                            row.previous_state, row.state = row.state, "removed"
                        elif action.startswith("restore") and row.state == "removed":
                            row.state = row.previous_state or "pending"
                            row.previous_state = None
                elif command.action.startswith("add-set:"):
                    self._append_row(workout, command.action.split(":", 1)[1])
                elif command.action == "mark-all":
                    for row in workout.rows:
                        if row.state == "pending":
                            row.state = "performed"
                elif command.action in ("discard", "cancel"):
                    workout.status = "discarded"
                elif command.action == "finish":
                    if self.user_id != self.vault_owner_id:
                        raise ValueError("Obsidian publication is available only to its owner")
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
                workout.therapy_areas = therapy_summary(workout)
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
                raise ValueError("Use a removal action to remove sets")
            if row.exercise.measurement_type == "weight_reps":
                if edit.weight is None or edit.reps is None:
                    raise ValueError("Every numeric set needs weight and reps")
                row.weight, row.reps = edit.weight, edit.reps
            elif edit.weight is not None or edit.reps is not None:
                raise ValueError("Physical therapy does not have a weight or reps")
            if edit.activity_area is not None:
                if row.exercise.measurement_type != "activity" and edit.activity_area:
                    raise ValueError("Only physical therapy rows have an area")
                row.activity_area = edit.activity_area.strip()
            row.state = edit.state
        workout.notes = command.notes
        if (
            command.therapy_areas is not None
            and not any(edit.activity_area is not None for edit in command.sets)
            and command.therapy_areas.strip() != therapy_summary(workout)
        ):
            self._set_therapy_areas(workout, split_therapy_areas(command.therapy_areas))

    def _append_row(self, workout, exercise_id, *, area="", state="pending"):
        matching = [row for row in workout.rows if row.exercise_id == exercise_id]
        if not matching:
            raise ValueError("Exercise is not in this session")
        source = next((row for row in reversed(matching) if row.state != "removed"), matching[-1])
        extra = WorkoutSet(
            id=str(uuid4()),
            exercise_id=exercise_id,
            exercise=source.exercise,
            template_key=None,
            position=max(row.position for row in workout.rows) + 1,
            occurrence=max(row.occurrence for row in matching) + 1,
            weight=source.weight,
            reps=source.reps,
            state=state,
            activity_area=area,
            previous_state=source.previous_state if state == "removed" else None,
            default_weight=source.weight,
            default_reps=source.reps,
            default_source="Added this session",
        )
        workout.rows.append(extra)
        return extra

    def _set_therapy_areas(self, workout, areas):
        rows = [row for row in workout.rows if row.exercise.measurement_type == "activity"]
        if not rows:
            return
        areas = areas or [""]
        for index, area in enumerate(areas):
            if index < len(rows):
                rows[index].activity_area = area
            else:
                self._append_row(workout, rows[0].exercise_id, area=area, state=rows[0].state)
        for row in rows[len(areas) :]:
            if row.state != "removed":
                row.previous_state, row.state = row.state, "removed"

    def retry_write(self, session_id):
        with self.factory() as db:
            WorkoutRepository(db, self.user_id).get(session_id)
            if self.user_id != self.vault_owner_id:
                raise ValueError("Obsidian publication is available only to its owner")
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
                workout = WorkoutRepository(db, self.user_id).get(session_id)
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
                db.scalars(
                    select(VaultWrite.session_id)
                    .join(WorkoutSession, WorkoutSession.id == VaultWrite.session_id)
                    .where(VaultWrite.status != "saved", WorkoutSession.user_id == self.user_id)
                )
            )
        for session_id in pending:
            self.retry_write(session_id)

    def approve_import(self, session_id):
        with self.factory.begin() as db:
            workout = WorkoutRepository(db, self.user_id).get(session_id)
            if workout.status != "review":
                raise ValueError("This note does not need completion review")
            workout.status = "completed"


def therapy_summary(workout):
    return ", ".join(
        row.activity_area for row in workout.rows if row.activity_area and row.state != "removed"
    )


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
        "therapy_areas": therapy_summary(workout),
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
                "activity_area": row.activity_area,
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
        "therapy_areas": view["therapy_areas"],
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
                    "activity_area",
                )
            }
            for row in view["sets"]
        ],
    }
    # The existing Templater parses numeric prefixes on every line, including YAML.
    # Encode spaces in free text so it cannot masquerade as a set.
    header = "---\n" + "\n".join(
        f"{key}: "
        + (
            json.dumps(value, separators=(",", ":")).replace(" ", r"\u0020")
            if key in {"notes", "therapy_areas", "gym_sets"}
            else json.dumps(value)
        )
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
    areas = [
        row["activity_area"]
        for row in view["sets"]
        if row["state"] == "performed" and row["activity_area"]
    ]
    if areas:
        lines.extend(
            [
                "",
                "## Physical Therapy",
                *(f"> Area: {area} <!-- therapy area -->" for area in areas),
            ]
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
