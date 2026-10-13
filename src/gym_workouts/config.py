from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
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
    bind_host: str = "127.0.0.1"
    proxy_ips: str = "127.0.0.1"
    auth_enabled: bool = False
    public_url: str = ""
    allowed_email: str = field(default="", repr=False)
    session_secret: str = field(default="", repr=False)
    google_client_id: str = field(default="", repr=False)
    google_client_secret: str = field(default="", repr=False)

    def __post_init__(self):
        if self.bind_host not in ("127.0.0.1", "0.0.0.0"):
            raise ValueError("GYM_BIND_HOST must be 127.0.0.1 or 0.0.0.0")
        if not self.auth_enabled:
            return
        origin = urlsplit(self.public_url)
        if (
            origin.scheme != "https"
            or origin.hostname not in self.allowed_hosts
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
            or origin.username
            or origin.password
        ):
            raise ValueError("GYM_PUBLIC_URL must be an HTTPS origin in GYM_ALLOWED_HOSTS")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.allowed_email):
            raise ValueError("Authentication requires GYM_ALLOWED_EMAIL")
        if len(self.session_secret) < 32:
            raise ValueError(
                "Authentication requires a GYM_SESSION_SECRET of at least 32 characters"
            )
        if bool(self.google_client_id) != bool(self.google_client_secret):
            raise ValueError("Set both Google client credentials together")

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
        auth = os.environ.get("GYM_AUTH_ENABLED", "false").strip().lower()
        if auth not in ("true", "false"):
            raise ValueError("GYM_AUTH_ENABLED must be true or false")
        return cls(
            database_path=project_path("GYM_DATABASE_PATH", "data/app/gym.sqlite3"),
            workout_dir=project_path("GYM_WORKOUT_DIR", str(default)),
            warehouse_path=project_path("GYM_WAREHOUSE_PATH", "data/warehouse/gym.duckdb"),
            timezone=timezone,
            port=port,
            allowed_hosts=hosts,
            bind_host=os.environ.get("GYM_BIND_HOST", "127.0.0.1"),
            proxy_ips=os.environ.get("GYM_PROXY_IPS", "127.0.0.1"),
            auth_enabled=auth == "true",
            public_url=os.environ.get("GYM_PUBLIC_URL", "").rstrip("/"),
            allowed_email=os.environ.get("GYM_ALLOWED_EMAIL", "").strip().casefold(),
            session_secret=os.environ.get("GYM_SESSION_SECRET", ""),
            google_client_id=os.environ.get("GYM_GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.environ.get("GYM_GOOGLE_CLIENT_SECRET", ""),
        )
