import pytest

goquest = pytest.importorskip(
    "questboard._goquest", reason="extension not built: uv run python scripts/build_go.py goquest"
)


@pytest.mark.parametrize(("rank", "expected"), [("S", 300), ("a", 200), ("B", 150), ("c", 100)])
def test_bonus_by_rank(rank: str, expected: int) -> None:
    assert goquest.bonus(100, rank) == expected


def test_unknown_rank_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown rank"):
        goquest.bonus(100, "Z")


def test_wrong_types_raise_type_error() -> None:
    with pytest.raises(TypeError):
        goquest.bonus("lots", "S")


def test_module_has_a_docstring() -> None:
    assert goquest.__doc__
