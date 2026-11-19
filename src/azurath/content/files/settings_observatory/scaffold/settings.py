"""Typed configuration from environment variables (and an optional .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # TODO: env_prefix and env_file
        extra="ignore",
    )

    # TODO: environment, storage_connection, max_active_quests, guilds


# TODO: a cached get_settings()
