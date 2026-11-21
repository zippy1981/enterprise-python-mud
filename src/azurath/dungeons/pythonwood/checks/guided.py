"""Checks for the Pythonwood's guided rooms ("uncomment the right answer").

Each guided room's starter file has numbered STEPs with commented-out choices. The
player uncomments the right line in each step. Checks look at what the code *does*
(its output and values), so uncommenting a wrong choice, or two choices, fails with a
message about that step.
"""

from __future__ import annotations

import ast

from azurath.checks import Report, checks_for, has_main_guard
from azurath.checks.testing import mutation_survives, run_pytest, stub_out
from azurath.content import load_dungeon
from azurath.dungeons.pythonwood.checks import tidy
from azurath.workspace import Workspace

check = checks_for("pythonwood")

UNCOMMENT_TIP = (
    "When you uncomment a line, delete the `#` AND the space after it, and nothing else. "
    "The easiest way: click the line and press Ctrl+/ (Cmd+/ on a Mac)."
)


def guided_file(ws: Workspace, r: Report, room: str, rel: str, scaffold: str) -> ast.Module | None:
    """Require the practice file exists, parses, and has been changed from the starter."""
    if not r.file(ws, rel, "Type `scaffold` to get the practice file."):
        return None
    tree, error = ws.parse(rel)
    if tree is None:
        detail = error or ""
        if any(clue in detail for clue in ("indent", "unindent")):
            detail += "\n" + UNCOMMENT_TIP
        else:
            detail += (
                "\nOne of the lines you uncommented isn't valid Python. Was it the right choice?"
            )
        r.require(False, f"`{rel}` is valid Python", detail)
        return None
    r.require(True, f"`{rel}` is valid Python")
    starter = load_dungeon("pythonwood").room_text(room, "scaffold", scaffold)
    changed = (ws.read(rel) or "").strip() != starter.strip()
    r.require(changed, "you've uncommented your answers", "Uncomment the right line in each STEP.")
    return tree if changed else None


def output_is(ws: Workspace, r: Report, rel: str, expected: list[str]) -> bool:
    run = ws.run_python(rel, timeout=20)
    got = [line.rstrip() for line in run.stdout.strip().splitlines()]
    if not run.ok:
        detail = run.tail(6)
        if "NameError" in run.output:
            detail += (
                "\nA NameError means Python doesn't know a name. Check that you picked the "
                "right line in every STEP (spelling and capital letters matter)."
            )
        return r.require(False, f"`python {rel}` runs without errors", detail)
    want = "\n".join(expected)
    return r.require(
        got == expected,
        f"`python {rel}` prints the right thing",
        f"expected:\n{want}\nbut it printed:\n" + ("\n".join(got) or "(nothing)"),
    )


def quiz(ws: Workspace, r: Report, module: str, answers: dict[str, tuple[object, str]]) -> None:
    """Each variable must hold the right answer; ``answers`` maps name -> (value, step)."""
    lines = [
        "import importlib",
        f"quiz = importlib.import_module({module!r})",
    ]
    for name, (value, step) in answers.items():
        lines.append(
            f"expect(getattr(quiz, {name!r}, None) == {value!r}, "
            f"{f'{step}: ' + 'pick the right answer for `' + name + '`'!r} "
            f"+ ('' if hasattr(quiz, {name!r}) else ' (nothing is uncommented yet)'))"
        )
    r.probe(ws.probe("\n".join(lines)), "every STEP has the right answer")


# --- the nine guided rooms ---------------------------------------------------------------


@check("trailhead_guided")
def trailhead_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/signpost.py"
    if guided_file(ws, r, "trailhead_guided", rel, "signpost.py") is None:
        return
    output_is(ws, r, rel, ["Hello from the Signpost!", "I am ready to code!"])


@check("variable_grove_guided")
def variable_grove_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/acorns.py"
    if guided_file(ws, r, "variable_grove_guided", rel, "acorns.py") is None:
        return
    if not output_is(ws, r, rel, ["<class 'float'>", "Pip 3 1.5 True"]):
        return
    r.probe(
        ws.probe("""
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                from practice import acorns
            expect(acorns.pet_name == "Pip", "STEP 1: pet_name should hold the text Pip")
            expect(type(acorns.age) is int, "STEP 2: age should be the whole number 3 (an int), no quotes")
            expect(type(acorns.height) is float, "STEP 3: height should be 1.5 with a DOT (a float), no quotes")
            expect(acorns.is_hungry is True, "STEP 4: is_hungry should be True (capital T, no quotes)")
        """),
        "each variable holds the right type of value",
    )


