"""Checks for the Pythonwood's quests.

The audience is around 13 years old, so every criterion and failure message is
written in plain language and points at what to do next. "Grizzle the gnome" is
the in-story name for mutation testing: we break a function on purpose and the
player's tests must turn red.
"""

from __future__ import annotations

import ast
import sys

import yaml

from azurath.checks import Report, calls, checks_for, has_main_guard
from azurath.checks.pyproject import dev_deps, load_pyproject, runtime_deps
from azurath.checks.testing import mutation_survives, run_pytest, stub_out, test_functions
from azurath.dungeons.pythonwood.checks import tidy
from azurath.workspace import Workspace

check = checks_for("pythonwood")


def _no_problems(r: Report, problems: list[str], description: str, extra: str = "") -> bool:
    detail = "\n".join(problems[:10]) + (f"\n{extra}" if extra and problems else "")
    return r.require(not problems, description, detail)


def _gnome(
    ws: Workspace, r: Report, test_file: str, module: str, name: str, trick: str, mutant: str
) -> None:
    """Grizzle swaps in a broken version of a function; the player's tests must go red."""
    survived, output = mutation_survives(ws, test_file, module, mutant)
    r.require(
        not survived,
        f"your tests catch Grizzle when he breaks `{name}` ({trick})",
        f"Grizzle broke `{name}` ({trick}) and your tests stayed green, so they aren't "
        f"checking it closely enough. Add a test that would fail if `{name}` gave the "
        f"wrong answer.\n{output}",
    )


def _stub_gnomes(ws: Workspace, r: Report, test_file: str, module: str, names: list[str]) -> None:
    for name in names:
        _gnome(ws, r, test_file, module, name, "it returns nothing", stub_out([name]))


def _enough_tests(r: Report, tree: ast.Module, rel: str, minimum: int) -> None:
    found = test_functions(tree)
    r.require(
        len(found) >= minimum,
        f"`{rel}` has at least {minimum} tests",
        f"found {len(found)}: {', '.join(found) or 'none'}. Each test is a `def test_...():`.",
    )


# --- 0. Trailhead ---------------------------------------------------------------------


@check("trailhead")
def trailhead(ws: Workspace, r: Report) -> None:
    if r.python_file(ws, "hello.py") is None:
        return
    run = ws.run_python("hello.py")
    printed = run.stdout.strip()
    detail = (
        run.tail()
        if not run.ok
        else f"it printed {printed!r}. Check the spelling, capitals and punctuation!"
    )
    r.require(
        run.ok and "Hello, Pythonwood!" in run.stdout,
        "`python hello.py` prints `Hello, Pythonwood!`",
        detail if printed or not run.ok else "it printed nothing. Did you use print()?",
    )
    source = ws.read("hello.py") or ""
    r.suggest(
        any(line.strip().startswith("#") for line in source.splitlines()),
        "you left a `#` comment explaining your program",
    )


# --- 1. Variable Grove ----------------------------------------------------------------

CRITTER_PROBE = """
import contextlib, io
out = io.StringIO()
with contextlib.redirect_stdout(out):
    import critter
printed = out.getvalue()

def value(name):
    expect(hasattr(critter, name), f"there's no variable called `{name}`")
    return getattr(critter, name, None)

name, species = value("critter_name"), value("species")
health, speed, sleepy = value("health"), value("speed"), value("is_sleepy")
expect(isinstance(name, str) and name.strip(), "`critter_name` should be some text in quotes, like \\"Sparky\\"")
expect(isinstance(species, str) and species.strip(), "`species` should be some text in quotes")
expect(type(health) is int, f"`health` should be a whole number (no quotes!), but it's {health!r}")
if type(health) is int:
    expect(1 <= health <= 95, f"`health` should start between 6 and 100 (so it's 1 to 95 after the bonk), but it ends at {health}")
expect(type(speed) is int and speed >= 0, f"`speed` should be a whole number, 0 or more, but it's {speed!r}")
expect(type(sleepy) is bool, f"`is_sleepy` should be True or False (capital letters, no quotes), but it's {sleepy!r}")
expect(printed.strip(), "critter.py should print a sentence about your critter")
lines = printed.strip().splitlines()
if lines and isinstance(name, str):
    expect(name in lines[0], f"your sentence should include the critter's name ({name!r}). It printed: {lines[0]!r}")
    expect(len(lines) >= 2, "after the bonk, print the same sentence again (it should print two lines)")
    if len(lines) >= 2 and type(health) is int:
        expect(str(health + 5) in lines[0], f"the first sentence should show the starting health ({health + 5}). It printed: {lines[0]!r}")
        expect(str(health) in lines[-1], f"the second sentence should show the health after the bonk ({health}). It printed: {lines[-1]!r}")
"""


