from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

import duckdb
from sqlalchemy import Integer, Numeric

from gym_workouts import models  # noqa: F401
from gym_workouts.database import Base

TABLES = (
    "exercises",
    "routine_sets",
    "workout_sessions",
    "workout_sets",
    "source_records",
    "import_batches",
    "vault_writes",
)
EXCLUDED = {
    "source_records": {"original_text"},
    "vault_writes": {"content"},
    "routine_sets": {"user_id"},
    "workout_sessions": {"therapy_areas", "user_id"},
    "workout_sets": {"activity_area"},
}


def extract_snapshot(database_path):
    if not database_path.is_file():
        raise ValueError("Operational database does not exist")
    with sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        version = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        owner = db.execute("SELECT id FROM users WHERE vault_owner = 1").fetchone()
        if owner is None:
            raise ValueError("Operational database has no configured owner")
        tables = {}
        for name in TABLES:
            contract = Base.metadata.tables[name]
            actual = [r[1] for r in db.execute(f'PRAGMA table_info("{name}")')]
            if set(actual) != set(contract.columns.keys()):
                raise ValueError(f"Operational schema drift: {name}")
            columns = [c.name for c in contract.columns if c.name not in EXCLUDED.get(name, set())]
            names = ", ".join(f'"{column}"' for column in columns)
            key = next(iter(contract.primary_key)).name
            condition = (
                " WHERE user_id = ?"
                if name in {"routine_sets", "workout_sessions"}
                else " WHERE session_id IN (SELECT id FROM workout_sessions WHERE user_id = ?)"
                if name in {"workout_sets", "vault_writes"}
                else ""
            )
            parameters = owner if condition else ()
            if name == "exercises":
                condition = (
                    " WHERE id IN (SELECT exercise_id FROM routine_sets WHERE user_id = ? "
                    "UNION SELECT r.exercise_id FROM workout_sets r JOIN workout_sessions w "
                    "ON w.id = r.session_id WHERE w.user_id = ?)"
                )
                parameters = owner + owner
            rows = db.execute(
                f'SELECT {names} FROM "{name}"{condition} ORDER BY "{key}"',
                parameters,
            ).fetchall()
            tables[name] = {"columns": columns, "rows": rows}
        payload = {"schema_version": version, "tables": tables}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return payload, hashlib.sha256(encoded.encode()).hexdigest()


def load_snapshot(database_path, warehouse_path):
    snapshot, snapshot_id = extract_snapshot(database_path)
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_at = datetime.now(UTC).isoformat()
    with duckdb.connect(str(warehouse_path)) as warehouse:
        warehouse.execute("BEGIN TRANSACTION")
        try:
            warehouse.execute("CREATE SCHEMA IF NOT EXISTS gym_raw")
            warehouse.execute(
                "CREATE TABLE IF NOT EXISTS gym_raw.raw_snapshot_manifest "
                "(snapshot_id VARCHAR PRIMARY KEY, extracted_at TIMESTAMPTZ, "
                "schema_version VARCHAR, row_counts VARCHAR)"
            )
            existing = warehouse.execute(
                "SELECT snapshot_id FROM gym_raw.raw_snapshot_manifest WHERE snapshot_id = ?",
                [snapshot_id],
            ).fetchone()
            counts = {name: len(table["rows"]) for name, table in snapshot["tables"].items()}
            if existing:
                warehouse.execute("ROLLBACK")
                return {"snapshot_id": snapshot_id, "unchanged": True, "row_counts": counts}
            for name, table in snapshot["tables"].items():
                contract = Base.metadata.tables[name]
                types = []
                for column in table["columns"]:
                    datatype = contract.columns[column].type
                    sql_type = (
                        "DECIMAL(12,4)"
                        if isinstance(datatype, Numeric)
                        else "BIGINT"
                        if isinstance(datatype, Integer)
                        else "VARCHAR"
                    )
                    types.append(f'"{column}" {sql_type}')
                relation = f"gym_raw.raw_{name}"
                warehouse.execute(
                    f"CREATE TABLE IF NOT EXISTS {relation} "
                    f"({', '.join(types)}, snapshot_id VARCHAR, extracted_at TIMESTAMPTZ)"
                )
                expected_columns = table["columns"] + ["snapshot_id", "extracted_at"]
                actual_columns = [
                    r[0] for r in warehouse.execute(f"DESCRIBE {relation}").fetchall()
                ]
                if actual_columns != expected_columns:
                    raise ValueError(f"Warehouse schema drift: {relation}")
                rows = []
                for source in table["rows"]:
                    values = [
                        Decimal(str(value))
                        if value is not None and isinstance(contract.columns[column].type, Numeric)
                        else value
                        for column, value in zip(table["columns"], source, strict=True)
                    ]
                    rows.append([*values, snapshot_id, extracted_at])
                if rows:
                    placeholders = ",".join("?" for _ in rows[0])
                    warehouse.executemany(f"INSERT INTO {relation} VALUES ({placeholders})", rows)
            # Manifest-last, in the same transaction: interrupted snapshots are never selected.
            warehouse.execute(
                "INSERT INTO gym_raw.raw_snapshot_manifest VALUES (?, ?, ?, ?)",
                [snapshot_id, extracted_at, snapshot["schema_version"], json.dumps(counts)],
            )
            warehouse.execute("COMMIT")
        except Exception:
            warehouse.execute("ROLLBACK")
            raise
    return {"snapshot_id": snapshot_id, "unchanged": False, "row_counts": counts}
