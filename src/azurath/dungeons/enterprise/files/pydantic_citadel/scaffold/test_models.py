import pytest
from pydantic import ValidationError

from questboard.models import Quest, Rank


def test_quest_parses_and_normalises() -> None:
    q = Quest(title="  Slay the Dragon ", reward=500, rank="s")
    assert q.title == "Slay the Dragon"
    assert q.rank is Rank.S
    assert q.slug == "slay-the-dragon"


def test_negative_rewards_are_rejected() -> None:
    # TODO: pytest.raises(ValidationError)
    ...