@check("variable_grove")
def variable_grove(ws: Workspace, r: Report) -> None:
    tree = r.python_file(ws, "critter.py")
    if tree is None:
        return
    run = ws.run_python("critter.py")
    if not r.require(run.ok, "`python critter.py` runs without errors", run.tail(8)):
        return
    r.probe(ws.probe(CRITTER_PROBE), "your critter's variables hold the right kinds of values")
    r.require(
        any(isinstance(n, ast.JoinedStr) for n in ast.walk(tree)),
        'you used an f-string (`f"...{critter_name}..."`) for the sentence',
    )
    _no_problems(
        r,
        tidy.values_in_fstring_braces(tree),
        "your f-string has variable NAMES in its { }, not values",
    )
    bonks = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AugAssign)
        and isinstance(n.op, ast.Sub)
        and isinstance(n.target, ast.Name)
        and n.target.id == "health"
    ]
    r.require(bonks, "the bonk uses `-=` on `health`", "Take 5 away with `health -= 5`.")
    _no_problems(
        r,
        tidy.name_problems(tidy.top_level_names(tree)),
        "every variable has a good, snake_case name",
    )


# --- 2. The Crossroads ----------------------------------------------------------------

MOOD_PROBE = """
import ast, contextlib, io, pathlib
source = pathlib.Path("mood.py").read_text(encoding="utf-8")
tree = ast.parse(source)

def sets_input(node):
    names = [t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)]
    return isinstance(node, ast.Assign) and set(names) & {"health", "is_sleepy"}

tree.body = [node for node in tree.body if not sets_input(node)]  # we choose the values
code = compile(tree, "mood.py", "exec")
cases = [
    (45, False, "I'm doing OK."), (10, False, "Ouch! I need a snack."),
    (19, False, "Ouch! I need a snack."), (20, False, "I'm doing OK."),
    (69, False, "I'm doing OK."), (70, False, "I feel GREAT!"), (100, False, "I feel GREAT!"),
    (10, True, "Zzz..."), (90, True, "Zzz..."),
]
for health, is_sleepy, want in cases:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(code, {"health": health, "is_sleepy": is_sleepy, "__name__": "__main__"})
    got = out.getvalue().strip().splitlines()
    expect(
        got == [want, "Mood check done!"],
        f"with health = {health} and is_sleepy = {is_sleepy}, mood.py should print "
        f"{want!r} and then 'Mood check done!', but it printed {got!r}",
    )
"""


def indented_well(ws: Workspace, r: Report, rel: str) -> bool:
    """Every block is pushed in by exactly 4 spaces (the Pythonwood's ruler)."""
    return _no_problems(
        r,
        tidy.indentation_problems(ws.read(rel) or "", rel),
        f"every block in `{rel}` is pushed in by exactly 4 spaces",
        "Indentation changes what Python does, so it has to be exact: 4 spaces per block.",
    )


def python_file(ws: Workspace, r: Report, rel: str) -> ast.Module | None:
    """Like ``r.python_file``, with help for indentation errors and the 4-space rule."""
    if not r.file(ws, rel):
        return None
    tree, error = ws.parse(rel)
    if tree is None:
        detail = error or ""
        if "indent" in detail:
            detail += (
                "\nThat's an indentation mistake. Count the spaces at the start of that "
                "line: every line inside an `if`, `else` or `def` is pushed in by exactly "
                "4 spaces more than the line with the colon."
            )
        r.require(False, f"`{rel}` is valid Python", detail)
        return None
    r.require(True, f"`{rel}` is valid Python")
    indented_well(ws, r, rel)
    return tree


