from __future__ import annotations

import argparse
import json
import os

import uvicorn
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from gym_workouts.config import ROOT, Settings
from gym_workouts.database import create_database
from gym_workouts.importer import import_workouts


def migrate(settings):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_path"] = settings.database_path
    command.upgrade(config, "head")


def init_main():
    parser = argparse.ArgumentParser(description="Initialize and import configured workout notes")
    parser.add_argument("--legacy-through", default=os.environ.get("GYM_LEGACY_THROUGH"))
    args = parser.parse_args()
    settings = Settings.from_env()
    migrate(settings)
    engine, factory = create_database(settings.database_path)
    try:
        print(
            json.dumps(
                import_workouts(factory, settings.workout_dir, args.legacy_through), indent=2
            )
        )
    finally:
        engine.dispose()


def import_main():
    parser = argparse.ArgumentParser(description="Import workout notes without modifying the vault")
    parser.add_argument(
        "--legacy-through",
        default=os.environ.get("GYM_LEGACY_THROUGH"),
        help="Confirm historical notes through this ISO date; otherwise require review",
    )
    args = parser.parse_args()
    settings = Settings.from_env()
    engine, factory = create_database(settings.database_path)
    try:
        print(
            json.dumps(
                import_workouts(factory, settings.workout_dir, args.legacy_through), indent=2
            )
        )
    finally:
        engine.dispose()


def web_main():
    settings = Settings.from_env()
    engine, _factory = create_database(settings.database_path)
    try:
        with engine.connect() as connection:
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            head = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
            if current != head:
                raise ValueError("Database migrations are not current")
    except Exception as exc:
        raise SystemExit("Initialize first with: uv run gym-init") from exc
    finally:
        engine.dispose()
    from gym_workouts.app import create_app

    print(f"Gym Workouts: http://127.0.0.1:{settings.port}")
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)


def snapshot_main():
    from gym_workouts.analytics import load_snapshot

    settings = Settings.from_env()
    print(json.dumps(load_snapshot(settings.database_path, settings.warehouse_path), indent=2))
