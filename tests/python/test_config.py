from pathlib import Path

import pytest

from gym_workouts.config import ROOT, Settings


def test_defaults_do_not_depend_on_a_machine_profile(monkeypatch):
    for key in (
        "GYM_WORKOUT_DIR",
        "GYM_DATABASE_PATH",
        "GYM_WAREHOUSE_PATH",
        "GYM_TIMEZONE",
        "GYM_PORT",
        "GYM_ALLOWED_HOSTS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("USERPROFILE", str(Path("unrelated-profile")))
    settings = Settings.from_env()
    assert settings.workout_dir == ROOT / "data/raw/workout"
    assert settings.timezone == "UTC"
    assert settings.allowed_hosts == ("127.0.0.1", "localhost", "testserver")


def test_local_configuration_overrides_portable_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("GYM_WORKOUT_DIR", str(tmp_path / "workout"))
    monkeypatch.setenv("GYM_TIMEZONE", "Europe/London")
    settings = Settings.from_env()
    assert settings.workout_dir == tmp_path / "workout"
    assert settings.timezone == "Europe/London"


def test_relative_workout_directory_resolves_inside_checkout(monkeypatch):
    monkeypatch.setenv("GYM_WORKOUT_DIR", "data/raw/custom-workout")
    assert Settings.from_env().workout_dir == ROOT / "data/raw/custom-workout"


def test_hosted_hostnames_are_explicit_and_normalized(monkeypatch):
    monkeypatch.setenv("GYM_ALLOWED_HOSTS", " Gym.Example.Com, 127.0.0.1,localhost ")
    assert Settings.from_env().allowed_hosts == ("gym.example.com", "127.0.0.1", "localhost")


@pytest.mark.parametrize("hosts", ["", "*", "*.example.com", "https://gym.example.com", "gym:8010"])
def test_host_configuration_rejects_wildcards_and_urls(monkeypatch, hosts):
    monkeypatch.setenv("GYM_ALLOWED_HOSTS", hosts)
    with pytest.raises(ValueError, match="exact hostnames"):
        Settings.from_env()
