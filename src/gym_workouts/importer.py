from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select
from yaml import YAMLError

from gym_workouts.contracts import SESSION_FILE, ParsedRow, filename_date, parse_note
from gym_workouts.models import (
    Exercise,
    ImportBatch,
    RoutineSet,
    SourceRecord,
    WorkoutSession,
    WorkoutSet,
)


def identity(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"gym-workouts:{value}"))


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def ensure_exercise(db, name):
    exercise_id = identity(f"exercise:{name}")
    if not db.get(Exercise, exercise_id):
        db.add(
            Exercise(
                id=exercise_id,
                name=name,
                measurement_type="activity" if name == "physical therapy" else "weight_reps",
            )
        )
        db.flush()
    return exercise_id


def import_workouts(factory, workout_dir, legacy_through=None):
    if legacy_through is not None:
        date.fromisoformat(legacy_through)
    if not workout_dir.is_dir():
        raise ValueError(f"Workout directory unavailable: {workout_dir}")
    report = {"imported": 0, "unchanged": 0, "review": [], "conflicts": [], "issues": []}
    with factory.begin() as db:
        batch = ImportBatch(id=str(uuid4()), imported_at=datetime.now(UTC).isoformat(), report="{}")
        db.add(batch)
        db.flush()
        for routine in ("A", "B"):
            path = workout_dir / f"_workout-{routine.lower()}.md"
            if not path.resolve().is_relative_to(workout_dir.resolve()):
                raise ValueError("Canonical template resolves outside the workout directory")
            text = path.read_text(encoding="utf-8")
            parsed = parse_note(text)
            if parsed.issues or not parsed.rows:
                raise ValueError(f"Canonical template must contain valid sets: {path.name}")
            source = db.get(SourceRecord, path.name)
            if source and source.checksum != checksum(text):
                report["conflicts"].append(
                    f"Template changed: {path.name}; review before replacing"
                )
                continue
            if not source:
                if not any(row.name == "physical therapy" for row in parsed.rows):
                    parsed.rows.append(
                        ParsedRow("physical therapy", None, None, len(parsed.rows), 1, "pending")
                    )
                for row in parsed.rows:
                    key = f"{routine}:{row.name}:{row.occurrence}"
                    db.add(
                        RoutineSet(
                            id=key,
                            routine=routine,
                            position=row.position,
                            exercise_id=ensure_exercise(db, row.name),
                            occurrence=row.occurrence,
                            weight=row.weight,
                            reps=row.reps,
                        )
                    )
                db.add(
                    SourceRecord(
                        path=path.name,
                        checksum=checksum(text),
                        original_text=text,
                        issues="[]",
                        batch_id=batch.id,
                    )
                )
        db.flush()
        templates = list(db.scalars(select(RoutineSet)))
        template_counts = Counter((r.routine, r.exercise_id) for r in templates)
        keys = {(r.routine, r.exercise_id, r.occurrence): r.id for r in templates}
        for path in sorted(workout_dir.rglob("*.md")):
            if not SESSION_FILE.fullmatch(path.name):
                continue
            # Do not follow sources outside the configured directory through symlinks.
            if not path.resolve().is_relative_to(workout_dir.resolve()):
                report["conflicts"].append(f"Outside workout directory: {path.name}")
                continue
            relative = str(path.relative_to(workout_dir)).replace("\\", "/")
            text = path.read_text(encoding="utf-8")
            existing = db.get(SourceRecord, relative)
            if existing:
                if existing.checksum == checksum(text):
                    report["unchanged"] += 1
                else:
                    report["conflicts"].append(f"Externally changed: {relative}")
                continue
            session_date, routine = filename_date(path.name)
            try:
                parsed = parse_note(text)
            except (ValueError, KeyError, TypeError, YAMLError) as exc:
                report["issues"].append(f"{relative}: {exc}")
                continue
            explicit = parsed.metadata.get("status") == "completed"
            if (
                str(parsed.metadata.get("session_date", session_date)) != session_date
                or parsed.metadata.get("workout", routine) != routine
            ):
                report["conflicts"].append(f"Filename and metadata disagree: {relative}")
                continue
            completed = explicit or (legacy_through is not None and session_date <= legacy_through)
            session_id = str(parsed.metadata.get("session_id") or identity(f"source:{relative}"))
            if db.get(WorkoutSession, session_id):
                report["conflicts"].append(f"Duplicate session identity: {relative}")
                continue
            workout = WorkoutSession(
                id=session_id,
                routine=routine,
                session_date=session_date,
                status="completed" if completed else "review",
                notes=parsed.notes,
                therapy_areas=parsed.metadata.get("therapy_areas", ""),
                created_at=f"{session_date}T00:00:00",
                completed_at=parsed.metadata.get("completed_at") if completed else None,
                source_path=relative,
            )
            db.add(workout)
            db.flush()
            counts = Counter(row.name for row in parsed.rows if row.weight is not None)
            for row in parsed.rows:
                exercise_id = ensure_exercise(db, row.name)
                key = row.template_key
                if key is None and counts[row.name] == template_counts[(routine, exercise_id)]:
                    key = keys.get((routine, exercise_id, row.occurrence))
                if key is not None and key != keys.get((routine, exercise_id, row.occurrence)):
                    raise ValueError(f"Invalid template mapping in {relative}")
                db.add(
                    WorkoutSet(
                        id=identity(f"{session_id}:row:{row.position}"),
                        session_id=session_id,
                        exercise_id=exercise_id,
                        template_key=key,
                        position=row.position,
                        occurrence=row.occurrence,
                        weight=row.weight,
                        reps=row.reps,
                        default_weight=row.weight,
                        default_reps=row.reps,
                        state=row.state,
                        previous_state=row.previous_state,
                        activity_area=row.activity_area,
                        default_source=f"Imported · {session_date}",
                    )
                )
            db.add(
                SourceRecord(
                    path=relative,
                    checksum=checksum(text),
                    original_text=text,
                    issues=json.dumps(parsed.issues),
                    batch_id=batch.id,
                )
            )
            report["imported"] += 1
            if not completed:
                report["review"].append(relative)
            if parsed.issues:
                report["issues"].append({"path": relative, "issues": parsed.issues})
        batch.report = json.dumps(report)
    return report
