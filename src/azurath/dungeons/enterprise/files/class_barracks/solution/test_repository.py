import dataclasses

import pytest

from questboard.repository import InMemoryRepository, Reward


@pytest.fixture
def repo() -> InMemoryRepository[str]:
    r: InMemoryRepository[str] = InMemoryRepository()
    r.add("rats", "Clear the cellar of rats")
    return r


def test_get_returns_added_item(repo: InMemoryRepository[str]) -> None:
    assert repo.get("rats") == "Clear the cellar of rats"
    assert "rats" in repo
    assert len(repo) == 1


def test_duplicate_keys_are_rejected(repo: InMemoryRepository[str]) -> None:
    with pytest.raises(KeyError):
        repo.add("rats", "again")


def test_missing_key_returns_none(repo: InMemoryRepository[str]) -> None:
    assert repo.get("dragon") is None


def test_iteration_keeps_insertion_order(repo: InMemoryRepository[str]) -> None:
    repo.add("dragon", "Slay the dragon")
    assert list(repo) == repo.all() == ["Clear the cellar of rats", "Slay the dragon"]


def test_rewards_add_up_and_are_frozen() -> None:
    total = Reward(10, 5) + Reward(1, 1)
    assert total == Reward(11, 6)
    with pytest.raises(dataclasses.FrozenInstanceError):
        total.gold = 0  # type: ignore[misc]