@check("crossroads")
def crossroads(ws: Workspace, r: Report) -> None:
    tree = python_file(ws, r, "mood.py")
    if tree is None:
        return
    run = ws.run_python("mood.py")
    if not r.require(run.ok, "`python mood.py` runs without errors", run.tail(8)):
        return
    ifs = [n for n in tree.body if isinstance(n, ast.If)]
    chain = ifs[0] if ifs else None
    branches, has_else = 0, False
    while chain is not None:
        branches += 1
        nxt = chain.orelse
        if len(nxt) == 1 and isinstance(nxt[0], ast.If):
            chain = nxt[0]
        else:
            has_else = bool(nxt)
            chain = None
    r.require(
        branches >= 3 and has_else,
        "you used `if`, `elif` and `else`",
        "Use one `if`, two `elif`s and an `else`, all lined up at the left edge.",
    )
    r.probe(ws.probe(MOOD_PROBE), "your critter picks the right mood every time")


# --- 3. Function Falls ----------------------------------------------------------------

ACTIONS_PROBE = """
import contextlib, io, importlib
mod = importlib.import_module("{module}")
for fn in {names}:
    expect(callable(getattr(mod, fn, None)), f"there's no function called `{{fn}}` in {module}")

def call(fn, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = getattr(mod, fn)(*args)
    expect(out.getvalue() == "", f"`{{fn}}` printed something. Functions here should return their answer, not print it")
    if result is None:
        expect(False, f"`{{fn}}{{args}}` returned nothing (None). Did you forget `return`, or print instead?")
    return result

cases = [
    ("feed", (50, 10), 60), ("feed", (95, 10), 100), ("feed", (100, 0), 100), ("feed", (0, 0), 0),
    ("describe", ("Sparky", 7), "Sparky has 7 health."), ("describe", ("Mossy", 100), "Mossy has 100 health."),
    ("is_tired", (10,), True), ("is_tired", (19,), True), ("is_tired", (20,), False), ("is_tired", (75,), False),
]
cases += {extra}
for fn, args, want in cases:
    if not callable(getattr(mod, fn, None)):
        continue
    got = call(fn, *args)
    if got is not None:
        expect(got == want, f"`{{fn}}{{args}}` returned {{got!r}}, but it should be {{want!r}}")
"""

REST_CASES = (
    '[("rest", (50, 2), 70), ("rest", (95, 1), 100), ("rest", (0, 0), 0), ("rest", (20, 8), 100)]'
)


def actions_probe(module: str, with_rest: bool) -> str:
    names = ["feed", "describe", "is_tired"] + (["rest"] if with_rest else [])
    return ACTIONS_PROBE.format(module=module, names=names, extra=REST_CASES if with_rest else "[]")


@check("function_falls")
def function_falls(ws: Workspace, r: Report) -> None:
    tree = python_file(ws, r, "actions.py")
    if tree is None:
        return
    r.probe(
        ws.probe(actions_probe("actions", with_rest=False)),
        "`feed`, `describe` and `is_tired` return the right answers",
    )
    _no_problems(
        r,
        tidy.prints_inside_functions(tree),
        "your functions return answers instead of printing them",
    )
    _no_problems(
        r,
        tidy.name_problems([a.arg for fn in tidy.functions(tree) for a in fn.args.args]),
        "every parameter has a good, snake_case name",
    )


# --- 4. The Shortcut Trail ------------------------------------------------------------

IS_FULL_CASES = '[("is_full", (100,), True), ("is_full", (150,), True), ("is_full", (99,), False), ("is_full", (0,), False)]'


