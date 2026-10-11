"""Reject private runtime files and machine-specific paths in publishable files."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
result = subprocess.run(
    ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=True,
)
candidates = sorted({Path(name) for name in result.stdout.split("\0") if name})
private_roots = {"data", ".secrets", "target", "logs", "artifacts", "dbt_packages"}
private_extensions = {
    ".sqlite",
    ".sqlite3",
    ".duckdb",
    ".db",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".bundle",
    ".bak",
    ".xlsx",
    ".tsv",
    ".zip",
}
machine_path = re.compile(
    r"(?:/mnt/[a-z]/Users/|[A-Za-z]:\\Users\\|/home/|/Users/)[A-Za-z0-9_.-]+[/\\]",
    re.IGNORECASE,
)
personal_email = re.compile(
    r"[A-Za-z0-9._%+-]+@(?:gmail|googlemail|outlook|hotmail|yahoo|icloud)\.com\b",
    re.IGNORECASE,
)

for path in candidates:
    name = path.name.lower()
    runtime_readme = (
        len(path.parts) == 3
        and path.parts[0] == "data"
        and path.parts[1] in {"app", "raw", "reports", "warehouse"}
        and name == "readme.md"
    )
    private_location = path.parts[0] in private_roots and not runtime_readme
    private_environment = name.startswith(".env") and name != ".env.example"
    private_credential = (
        name.startswith(("credentials", "client_secret", "token")) or "service-account" in name
    ) and path.suffix.lower() == ".json"
    database_sidecar = any(ext in name for ext in (".sqlite3-", ".duckdb.", ".db-"))
    if (
        private_location
        or path.suffix.lower() in private_extensions
        or private_environment
        or private_credential
        or database_sidecar
        or (ROOT / path).is_symlink()
    ):
        raise SystemExit(f"Private file must remain ignored: {path}")
    if (ROOT / path).is_file():
        content = (ROOT / path).read_bytes().decode("utf-8", errors="replace")
        if machine_path.search(content):
            raise SystemExit(f"Machine-specific home path must not be published: {path}")
        if personal_email.search(content):
            raise SystemExit(f"Personal email address must remain in private settings: {path}")
print("Public-file policy passed; runtime state and machine settings stay local.")
