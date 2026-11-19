"""Game configuration, loaded with pydantic-settings.

This is the same pattern you build in the Settings Observatory. Values come
from, highest priority first:

1. keyword arguments (the CLI passes ``--workspace`` this way)
2. environment variables prefixed ``AZURATH_`` (``AZURATH_EDITOR=vim``)
3. an optional ``azurath.toml`` in the current directory

It is like layering ``appsettings.json``, environment variables and command-line
args with ``IConfiguration``, except the result is a typed, validated object.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class AzurathSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AZURATH_",
        toml_file="azurath.toml",
        extra="ignore",
    )

    workspace: Path = Field(
        default=Path("questboard"),
        description="Folder where you build the questboard repo, relative to the current dir.",
    )
    editor: str | None = Field(
        default=None,
        description="Command for `edit`, e.g. 'vim', 'nano', 'code -r'. Auto-detected if unset.",
    )
    shell: str | None = Field(
        default=None,
        description="Shell for `!` commands. Defaults to $SHELL, or pwsh/powershell on Windows.",
    )
    auto_commit: bool = Field(default=True, description="git commit when a quest is completed.")
    code_theme: str = Field(default="monokai", description="Pygments theme for code blocks.")
    color: bool = True

    @field_validator("workspace")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Order matters: earlier sources win.
        return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls))
