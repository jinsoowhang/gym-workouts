from __future__ import annotations

import os
import tempfile
from pathlib import Path

from gym_workouts.contracts import SESSION_FILE
from gym_workouts.importer import checksum


def publish_note(directory: Path, target_name: str, content: str) -> None:
    """Publish a complete note without overwriting any existing differing file."""
    if not SESSION_FILE.fullmatch(target_name):
        raise ValueError("Invalid workout filename")
    if not directory.is_dir():
        raise OSError("Workout directory is unavailable. Reconnect the vault and retry.")
    target = directory / target_name
    if target.is_symlink():
        raise OSError("Refusing to write through a note symlink")
    if target.exists():
        if checksum(target.read_text(encoding="utf-8")) == checksum(content):
            return
        raise FileExistsError("A different Obsidian note already exists for this date and workout.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".gym-",
            suffix=".tmp",
            dir=directory,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            # Same-directory hard link publishes all bytes atomically with no overwrite race.
            os.link(temporary, target)
        except FileExistsError:
            if target.is_symlink() or checksum(target.read_text(encoding="utf-8")) != checksum(
                content
            ):
                raise FileExistsError(
                    "Note appeared during save; existing content was preserved."
                ) from None
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
