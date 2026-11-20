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
    title: str = Field(min_length=3, max_length=80)
    reward: int = Field(ge=0)
    rank: Rank = Rank.C
    guilds: list[str] = Field(default_factory=list)

    @field_validator("rank", mode="before")
    @classmethod
    def _normalise_rank(cls, value: object) -> object:
        return parse_rank(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _s_rank_quests_pay_well(self) -> Quest:
        if self.rank is Rank.S and self.reward < 100:
            raise ValueError("S-rank quests must pay at least 100 gold")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slug(self) -> str:
        return slugify(self.title)
