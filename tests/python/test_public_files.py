import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("filename", "content", "allowed"),
    [
        ("README.md", "Contact: owner@example.com", True),
        ("README.md", "Contact: invented-owner@" + "gmail.com", False),
        ("client_secret_example.json", "{}", False),
        ("token.json", "{}", False),
    ],
)
def test_public_file_policy_blocks_private_contact_and_oauth_files(
    tmp_path, filename, content, allowed
):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(ROOT / "scripts/check_public_files.py", scripts / "check_public_files.py")
    shutil.copyfile(ROOT / ".gitignore", tmp_path / ".gitignore")
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    (tmp_path / filename).write_text(content)
    # Check the index too: ignore rules cannot protect a file already force-staged.
    subprocess.run(["git", "add", "--force", "--", filename], cwd=tmp_path, check=True)
    result = subprocess.run(
        [sys.executable, str(scripts / "check_public_files.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is allowed
    if not allowed:
        assert filename in result.stderr
