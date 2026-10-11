from pathlib import Path

from gym_workouts.config import ROOT, Settings


def test_defaults_do_not_depend_on_a_machine_profile(monkeypatch):
    for key in (
        "GYM_WORKOUT_DIR",
        "GYM_DATABASE_PATH",
        "GYM_WAREHOUSE_PATH",
        "GYM_TIMEZONE",
        "GYM_PORT",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("USERPROFILE", str(Path("unrelated-profile")))
    settings = Settings.from_env()
    assert settings.workout_dir == ROOT / "data/raw/workout"
    assert settings.timezone == "UTC"


def test_local_configuration_overrides_portable_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("GYM_WORKOUT_DIR", str(tmp_path / "workout"))
    monkeypatch.setenv("GYM_TIMEZONE", "Europe/London")
    settings = Settings.from_env()
    assert settings.workout_dir == tmp_path / "workout"
    assert settings.timezone == "Europe/London"


def test_relative_workout_directory_resolves_inside_checkout(monkeypatch):
    monkeypatch.setenv("GYM_WORKOUT_DIR", "data/raw/custom-workout")
    assert Settings.from_env().workout_dir == ROOT / "data/raw/custom-workout"