@check("shortcut_trail")
def shortcut_trail(ws: Workspace, r: Report) -> None:
    actions = python_file(ws, r, "actions.py")
    mood = python_file(ws, r, "mood.py")
    if actions is None or mood is None:
        return
    r.probe(
        ws.probe(
            ACTIONS_PROBE.format(
                module="actions",
                names=["feed", "describe", "is_tired", "is_full"],
                extra=IS_FULL_CASES,
            )
        ),
        "your actions (and the new `is_full`) still give the right answers",
    )
    r.probe(ws.probe(MOOD_PROBE), "mood.py still picks the right mood every time")
    returns = {
        fn.name: fn.body for fn in tidy.functions(actions) if fn.name in ("is_tired", "is_full")
    }
    one_line = [
        name
        for name, body in returns.items()
        if [n for n in body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
        and not (len(body) == 1 and isinstance(body[0], ast.Return))
    ]
    _no_problems(
        r,
        [f"`{name}` should be a single `return` line" for name in one_line],
        "`is_tired` and `is_full` are each one `return` line",
    )
    _no_problems(
        r,
        tidy.bool_shortcut_problems(actions, "actions.py")
        + tidy.bool_shortcut_problems(mood, "mood.py"),
        "no long-way True/False answers left (no `== True`, no if that returns True/False)",
    )


# --- 5. Testing Meadow ----------------------------------------------------------------


@check("testing_meadow")
def testing_meadow(ws: Workspace, r: Report) -> None:
    actions = python_file(ws, r, "actions.py")
    if actions is None:
        return
    _no_problems(
        r,
        tidy.bool_shortcut_problems(actions, "actions.py"),
        "`actions.py` still takes the True/False shortcut",
    )
    r.probe(
        ws.probe(actions_probe("actions", with_rest=True)),
        "`rest` (and the other actions) return the right answers",
    )
    rel = "tests/test_actions.py"
    tree = python_file(ws, r, rel)
    if tree is None:
        return
    _enough_tests(r, tree, rel, 5)
    called = {c.split(".")[-1] for c in calls(tree)}  # real calls, not words in comments
    untested = [name for name in ("feed", "describe", "is_tired", "rest") if name not in called]
    r.require(
        not untested,
        "there are tests for `feed`, `describe`, `is_tired` and `rest`",
        "no tests call: " + ", ".join(untested),
    )
    if not run_pytest(ws, r, rel, "all your tests are GREEN"):
        return
    _stub_gnomes(ws, r, rel, "actions.py", ["feed", "describe", "is_tired", "rest"])
    _gnome(
        ws,
        r,
        rel,
        "actions.py",
        "feed",
        "he removed the 100 limit",
        "\n\ndef feed(health, snack):  # Grizzle was here\n    return health + snack\n",
    )
    survived, _ = mutation_survives(
        ws,
        rel,
        "actions.py",
        "\n\ndef is_tired(energy):  # Grizzle was here\n    return energy <= 20\n",
    )
    r.suggest(
        not survived,
        "bonus: your tests notice when `is_tired(20)` gives the wrong answer",
        "Grizzle changed `<` to `<=` and nobody noticed. Test exactly 20 energy!",
    )


# --- 6. Tidy Treehouse ----------------------------------------------------------------

RULES_PROBE = """
from critters import rules
for name, want in {"MAX_HEALTH": 100, "MAX_ENERGY": 100, "TIRED_BELOW": 20, "REST_PER_HOUR": 10}.items():
    got = getattr(rules, name, None)
    expect(got == want, f"critters/rules.py should have `{name} = {want}`" + (f" (it's {got!r})" if got is not None else ""))
"""


def _imports_from(tree: ast.Module, suffix: str) -> bool:
    return any(
        isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[-1] == suffix
        for n in ast.walk(tree)
    )


@check("tidy_treehouse")
def tidy_treehouse(ws: Workspace, r: Report) -> None:
    r.require(
        not ws.exists("actions.py"),
        "the old `actions.py` has moved into `critters/`",
        "`!git mv actions.py critters/actions.py` (run `!mkdir critters` first)",
    )
    if not r.file(ws, "critters/__init__.py", "This empty file makes the folder a package."):
        return
    if python_file(ws, r, "critters/rules.py") is not None:
        r.probe(ws.probe(RULES_PROBE), "`critters/rules.py` names the game's numbers")
    rel = "critters/actions.py"
    tree = python_file(ws, r, rel)
    if tree is None:
        return
    r.require(
        _imports_from(tree, "rules"),
        "`critters/actions.py` imports its settings from `critters.rules`",
        "Add: `from critters.rules import MAX_ENERGY, MAX_HEALTH, REST_PER_HOUR, TIRED_BELOW`",
    )
    _no_problems(
        r, tidy.magic_numbers(tree, {100, 20, 10}), "no magic numbers left in `critters/actions.py`"
    )
    _no_problems(
        r,
        tidy.bool_shortcut_problems(tree, rel),
        "`critters/actions.py` still takes the True/False shortcut",
    )
    _no_problems(
        r,
        tidy.missing_docstrings(tree, rel),
        "every function in `critters/actions.py` has a docstring",
    )
    r.probe(
        ws.probe(actions_probe("critters.actions", with_rest=True)),
        "your actions still work after the move",
    )
    tests = "tests/test_actions.py"
    if python_file(ws, r, tests) is None:
        return
    r.require(
        "critters" in (ws.read(tests) or ""),
        "your tests import from `critters.actions`",
        "Change `from actions import ...` to `from critters.actions import ...`",
    )
    run_pytest(ws, r, tests, "all your tests are still GREEN (you refactored safely!)")


# --- 7. Backpack Burrow ---------------------------------------------------------------


def _imported_top_modules(tree: ast.Module) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module.split(".")[0])
    return found