@check("variable_grove_guided_math")
def variable_grove_guided_math(ws: Workspace, r: Report) -> None:
    rel = "practice/abacus.py"
    if guided_file(ws, r, "variable_grove_guided_math", rel, "abacus.py") is None:
        return
    if output_is(ws, r, rel, ["acorns=26 share=4 leftover=1"]):
        return
    r.probe(
        ws.probe("""
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                from practice import abacus
            share = getattr(abacus, "each_share", None)
            expect(type(share) is int, f"STEP 3: each_share should be a WHOLE number. `/` gives {13 / 3}, `//` gives {13 // 3}")
            expect(getattr(abacus, "leftover", None) == 1, "STEP 4: the remainder of 13 shared by 3 is 1 (that's `%`)")
        """),
        "the sums use the right operators",
    )


@check("variable_grove_guided_strings")
def variable_grove_guided_strings(ws: Workspace, r: Report) -> None:
    rel = "practice/words.py"
    tree = guided_file(ws, r, "variable_grove_guided_strings", rel, "words.py")
    if tree is None:
        return
    output_is(
        ws, r, rel, ["PIP ACORNSWORTH", "P", "Pip Acornsworth has 15 characters", "hiphiphip"]
    )
    problems = tidy.values_in_fstring_braces(tree)
    r.require(
        not problems, "STEP 5: the f-string has variable NAMES in its { }", "\n".join(problems)
    )


@check("variable_grove_guided_order")
def variable_grove_guided_order(ws: Workspace, r: Report) -> None:
    rel = "practice/brackets.py"
    if guided_file(ws, r, "variable_grove_guided_order", rel, "brackets.py") is None:
        return
    quiz(
        ws,
        r,
        "practice.brackets",
        {
            "answer_one": (2 + 3 * 4, "STEP 1 (times happens before plus)"),
            "answer_two": ((2 + 3) * 4, "STEP 2"),
            "average": ((8 + 4) / 2, "STEP 3 (brackets first, then divide)"),
            "answer_four": (2**3 * 2, "STEP 4 (powers happen before times)"),
            "total": (3 * 2 + 1, "STEP 5"),
        },
    )
    output_is(ws, r, rel, ["14 20 6.0 16 7"])


@check("variable_grove_guided_increment")
def variable_grove_guided_increment(ws: Workspace, r: Report) -> None:
    rel = "practice/tally.py"
    tree = guided_file(ws, r, "variable_grove_guided_increment", rel, "tally.py")
    if tree is None:
        return
    if not output_is(ws, r, rel, ["16 Hi!"]):
        return
    operators = {type(n.op).__name__ for n in ast.walk(tree) if isinstance(n, ast.AugAssign)}
    r.require(
        {"Add", "Sub", "Mult"} <= operators,
        "you used `+=`, `-=` and `*=`",
        "Each STEP has a choice using one of them.",
    )


@check("function_falls_guided")
def function_falls_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/stones.py"
    if guided_file(ws, r, "function_falls_guided", rel, "stones.py") is None:
        return
    if not output_is(ws, r, rel, ["42"]):
        return
    r.probe(
        ws.probe("""
            import contextlib, io
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                from practice import stones
                d, g, big, small = stones.double(4), stones.greet("Ada"), stones.is_big(11), stones.is_big(10)
                b = stones.bonus(2)
            expect(d == 8, f"STEP 1: double(4) should return 8, but it returned {d!r}")
            expect(g == "Hi, Ada!", f"STEP 2: greet('Ada') should return 'Hi, Ada!', but it returned {g!r}")
            expect(big is True and small is False, "STEP 3: is_big should be True for 11 and False for 10")
            expect(b == 30, f"STEP 4: bonus(2) should be (2 + 1) * 10 = 30, but it returned {b!r}. Brackets first!")
            expect(out.getvalue().strip() == "42", "the functions should RETURN their answers, not print them")
        """),
        "every function returns the right answer",
    )


@check("testing_meadow_guided")
def testing_meadow_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/test_practice_pen.py"
    if guided_file(ws, r, "testing_meadow_guided", rel, "test_practice_pen.py") is None:
        return
    r.probe(
        ws.probe("""
            from practice.test_practice_pen import add_berries
            expect(add_berries(2, 3) == 5, f"STEP 2: add_berries(2, 3) should be 5, not {add_berries(2, 3)!r}")
            expect(add_berries(4, 0) == 4, "STEP 2: add_berries(4, 0) should be 4")
        """),
        "`add_berries` is finished (GREEN step)",
    )
    if not run_pytest(ws, r, rel, "`pytest practice` is GREEN"):
        return
    survived, output = mutation_survives(ws, rel, rel, stub_out(["add_berries"]))
    r.require(
        not survived,
        "your tests catch a broken `add_berries` (they can go RED)",
        "Did you uncomment both tests (STEP 1 and STEP 3), with the right answers?\n" + output,
    )


