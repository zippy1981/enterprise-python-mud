"""Checks for the Go extension side quests."""

from __future__ import annotations

import shutil

from azurath.checks import Report, check
from azurath.workspace import Workspace


def _toolchain(ws: Workspace, r: Report) -> bool:
    go = shutil.which("go")
    if not r.require(
        go is not None, "Go is installed", "`ask gwen about install` (https://go.dev/dl/)"
    ):
        return False
    cc = ws.run(["go", "env", "CC"])
    compiler = cc.stdout.strip().split()[0] if cc.ok and cc.stdout.strip() else "gcc"
    return r.require(
        shutil.which(compiler) is not None,
        f"a C compiler for cgo (`{compiler}`) is on PATH",
        "cgo needs one: `ask gwen about install`.",
    )


def _go_sources(ws: Workspace, folder: str) -> str:
    return "\n".join(ws.read(f) or "" for f in ws.files(folder) if f.endswith(".go"))


def _build(ws: Workspace, r: Report, target: str) -> bool:
    if not r.file(ws, "scripts/build_go.py", "`scaffold` writes it."):
        return False
    res = ws.run([ws.python(), "scripts/build_go.py", target], timeout=600)
    return r.require(res.ok, f"`scripts/build_go.py {target}` builds", res.tail(25))


def _tests_ran(ws: Workspace, r: Report, rel: str, description: str) -> None:
    if r.python_file(ws, rel) is None:
        return
    res = ws.run(
        [ws.python(), "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", rel], timeout=300
    )
    if not r.require(res.ok, description, res.tail(20)):
        return
    r.require("skipped" not in res.stdout, f"`{rel}` actually ran (nothing skipped)", res.tail(6))


@check("gopher_forge")
def gopher_forge(ws: Workspace, r: Report) -> None:
    if not _toolchain(ws, r):
        return
    if not r.file(ws, "goext/go.mod"):
        return
    source = _go_sources(ws, "goext")
    r.require('import "C"' in source, '`goext` uses cgo (`import "C"`)')
    for name in ("CalculateBonus", "GuildMotto", "FreeString"):
        r.require(
            f"//export {name}" in source,
            f"`goext` exports `{name}`",
            f"Add `//export {name}` above the func.",
        )
    if not _build(ws, r, "rewards"):
        return
    wrapper = ws.read("questboard/native.py")
    if not r.file(ws, "questboard/native.py"):
        return
    assert wrapper is not None
    r.require(
        "argtypes" in wrapper and "restype" in wrapper,
        "`native.py` declares `argtypes` and `restype`",
    )
    r.require("FreeString" in wrapper, "`native.py` frees the motto string with `FreeString`")
    behaviour = ws.probe("""
        from questboard import native
        for rank, want in {"S": 300, "A": 200, "a": 200, "B": 150, "C": 100}.items():
            got = native.calculate_bonus(100, rank)
            expect(got == want, f"calculate_bonus(100, {rank!r}) returned {got!r}, expected {want}")
            expect(type(got) is int, "calculate_bonus should return a plain int")
        expect(native.calculate_bonus(7, "B") == 10, "B-rank uses integer maths: 7 * 3 // 2 == 10")
        try:
            native.calculate_bonus(100, "Z")
            expect(False, "calculate_bonus(100, 'Z') should raise ValueError")
        except ValueError:
            pass
        motto = native.guild_motto("Ada")
        expect(motto == "For Ada and the Guild!", f"guild_motto('Ada') returned {motto!r}")
        expect(native.guild_motto("Zoë") == "For Zoë and the Guild!", "guild_motto should handle UTF-8 names")
        for _ in range(2000):  # if this leaks it won't fail, but it shouldn't crash either
            native.guild_motto("x")
    """)
    r.probe(behaviour, "`calculate_bonus` and `guild_motto` work through ctypes")
    built = [
        f for f in ws.path("questboard").glob("*rewards*") if f.suffix in {".so", ".dylib", ".dll"}
    ]
    if built:
        rel = built[0].relative_to(ws.root).as_posix()
        r.require(
            ws.git_ignores(rel),
            f"git ignores the built `{rel}`",
            "Add `*.so`, `*.dylib`, `*.dll` to .gitignore.",
        )
    _tests_ran(ws, r, "tests/test_native.py", "`tests/test_native.py` passes")


@check("gopher_sanctum")
def gopher_sanctum(ws: Workspace, r: Report) -> None:
    if not _toolchain(ws, r):
        return
    headers = ws.probe("""
        import os, sysconfig
        inc = sysconfig.get_paths()["include"]
        expect(os.path.exists(os.path.join(inc, "Python.h")), f"Python.h not found in {inc}")
    """)
    if not r.probe(headers, "Python headers exist for your `.venv` interpreter"):
        return
    for rel in ("goquest/go.mod", "goquest/module.c"):
        if not r.file(ws, rel):
            return
    source = _go_sources(ws, "goquest")
    r.require("//export PyInit__goquest" in source, "`goquest` exports `PyInit__goquest`")
    if not _build(ws, r, "goquest"):
        return
    behaviour = ws.probe("""
        import importlib.machinery
        from questboard import _goquest
        expect(any(_goquest.__file__.endswith(s) for s in importlib.machinery.EXTENSION_SUFFIXES),
               f"_goquest should load from a native extension file, got {_goquest.__file__}")
        for rank, want in {"S": 300, "A": 200, "b": 150, "C": 100}.items():
            got = _goquest.bonus(100, rank)
            expect(got == want, f"bonus(100, {rank!r}) returned {got!r}, expected {want}")
        expect(_goquest.bonus(7, "B") == 10, "B-rank uses integer maths: 7 * 3 // 2 == 10")
        try:
            _goquest.bonus(100, "Z")
            expect(False, "bonus(100, 'Z') should raise ValueError")
        except ValueError:
            pass
        try:
            _goquest.bonus("lots", "S")
            expect(False, "bonus('lots', 'S') should raise TypeError")
        except TypeError:
            pass
        expect(bool(_goquest.__doc__), "the module should have a docstring (m_doc)")
    """)
    r.probe(
        behaviour, "`import questboard._goquest` works and `bonus()` behaves like a Python function"
    )
    built = [f for f in ws.path("questboard").glob("_goquest*") if f.suffix in {".so", ".pyd"}]
    if built:
        rel = built[0].relative_to(ws.root).as_posix()
        r.require(
            ws.git_ignores(rel),
            f"git ignores the built `{rel}`",
            "Add `*.so` and `*.pyd` to .gitignore.",
        )
    r.require(ws.exists("questboard/_goquest.pyi"), "type stubs in `questboard/_goquest.pyi`")
    _tests_ran(ws, r, "tests/test_goquest.py", "`tests/test_goquest.py` passes")