@check("backpack_burrow")
def backpack_burrow(ws: Workspace, r: Report) -> None:
    joined = ws.joined_uv_workspace()
    if joined is not None:
        r.require(
            False,
            "your project has its own packing list, not joined to another project",
            f"uv added critter-quest to the project in {joined.parent}. Ask a grown-up to help: "
            f"open {joined}, delete the `[tool.uv.workspace]` section, then run "
            "`!uv add --dev pytest` again here.",
        )
        return
    data = load_pyproject(ws, r)
    if data is None:
        return
    venv = ws.venv_python()
    if not r.require(
        venv is not None,
        "your project has its own backpack (a `.venv` folder)",
        "Run `!uv add --dev pytest`. If it still isn't there, you probably left out "
        "`--no-workspace` (`ask barnaby about no workspace`).",
    ):
        return
    r.require(ws.exists("uv.lock"), "there's a receipt (`uv.lock`)", "`!uv add ...` writes it.")
    r.require(
        "pytest" in dev_deps(data), "pytest is in the **dev** pocket", "`!uv add --dev pytest`"
    )
    borrowed = runtime_deps(data) - {"pytest"}
    r.require(borrowed, "you borrowed a package (it's in `dependencies`)", "`!uv add cowsay`")
    if borrowed:
        modules = " ".join(sorted(borrowed))
        found = ws.run(["uv", "pip", "show", "--python", str(venv), *sorted(borrowed)])
        r.require(
            found.ok, f"the backpack really contains {modules}", found.tail(4) + "\n`!uv sync`"
        )

    tree = python_file(ws, r, "fun.py")
    if tree is not None:
        local = {p.split("/")[0].removesuffix(".py") for p in ws.files()}
        outside = _imported_top_modules(tree) - set(sys.stdlib_module_names) - local
        r.require(
            outside,
            "`fun.py` imports a package you borrowed",
            "Add `import cowsay` (or your package) at the top.",
        )
        run = ws.run([str(venv), "fun.py"])
        r.require(
            run.ok and run.stdout.strip(),
            "`python fun.py` runs and shows something",
            run.tail(8) or "it printed nothing",
        )

    patterns = {p.rstrip("/") for p in ws.gitignore_patterns()}
    r.require(
        ".venv" in patterns,
        "`.gitignore` has a `.venv/` line",
        "`edit .gitignore` and add `.venv/`",
    )
    if ws.is_git_repo():
        r.require(
            not ws.git_tracks(".venv"),
            "git isn't saving the backpack",
            "`!git rm -r --cached .venv`",
        )
    if ws.files("tests"):
        run_pytest(ws, r, "tests", "your tests are still GREEN, now running from the backpack")


# --- 8. Looping Lagoon ----------------------------------------------------------------

TEAM_PROBE = """
import copy
from critters import team as team_mod
TEAM = [{"name": "Sparky", "health": 30}, {"name": "Mossy", "health": 80}, {"name": "Pebble", "health": 55}]
original = copy.deepcopy(TEAM)
cases = [
    ("total_health", TEAM, 165), ("total_health", [], 0), ("total_health", TEAM[:1], 30),
    ("strongest", TEAM, "Mossy"), ("strongest", [], ""), ("strongest", TEAM[:1], "Sparky"),
    ("strongest", [{"name": "Ash", "health": 50}, {"name": "Birch", "health": 50}], "Ash"),
    ("strongest", [{"name": "Low", "health": 1}, {"name": "Mid", "health": 5}, {"name": "Top", "health": 9}], "Top"),
    ("roll_call", TEAM, ["Sparky", "Mossy", "Pebble"]), ("roll_call", [], []),
]
for fn, arg, want in cases:
    func = getattr(team_mod, fn, None)
    if not expect(callable(func), f"there's no function called `{fn}` in critters/team.py"):
        continue
    got = func(arg)
    expect(got == want, f"`{fn}` gave {got!r} for {arg!r}, but it should be {want!r}")
expect(TEAM == original, "one of your functions changed the team it was given. Don't modify the list!")
"""


