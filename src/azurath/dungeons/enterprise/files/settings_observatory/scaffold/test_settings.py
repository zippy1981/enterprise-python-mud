import pytest

from questboard.settings import Settings, get_settings


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTBOARD_STORAGE_CONNECTION", "UseDevelopmentStorage=true")
    monkeypatch.setenv("QUESTBOARD_MAX_ACTIVE_QUESTS", "5")
    settings = Settings(_env_file=None)
    assert settings.max_active_quests == 5
    # TODO: assert the secret is hidden in repr() but available via get_secret_value()


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTBOARD_STORAGE_CONNECTION", "x")
    get_settings.cache_clear()
    # TODO: assert get_settings() returns the same object twice
