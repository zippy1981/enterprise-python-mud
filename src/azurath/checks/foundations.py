"""Checks for the Orientation → Modules rooms."""

from __future__ import annotations

import re

from azurath.checks import Report, check, defined_functions, has_main_guard
from azurath.workspace import Workspace

BASICS_PROBE = """
import importlib
mod = importlib.import_module("{module}")
for name in ("slugify", "parse_rank", "top_quests", "format_bounty"):
    expect(hasattr(mod, name), f"{module}.{{name}} is missing")
slugify, parse_rank = mod.slugify, mod.parse_rank
top_quests, format_bounty = mod.top_quests, mod.format_bounty

cases = {{
    "  Slay the Dragon! ": "slay-the-dragon",
    "Rust & Go: a C# dev's tale": "rust-go-a-c-dev-s-tale",
    "already-slugged": "already-slugged",
    "---": "",
    "Quest   42": "quest-42",
}}
for raw, want in cases.items():
    got = slugify(raw)
    expect(got == want, f"slugify({{raw!r}}) returned {{got!r}}, expected {{want!r}}")

for raw, want in {{" a ": "A", "S": "S", "b": "B", "c\\n": "C"}}.items():
    try:
        got = parse_rank(raw)
        expect(got == want, f"parse_rank({{raw!r}}) returned {{got!r}}, expected {{want!r}}")
    except Exception as exc:
        expect(False, f"parse_rank({{raw!r}}) raised {{exc!r}}")
for bad in ("x", "", "SS", "d"):
    try:
        parse_rank(bad)
        expect(False, f"parse_rank({{bad!r}}) should raise ValueError")
    except ValueError:
        pass
    except Exception as exc:
        expect(False, f"parse_rank({{bad!r}}) raised {{type(exc).__name__}}, expected ValueError")

rewards = {{"dragon": 500, "rats": 5, "goblins": 50, "lich": 500, "imp": 50}}
got = top_quests(rewards)
expect(got == ["dragon", "lich", "goblins"], f"top_quests(rewards) returned {{got!r}}, expected ['dragon', 'lich', 'goblins']")
got = top_quests(rewards, n=1)
expect(got == ["dragon"], f"top_quests(rewards, n=1) returned {{got!r}}")
got = top_quests({{}})
expect(got == [], f"top_quests({{{{}}}}) returned {{got!r}}, expected []")
expect(rewards == {{"dragon": 500, "rats": 5, "goblins": 50, "lich": 500, "imp": 50}},
       "top_quests must not modify the dict it's given")

for args, want in {{("Dragon", 1500): "Dragon: 1,500 gold", ("Rats", 5): "Rats: 5 gold",
                    ("Hoard", 1234567): "Hoard: 1,234,567 gold"}}.items():
    got = format_bounty(*args)
    expect(got == want, f"format_bounty{{args!r}} returned {{got!r}}, expected {{want!r}}")
"""


@check("gatehouse")
def gatehouse(ws: Workspace, r: Report) -> None:
    tree = r.python_file(ws, "hello.py")
    if tree is None:
        return
    r.require(
        "main" in defined_functions(tree),
        "`hello.py` defines a `main()` function",
        "def main() -> None:",
    )
    r.require(has_main_guard(tree), '`hello.py` has an `if __name__ == "__main__":` guard')
    run = ws.run_python("hello.py")
    r.require(
        run.ok and "Hello, Azurath!" in run.stdout,
        "running `python hello.py` prints `Hello, Azurath!`",
        run.tail() or "it printed nothing",
    )
    imported = ws.probe("""
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            import hello
        expect(buf.getvalue() == "", f"importing hello printed {buf.getvalue()!r}")
        expect(callable(getattr(hello, "main", None)), "hello.main isn't callable")
    """)
    r.probe(imported, "`import hello` prints nothing (the guard works)")


