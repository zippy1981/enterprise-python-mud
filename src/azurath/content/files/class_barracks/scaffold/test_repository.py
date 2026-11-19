import pytest

from questboard.repository import InMemoryRepository, Reward


@pytest.fixture
def repo() -> InMemoryRepository[str]:
    r: InMemoryRepository[str] = InMemoryRepository()
    r.add("rats", "Clear the cellar of rats")
    return r


def test_get_returns_added_item(repo: InMemoryRepository[str]) -> None:
    assert repo.get("rats") == "Clear the cellar of rats"


def test_duplicate_keys_are_rejected(repo: InMemoryRepository[str]) -> None:
    # TODO: pytest.raises(KeyError)
    ...


def test_missing_key_returns_none(repo: InMemoryRepository[str]) -> None:
    # TODO
    ...


def test_rewards_add_up() -> None:
    assert Reward(10, 5) + Reward(1, 1) == Reward(11, 6)
