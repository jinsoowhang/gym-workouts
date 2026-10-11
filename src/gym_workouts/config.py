from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    workout_dir: Path
    warehouse_path: Path
    timezone: str = "UTC"
    port: int = 8010
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "testserver")

    @classmethod
    def from_env(cls) -> Settings:
        default = ROOT / "data/raw/workout"

        def project_path(name: str, fallback: str) -> Path:
            path = Path(os.environ.get(name, fallback)).expanduser()
            return path if path.is_absolute() else ROOT / path

        timezone = os.environ.get("GYM_TIMEZONE", "UTC")
        ZoneInfo(timezone)
        port = int(os.environ.get("GYM_PORT", "8010"))
        if not 1024 <= port <= 65535:
            raise ValueError("GYM_PORT must be between 1024 and 65535")
        hosts = tuple(
            host.strip().lower()
            for host in os.environ.get("GYM_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(
                ","
            )
            if host.strip()
        )
        if not hosts or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", h) for h in hosts
        ):
            raise ValueError("GYM_ALLOWED_HOSTS must contain exact hostnames without ports or URLs")
        return cls(
            database_path=project_path("GYM_DATABASE_PATH", "data/app/gym.sqlite3"),
            workout_dir=project_path("GYM_WORKOUT_DIR", str(default)),
            warehouse_path=project_path("GYM_WAREHOUSE_PATH", "data/warehouse/gym.duckdb"),
            timezone=timezone,
            port=port,
            allowed_hosts=hosts,
        )