@check("tidy_treehouse_guided")
def tidy_treehouse_guided(ws: Workspace, r: Report) -> None:
    for rel in ("practice/__init__.py", "practice/sorting_shed/__init__.py"):
        if not r.file(ws, rel, "Type `scaffold` to get the practice files."):
            return
    if (
        guided_file(ws, r, "tidy_treehouse_guided", "practice/sorting_shed/rules.py", "rules.py")
        is None
    ):
        return
    rel = "practice/sorting_shed/shed.py"
    tree = guided_file(ws, r, "tidy_treehouse_guided", rel, "shed.py")
    if tree is None:
        return
    r.probe(
        ws.probe("""
            from practice.sorting_shed import rules, shed
            expect(getattr(rules, "MAX_COINS", None) == 50, "STEP 1: rules.py needs MAX_COINS = 50")
            expect(shed.add_coins(40, 5) == 45, f"STEP 4: add_coins(40, 5) should be 45, not {shed.add_coins(40, 5)!r}")
            expect(shed.add_coins(45, 10) == 50, "STEP 4: add_coins(45, 10) should stop at MAX_COINS (50)")
        """),
        "the shed adds coins up to MAX_COINS",
    )
    fn = next((f for f in tidy.functions(tree) if f.name == "add_coins"), None)
    doc = ast.get_docstring(fn) if fn else None
    r.require(
        bool(doc) and "coin" in doc.lower(),
        "STEP 3: `add_coins` has a helpful docstring",
        "Pick the docstring that explains what the function does.",
    )
    magic = tidy.magic_numbers(tree, {50})
    r.require(not magic, "STEP 4: no magic number 50 in `shed.py`", "\n".join(magic))


@check("backpack_burrow_guided")
def backpack_burrow_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/packing_quiz.py"
    if guided_file(ws, r, "backpack_burrow_guided", rel, "packing_quiz.py") is None:
        return
    quiz(
        ws,
        r,
        "practice.packing_quiz",
        {
            "package": ("code someone else wrote that you can borrow", "STEP 1"),
            "backpack_folder": (".venv", "STEP 2"),
            "add_command": ("uv add cowsay", "STEP 3"),
            "dev_command": ("uv add --dev pytest", "STEP 4"),
            "save_in_git": (["pyproject.toml", "uv.lock"], "STEP 5"),
            "init_command": ("uv init --bare --no-workspace", "STEP 6"),
        },
    )


@check("looping_lagoon_guided")
def looping_lagoon_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/lily_pads.py"
    if guided_file(ws, r, "looping_lagoon_guided", rel, "lily_pads.py") is None:
        return
    if not output_is(ws, r, rel, ["BERRY", "14"]):
        return
    r.probe(
        ws.probe("""
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                from practice import lily_pads
            expect(lily_pads.snacks == ["berry", "acorn", "seed"], "STEP 1: snacks should be a LIST in square brackets")
            for words, want in ((["ab", "c"], 3), ([], 0), (["seed"], 4)):
                got = lily_pads.count_letters(words)
                expect(got == want, f"STEP 3: count_letters({words!r}) should be {want}, not {got!r}")
        """),
        "the list and the loop work",
    )


@check("robot_tower_guided")
def robot_tower_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/robot_quiz.py"
    if guided_file(ws, r, "robot_tower_guided", rel, "robot_quiz.py") is None:
        return
    quiz(
        ws,
        r,
        "practice.robot_quiz",
        {
            "commit": ("a save point of your whole project", "STEP 1"),
            "ci": ("Continuous Integration", "STEP 2"),
            "robot_runs": ("every time you push", "STEP 3"),
            "workflow_folder": (".github/workflows", "STEP 4"),
            "when_red": ("fix it before anything else", "STEP 5"),
        },
    )


@check("critter_arena_guided")
def critter_arena_guided(ws: Workspace, r: Report) -> None:
    rel = "practice/training_ring.py"
    tree = guided_file(ws, r, "critter_arena_guided", rel, "training_ring.py")
    if tree is None:
        return
    result = ws.probe(
        """
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            from practice import training_ring
        expect(out.getvalue() == "", "STEP 3: importing the file shouldn't run main(). Use the __name__ line")
        for health, power, want in ((10, 3, 4), (9, 3, 3), (1, 5, 1), (0, 5, 0)):
            got = training_ring.rounds_to_win(health, power)
            expect(got == want, f"STEPS 1-2: rounds_to_win({health}, {power}) should be {want}, not {got!r}")
    """,
        timeout=20,
    )
    if result.crashed and "timed out" in result.output:
        r.require(
            False,
            "the loop finishes",
            "The loop never stopped. Did you uncomment BOTH lines of its body?",
        )
        return
    r.probe(result, "the while loop counts the hits")
    r.require(has_main_guard(tree), 'STEP 3: the `if __name__ == "__main__":` line is uncommented')
    output_is(ws, r, rel, ["It takes 4 hits to win."])
