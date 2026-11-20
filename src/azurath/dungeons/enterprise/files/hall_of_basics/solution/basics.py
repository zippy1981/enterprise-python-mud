"""Four little functions, the first building blocks of questboard.

The `>>>` lines in each docstring are *doctests*: runnable examples. Try:
    python -m doctest basics.py -v
"""

import re

VALID_RANKS = {"S", "A", "B", "C"}


def slugify(title: str) -> str:
    """Turn a quest title into a URL-friendly slug.

    >>> slugify("  Slay the Dragon! ")
    'slay-the-dragon'
    """
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def parse_rank(text: str) -> str:
    """Normalise a rank like ' a ' to 'A'. Raise ValueError if it isn't S/A/B/C.

    >>> parse_rank(" a ")
    'A'
    """
    rank = text.strip().upper()
    if rank not in VALID_RANKS:
        raise ValueError(f"unknown rank {text!r}; expected one of {sorted(VALID_RANKS)}")
    return rank


def top_quests(rewards: dict[str, int], n: int = 3) -> list[str]:
    """Names of the n best-paying quests, highest first, ties alphabetical.

    >>> top_quests({"rats": 5, "dragon": 500, "lich": 500}, n=2)
    ['dragon', 'lich']
    """
    return sorted(rewards, key=lambda name: (-rewards[name], name))[:n]


def format_bounty(name: str, reward: int) -> str:
    """Format a bounty for the notice board.

    >>> format_bounty("Dragon", 1500)
    'Dragon: 1,500 gold'
    """
    return f"{name}: {reward:,} gold"