@check("looping_lagoon")
def looping_lagoon(ws: Workspace, r: Report) -> None:
    rel = "critters/team.py"
    tree = python_file(ws, r, rel)
    if tree is None:
        return
    r.probe(
        ws.probe(TEAM_PROBE), "`total_health`, `strongest` and `roll_call` give the right answers"
    )
    by_name = {fn.name: fn for fn in tidy.functions(tree)}
    no_loop = [
        n
        for n in ("total_health", "strongest", "roll_call")
        if n in by_name and not tidy.has_loop(by_name[n])
    ]
    r.require(
        not no_loop, "each team function uses a loop", "no loop found in: " + ", ".join(no_loop)
    )
    _no_problems(
        r, tidy.missing_docstrings(tree, rel), f"every function in `{rel}` has a docstring"
    )
    tests = "tests/test_team.py"
    test_tree = python_file(ws, r, tests)
    if test_tree is None:
        return
    _enough_tests(r, test_tree, tests, 3)
    if not run_pytest(ws, r, tests, "your team tests are GREEN"):
        return
    _stub_gnomes(ws, r, tests, rel, ["total_health", "strongest", "roll_call"])
    _gnome(
        ws,
        r,
        tests,
        rel,
        "strongest",
        "it always picks the first critter",
        '\n\ndef strongest(team):  # Grizzle was here\n    return team[0]["name"] if team else ""\n',
    )


# --- 9. Robot Tower -------------------------------------------------------------------


def _workflow(ws: Workspace) -> str | None:
    for rel in (".github/workflows/tests.yml", ".github/workflows/tests.yaml"):
        if ws.exists(rel):
            return rel
    others = [f for f in ws.files(".github/workflows") if f.endswith((".yml", ".yaml"))]
    return others[0] if others else None


@check("robot_tower")
def robot_tower(ws: Workspace, r: Report) -> None:
    rel = _workflow(ws)
    if not r.require(rel is not None, "`.github/workflows/tests.yml` exists", "Try `scaffold`."):
        return
    try:
        workflow = yaml.safe_load(ws.read(rel) or "")
    except yaml.YAMLError as exc:
        r.require(
            False, f"`{rel}` is valid YAML", f"Check your indentation (spaces, not tabs).\n{exc}"
        )
        return
    if not r.require(isinstance(workflow, dict), f"`{rel}` is valid YAML"):
        return
    triggers = workflow.get("on", workflow.get(True))  # PyYAML reads the key `on` as True!
    names = set(triggers) if isinstance(triggers, dict | list) else {triggers}
    r.require(
        "push" in names, "the robot runs `on` every **push**", f"found: {sorted(map(str, names))}"
    )
    jobs = [j for j in (workflow.get("jobs") or {}).values() if isinstance(j, dict)]
    r.require(
        any("ubuntu" in str(j.get("runs-on", "")) for j in jobs), "a job `runs-on: ubuntu-latest`"
    )
    steps = [s for j in jobs for s in (j.get("steps") or []) if isinstance(s, dict)]
    uses = [str(s.get("uses", "")) for s in steps]
    runs = [str(s.get("run", "")) for s in steps]
    r.require(
        any(u.startswith("actions/checkout") for u in uses),
        "a step downloads your code (`actions/checkout`)",
    )
    uv_way = any(u.startswith("astral-sh/setup-uv") for u in uses)
    pip_way = any(u.startswith("actions/setup-python") for u in uses) and any(
        "pip install" in c and "pytest" in c for c in runs
    )
    r.require(
        uv_way or pip_way,
        "a step gets uv (`astral-sh/setup-uv`) so the robot can pack your backpack",
        "Add `- uses: astral-sh/setup-uv@v6` after the checkout step.",
    )
    r.require(
        any("pytest" in c and "install" not in c for c in runs),
        "a step runs your tests (`uv run python -m pytest`)",
    )
    if uv_way:
        r.require(
            ws.exists("pyproject.toml") and ws.exists("uv.lock"),
            "your packing list (`pyproject.toml`) and receipt (`uv.lock`) are there for the robot",
            "Go back to the Backpack Burrow!",
        )
    run_pytest(ws, r, "tests", "all your tests are GREEN (the robot will run every one!)")
    if ws.is_git_repo():
        remote = ws.git("remote", "-v")
        r.suggest(
            remote.ok and "origin" in remote.stdout,
            "your project is on GitHub (with a grown-up's OK)",
            "`ask bolt about github`",
        )


