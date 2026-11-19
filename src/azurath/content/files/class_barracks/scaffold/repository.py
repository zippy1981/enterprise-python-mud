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
        # TODO: return NotImplemented for non-Rewards, else a new summed Reward
        raise NotImplementedError


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
        # TODO: raise KeyError on duplicates
        raise NotImplementedError

    def get(self, key: str) -> T | None:
        raise NotImplementedError

    def all(self) -> list[T]:
        raise NotImplementedError

    # TODO: __len__, __contains__, __iter__
