import pytest

from questboard import native

pytestmark = pytest.mark.skipif(
    not native.available(), reason="Go library not built: uv run python scripts/build_go.py rewards"
)


@pytest.mark.parametrize(("rank", "expected"), [("S", 300), ("a", 200), ("B", 150), ("C", 100)])
def test_bonus_by_rank(rank: str, expected: int) -> None:
    assert native.calculate_bonus(100, rank) == expected


def test_unknown_rank_raises() -> None:
    with pytest.raises(ValueError):
        native.calculate_bonus(100, "Z")


def test_guild_motto() -> None:
    assert native.guild_motto("Ada") == "For Ada and the Guild!"
