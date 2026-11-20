"""Python bindings for the Go rewards library (goext/), via ctypes."""

from __future__ import annotations

import ctypes
import sys
from functools import cache
from pathlib import Path


def _library_path() -> Path:
    if sys.platform == "win32":
        name = "rewards.dll"
    elif sys.platform == "darwin":
        name = "librewards.dylib"
    else:
        name = "librewards.so"
    return Path(__file__).with_name(name)


@cache
def _lib() -> ctypes.CDLL:
    path = _library_path()
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} isn't built: uv run python scripts/build_go.py rewards"
        )
    lib = ctypes.CDLL(str(path))
    lib.CalculateBonus.argtypes = [ctypes.c_longlong, ctypes.c_char_p]
    lib.CalculateBonus.restype = ctypes.c_longlong
    # TODO: declare GuildMotto (restype c_void_p!) and FreeString
    return lib


def available() -> bool:
    try:
        _lib()
    except OSError:  # FileNotFoundError is an OSError, as is a failed dlopen
        return False
    return True


def calculate_bonus(base: int, rank: str) -> int:
    # TODO: reject negative bases, call CalculateBonus, turn -1 into ValueError
    raise NotImplementedError


def guild_motto(name: str) -> str:
    # TODO: call GuildMotto, copy the string with ctypes.string_at, then FreeString it
    raise NotImplementedError
