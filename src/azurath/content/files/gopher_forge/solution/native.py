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
    lib.GuildMotto.argtypes = [ctypes.c_char_p]
    lib.GuildMotto.restype = ctypes.c_void_p  # keep the raw pointer so we can free it
    lib.FreeString.argtypes = [ctypes.c_void_p]
    lib.FreeString.restype = None
    return lib


def available() -> bool:
    try:
        _lib()
    except OSError:  # FileNotFoundError is an OSError, as is a failed dlopen
        return False
    return True


def calculate_bonus(base: int, rank: str) -> int:
    if base < 0:
        raise ValueError("base must be >= 0")  # -1 is the library's error sentinel
    result = _lib().CalculateBonus(base, rank.encode("utf-8"))
    if result < 0:
        raise ValueError(f"unknown rank: {rank!r}")
    return int(result)


def guild_motto(name: str) -> str:
    lib = _lib()
    ptr = lib.GuildMotto(name.encode("utf-8"))
    try:
        return ctypes.string_at(ptr).decode("utf-8")
    finally:
        lib.FreeString(ptr)
