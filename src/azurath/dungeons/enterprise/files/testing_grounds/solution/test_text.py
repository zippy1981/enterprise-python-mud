"""Tests for questboard.text. Run with: uv run pytest -q"""

import pytest

from questboard.text import format_bounty, parse_rank, slugify, top_quests


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Slay the Dragon", "slay-the-dragon"),
        ("  Slay the Dragon!  ", "slay-the-dragon"),
        ("Quest #42: Rats", "quest-42-rats"),
        ("!!!", ""),
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_parse_rank_normalises() -> None:
    assert parse_rank(" a ") == "A"


@pytest.mark.parametrize("bad", ["Z", "", "SS"])
def test_parse_rank_rejects_unknown_ranks(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_rank(bad)


def test_top_quests_orders_by_reward_then_name() -> None:
    rewards = {"rats": 5, "lich": 500, "dragon": 500, "goblins": 50}
    assert top_quests(rewards, n=3) == ["dragon", "lich", "goblins"]


def test_format_bounty() -> None:
    assert format_bounty("Dragon", 1500) == "Dragon: 1,500 gold"
