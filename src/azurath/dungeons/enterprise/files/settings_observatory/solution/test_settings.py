import pytest
from pydantic import ValidationError

from questboard.settings import Settings, get_settings


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTBOARD_STORAGE_CONNECTION", "UseDevelopmentStorage=true")
    monkeypatch.setenv("QUESTBOARD_MAX_ACTIVE_QUESTS", "5")
    monkeypatch.setenv("QUESTBOARD_GUILDS", '["mages", "clerics"]')
    settings = Settings(_env_file=None)
    assert settings.max_active_quests == 5
    assert settings.guilds == ["mages", "clerics"]
    assert "UseDevelopmentStorage" not in repr(settings)
    assert settings.storage_connection.get_secret_value() == "UseDevelopmentStorage=true"


def test_storage_connection_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUESTBOARD_STORAGE_CONNECTION", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_environment_must_be_known() -> None:
    with pytest.raises(ValidationError):
        Settings(storage_connection="x", environment="staging", _env_file=None)


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTBOARD_STORAGE_CONNECTION", "x")
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()
