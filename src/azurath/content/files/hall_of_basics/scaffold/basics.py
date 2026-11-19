"""Four little functions, the first building blocks of questboard.

The `>>>` lines in each docstring are *doctests*: runnable examples. Once you've
implemented the functions, try:  !python -m doctest basics.py -v
"""

import re

VALID_RANKS = {"S", "A", "B", "C"}  # a set literal, like a HashSet<string>


def slugify(title: str) -> str:
    """Turn a quest title into a URL-friendly slug.

    >>> slugify("  Slay the Dragon! ")
    'slay-the-dragon'
    """
    raise NotImplementedError("TODO: use title.lower() and re.sub()")


def parse_rank(text: str) -> str:
    """Normalise a rank like ' a ' to 'A'. Raise ValueError if it isn't S/A/B/C.

    >>> parse_rank(" a ")
    'A'
    """
    raise NotImplementedError("TODO")


def top_quests(rewards: dict[str, int], n: int = 3) -> list[str]:
    """Names of the n best-paying quests, highest first, ties alphabetical.

    >>> top_quests({"rats": 5, "dragon": 500, "lich": 500}, n=2)
    ['dragon', 'lich']
    """
    raise NotImplementedError("TODO: sorted(..., key=lambda name: ...)")


def format_bounty(name: str, reward: int) -> str:
    """Format a bounty for the notice board.

    >>> format_bounty("Dragon", 1500)
    'Dragon: 1,500 gold'
    """
    raise NotImplementedError("TODO: an f-string with a format spec")