def _annotations_report(ws: Workspace, r: Report, rel: str) -> None:
    tree, _ = ws.parse(rel)
    if tree is None:
        return
    fns = defined_functions(tree)
    missing = []
    for name in ("slugify", "parse_rank", "top_quests", "format_bounty"):
        fn = fns.get(name)
        if fn is None:
            continue
        if fn.returns is None or any(a.annotation is None for a in fn.args.args):
            missing.append(name)
    r.require(
        not missing,
        "all four functions have type hints",
        "Add parameter and return hints to: " + ", ".join(missing),
    )


@check("hall_of_basics")
def hall_of_basics(ws: Workspace, r: Report) -> None:
    rel = "basics.py"
    if not ws.exists(rel) and ws.exists("questboard/text.py"):
        rel = "questboard/text.py"  # they've already moved it in a later room
    if r.python_file(ws, rel) is None:
        return
    _annotations_report(ws, r, rel)
    module = rel.removesuffix(".py").replace("/", ".")
    r.probe(ws.probe(BASICS_PROBE.format(module=module)), "the four functions behave as specified")


@check("venv_crypt")
def venv_crypt(ws: Workspace, r: Report) -> None:
    r.require(
        ws.exists(".venv/pyvenv.cfg"),
        "`.venv` is a virtual environment",
        "Run `!python -m venv .venv` (or python3 / py).",
    )
    venv = ws.venv_python()
    if venv is None:
        r.require(
            False,
            "`.venv` contains a Python interpreter",
            "Recreate it: delete .venv and run venv again.",
        )
        return
    has_yaml = ws.run([str(venv), "-c", "import yaml; print(yaml.__version__)"])
    r.require(
        has_yaml.ok,
        "PyYAML is installed in `.venv`",
        "`!python -m pip install pyyaml`. If it went elsewhere, check `!python -m pip --version`.",
    )
    reqs = ws.read("requirements.txt")
    pinned = bool(reqs and re.search(r"(?im)^\s*pyyaml\s*==\s*\d", reqs))
    if reqs is None:
        detail = "`!python -m pip freeze > requirements.txt`"
    else:
        detail = "requirements.txt should contain a line like `PyYAML==6.0.2`"
    r.require(pinned, "`requirements.txt` pins `PyYAML==<version>`", detail)
    r.require(ws.git_ignores(".venv"), "git ignores `.venv`", "Add `.venv/` to .gitignore.")
    if ws.is_git_repo():
        r.require(
            not ws.git_tracks(".venv"),
            "`.venv` isn't committed",
            "Remove it from the index: `!git rm -r --cached .venv`",
        )


@check("module_library")
def module_library(ws: Workspace, r: Report) -> None:
    r.require(
        not ws.exists("basics.py"),
        "`basics.py` has moved (no longer at the repo root)",
        "`!git mv basics.py questboard/text.py`",
    )
    if r.python_file(ws, "questboard/text.py") is None:
        return
    if r.python_file(ws, "questboard/__init__.py") is None:
        return
    r.python_file(ws, "questboard/__main__.py")
    api = ws.probe("""
        import questboard
        v = getattr(questboard, "__version__", None)
        expect(isinstance(v, str) and v, "questboard.__version__ should be a non-empty string")
        all_ = getattr(questboard, "__all__", [])
        for name in ("slugify", "parse_rank", "top_quests", "format_bounty"):
            expect(callable(getattr(questboard, name, None)), f"`from questboard import {name}` doesn't work")
            expect(name in all_, f"{name!r} missing from questboard.__all__")
        from questboard.text import slugify
        expect(slugify("It Works!") == "it-works", "questboard.text.slugify is wrong")
        print(v)
    """)
    r.probe(api, "`questboard` re-exports its API and has `__version__`")
    run = ws.run_python("-m", "questboard")
    version = api.output.strip().splitlines()[-1] if api.ok and api.output.strip() else "?"
    r.require(
        run.ok and f"questboard {version}" in run.stdout,
        f"`python -m questboard` prints `questboard {version}`",
        run.tail() or "it printed nothing",
    )
    r.probe(
        ws.probe(BASICS_PROBE.format(module="questboard.text")),
        "the functions still work after the move",
    )