# --- 10. Critter Arena ----------------------------------------------------------------

BATTLE_PROBE = """
import copy
from critters.battle import attack, winner
sparky = {"name": "Sparky", "health": 30, "power": 12}
mossy = {"name": "Mossy", "health": 40, "power": 7}
before = copy.deepcopy([sparky, mossy])
for args, want in [((sparky, mossy), 28), ((mossy, sparky), 23),
                   ((sparky, {"name": "Twig", "health": 5, "power": 1}), 0),
                   (({"name": "Zero", "health": 9, "power": 0}, mossy), 40)]:
    got = attack(*args)
    expect(got == want, f"attack({args[0]['name']}, {args[1]['name']}) gave {got!r}, but it should be {want}")
expect(winner(sparky, mossy) == "Sparky", f"winner(Sparky, Mossy) should be 'Sparky', got {winner(sparky, mossy)!r}")
expect(winner(mossy, sparky) == "Sparky", f"winner(Mossy, Sparky) should be 'Sparky', got {winner(mossy, sparky)!r}")
ash = {"name": "Ash", "health": 10, "power": 5}
birch = {"name": "Birch", "health": 10, "power": 5}
expect(winner(ash, birch) == "Ash", "between identical critters, whoever goes first should win")
expect(winner(birch, ash) == "Birch", "between identical critters, whoever goes first should win")
snooze = {"name": "Snooze", "health": 10, "power": 0}
expect(winner(snooze, dict(snooze, name="Doze")) == "draw", "two critters with 0 power should be a 'draw'")
expect(winner(snooze, ash) == "Ash", "a critter with 0 power can't win against one that can hit")
expect([sparky, mossy] == before, "your battle functions changed the critters' dictionaries. Keep health in variables instead!")
"""


@check("critter_arena")
def critter_arena(ws: Workspace, r: Report) -> None:
    rel = "critters/battle.py"
    tree = python_file(ws, r, rel)
    if tree is None:
        return
    result = ws.probe(BATTLE_PROBE, timeout=20)
    if result.crashed and "timed out" in result.output:
        r.require(
            False,
            "the battle finishes",
            "`winner` never stopped. Is there a while loop that can run forever?",
        )
    else:
        r.probe(result, "`attack` and `winner` follow the battle rules")
    main_tree = python_file(ws, r, "main.py")
    if main_tree is not None:
        r.require(
            "main" in {fn.name for fn in tidy.functions(main_tree)} and has_main_guard(main_tree),
            '`main.py` has a `main()` function and the `if __name__ == "__main__":` line',
        )
        r.require(
            _imports_from(main_tree, "battle"),
            "`main.py` uses your battle code (`from critters.battle import ...`)",
        )
        run = ws.run_python("main.py", timeout=20)
        r.require(
            run.ok and ("wins!" in run.stdout or "draw" in run.stdout.lower()),
            "`python main.py` runs a battle and prints who wins",
            run.tail(6) or "it printed nothing",
        )
    problems, long_ones = [], []
    for path in [p for p in ws.files("critters") if p.endswith(".py")] + ["main.py"]:
        file_tree, _ = ws.parse(path)
        if file_tree is None:
            continue
        if path.startswith("critters/"):
            problems += tidy.missing_docstrings(file_tree, path)
        long_ones += tidy.long_functions(file_tree, path)
    _no_problems(r, problems, "every function in `critters/` has a docstring")
    _no_problems(r, long_ones, "no function is longer than 25 lines")
    tests = "tests/test_battle.py"
    test_tree = python_file(ws, r, tests)
    if test_tree is None:
        return
    _enough_tests(r, test_tree, tests, 3)
    if not run_pytest(ws, r, "tests", "ALL your tests are GREEN"):
        return
    _gnome(
        ws,
        r,
        tests,
        rel,
        "attack",
        "health can go below 0",
        '\n\ndef attack(attacker, defender):  # Grizzle was here\n    return defender["health"] - attacker["power"]\n',
    )
    _stub_gnomes(ws, r, tests, rel, ["winner"])
