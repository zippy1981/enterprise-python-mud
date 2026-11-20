"""Typed configuration from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUESTBOARD_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["dev", "test", "prod"] = "dev"
    storage_connection: SecretStr
    max_active_quests: int = Field(default=10, ge=1)
    guilds: list[str] = ["mages", "rogues", "bards"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
