from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

SESSION_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2}) Workout ([AB])\.md$")
SET_LINE = re.compile(r"^(.+?)\s+(\d+(?:\.\d+)?)\s+(\d+)$")


def normalize_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def weight_value(value) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Weight must be a number in lb") from exc
    if not number.is_finite() or not 0 <= number <= Decimal("99999999"):
        raise ValueError("Weight must be a finite nonnegative number")
    if number.as_tuple().exponent < -4:
        raise ValueError("Weight supports up to four decimal places")
    return number


def format_weight(value) -> str:
    if value is None:
        return ""
    return (
        format(Decimal(str(value)), "f").rstrip("0").rstrip(".")
        if "." in str(value)
        else str(value)
    )


@dataclass
class ParsedRow:
    name: str
    weight: Decimal | None
    reps: int | None
    position: int
    occurrence: int
    state: str = "performed"
    template_key: str | None = None
    previous_state: str | None = None


@dataclass
class ParsedNote:
    rows: list[ParsedRow]
    notes: str
    issues: list[str]
    metadata: dict


def parse_note(text: str) -> ParsedNote:
    metadata = {}
    body = text
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) != 3:
            raise ValueError("Unclosed YAML frontmatter")
        metadata = yaml.safe_load(parts[1]) or {}
        if not isinstance(metadata, dict):
            raise ValueError("Frontmatter must be a mapping")
        body = parts[2]
    if metadata.get("gym_workouts_version", 1) != 1:
        raise ValueError("Unsupported app note format version")
    if metadata.get("completed_at") is not None:
        completed_at = datetime.fromisoformat(str(metadata["completed_at"]))
        if completed_at.tzinfo is None:
            raise ValueError("Completion timestamps require a timezone")
        metadata["completed_at"] = completed_at.astimezone(UTC).isoformat()
    rows, notes, issues = [], [], []
    counts = Counter()
    for number, raw in enumerate(body.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ">")):
            continue
        match = SET_LINE.fullmatch(line)
        if match:
            name = normalize_name(match[1])
            counts[name] += 1
            rows.append(
                ParsedRow(name, weight_value(match[2]), int(match[3]), len(rows), counts[name])
            )
        elif normalize_name(line) == "physical therapy":
            counts["physical therapy"] += 1
            rows.append(ParsedRow("physical therapy", None, None, len(rows), 1, state="unknown"))
        else:
            notes.append(line)
            issues.append(f"Line {number}: retained nonnumeric text")
    if "gym_sets" in metadata:
        # Metadata retains omitted/removed positions separately from numeric result lines.
        observed_results = [(r.name, r.weight, r.reps) for r in rows]
        raw_rows = metadata["gym_sets"]
        if not isinstance(raw_rows, list):
            raise ValueError("gym_sets must be a list")
        rows = []
        seen = set()
        for raw in raw_rows:
            name = normalize_name(raw["name"])
            position = int(raw["position"])
            if position < 0 or position in seen:
                raise ValueError("Duplicate or invalid set position")
            seen.add(position)
            state = raw["state"]
            if state not in {"pending", "performed", "skipped", "removed", "unknown"}:
                raise ValueError("Invalid set status")
            weight = weight_value(raw["weight"]) if raw["weight"] is not None else None
            reps = raw["reps"]
            if name != "physical therapy" and (weight is None or type(reps) is not int or reps < 0):
                raise ValueError("Numeric sets require valid weight and reps")
            rows.append(
                ParsedRow(
                    name,
                    weight,
                    reps,
                    position,
                    int(raw["occurrence"]),
                    state,
                    raw.get("template_key"),
                    raw.get("previous_state"),
                )
            )
        rows.sort(key=lambda row: row.position)
        recorded_results = [(r.name, r.weight, r.reps) for r in rows if r.state == "performed"]
        if recorded_results != observed_results:
            raise ValueError("Note results differ from app metadata; review the external edits")
    if metadata.get("weight_unit", "lb") != "lb":
        raise ValueError("Only lb notes are supported; do not silently convert source values")
    return ParsedNote(rows, str(metadata.get("notes", "\n".join(notes))), issues, metadata)


class StartCommand(BaseModel):
    routine: Literal["A", "B"] | None = None


class SetEdit(BaseModel):
    id: str
    weight: Decimal | None = None
    reps: int | None = Field(default=None, ge=0, le=1000000, strict=True)
    state: Literal["pending", "performed", "skipped", "removed", "unknown"]

    @field_validator("weight", mode="before")
    @classmethod
    def validate_weight(cls, value):
        return None if value is None else weight_value(value)


class SessionCommand(BaseModel):
    revision: int = Field(ge=0)
    sets: list[SetEdit] = Field(default_factory=list)
    notes: str = Field(default="", max_length=10000)
    action: str = "save"


def filename_date(filename: str) -> tuple[str, str]:
    match = SESSION_FILE.fullmatch(filename)
    if not match:
        raise ValueError("Invalid workout filename")
    date.fromisoformat(match[1])
    return match[1], match[2]
