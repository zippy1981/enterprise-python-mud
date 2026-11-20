"""Storage abstractions for questboard."""

from __future__ import annotations  # lets annotations mention classes before they're defined

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Reward:
    gold: int
    xp: int = 0

    def __add__(self, other: object) -> Reward:
        if not isinstance(other, Reward):
            return NotImplemented
        return Reward(self.gold + other.gold, self.xp + other.xp)


class Repository(Protocol[T]):
    """Anything that can store items by key. (An interface, structurally typed.)"""

    def add(self, key: str, item: T) -> None: ...
    def get(self, key: str) -> T | None: ...
    def all(self) -> list[T]: ...


class InMemoryRepository(Generic[T]):
    """A dict-backed Repository. Satisfies the Protocol without inheriting from it."""

    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def add(self, key: str, item: T) -> None:
        if key in self._items:
            raise KeyError(f"duplicate key: {key!r}")
        self._items[key] = item

    def get(self, key: str) -> T | None:
        return self._items.get(key)

    def all(self) -> list[T]:
        return list(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def __iter__(self) -> Iterator[T]:
        return iter(self._items.values())
