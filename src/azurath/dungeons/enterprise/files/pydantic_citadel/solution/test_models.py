import pytest
from pydantic import ValidationError

from questboard.models import Quest, Rank


def test_quest_parses_and_normalises() -> None:
    q = Quest(title="  Slay the Dragon ", reward="500", rank="s")
    assert q.title == "Slay the Dragon"
    assert q.reward == 500
    assert q.rank is Rank.S
    assert q.slug == "slay-the-dragon"


@pytest.mark.parametrize(
    "bad",
    [
        {"title": "ab", "reward": 1},
        {"title": "Rats", "reward": -1},
        {"title": "Rats", "reward": 1, "rank": "Z"},
        {"title": "Cheap dragon", "reward": 50, "rank": "S"},
    ],
)
def test_invalid_quests_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Quest.model_validate(bad)


def test_round_trips_through_json() -> None:
    q = Quest(title="Rats", reward=5, guilds=["rogues"])
    dumped = q.model_dump(mode="json")
    assert dumped["slug"] == "rats"
    assert isinstance(dumped["id"], str)
    assert Quest.model_validate_json(q.model_dump_json()) == q
