"""Tests for questboard.text. Run with: uv run pytest -q"""

import pytest

from questboard.text import format_bounty, parse_rank, slugify, top_quests


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Slay the Dragon", "slay-the-dragon"),
        # TODO: add at least two more cases (punctuation? leading spaces? numbers?)
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_parse_rank_normalises() -> None:
    assert parse_rank(" a ") == "A"


def test_parse_rank_rejects_unknown_ranks() -> None:
    # TODO: use pytest.raises(ValueError) to prove parse_rank("Z") fails
    ...


def test_top_quests_orders_by_reward_then_name() -> None:
    # TODO
    ...


def test_format_bounty() -> None:
    assert format_bounty("Dragon", 1500) == "Dragon: 1,500 gold"
