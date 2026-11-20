"""Domain models, validated by pydantic."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from questboard.text import parse_rank, slugify


class Rank(StrEnum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"


class Quest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: UUID = Field(default_factory=uuid4)
    title: str  # TODO: 3-80 characters
    reward: int  # TODO: >= 0
    rank: Rank = Rank.C
    guilds: list[str] = Field(default_factory=list)

    # TODO: a mode="before" field validator for rank that uses parse_rank

    # TODO: a mode="after" model validator: S-rank quests pay >= 100 gold

    # TODO: a computed `slug` field using slugify(self.title)
