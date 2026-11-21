"""The if-statement, indentation and True/False-shortcut rules in the Pythonwood."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from azurath.checks import run_check
from azurath.content import load_dungeon
from azurath.dungeons.pythonwood.checks import tidy
from azurath.workspace import Workspace

PYTHONWOOD = load_dungeon("pythonwood")


def solution(room: str, name: str) -> str:
    return PYTHONWOOD.room_text(room, "solution", name)


def failures(room: str, ws: Workspace) -> list[str]:
    report = run_check(PYTHONWOOD, room, ws)
    return [
        f"{c.description}\n{c.detail or ''}" for c in report.items if not c.ok and not c.optional
    ]


def test_lessons_come_in_order() -> None:
    order = [r.id for r in PYTHONWOOD.ordered()]
    assert (
        order.index("variable_grove")
        < order.index("crossroads_guided")
        < order.index("crossroads")
        < order.index("function_falls_guided")
        < order.index("function_falls")
        < order.index("shortcut_trail_guided")
        < order.index("shortcut_trail")
        < order.index("testing_meadow_guided")
    )


# --- indentation --------------------------------------------------------------------------


def test_four_spaces_is_fine() -> None:
    src = "def f(x):\n    if x:\n        return 1\n    return 2\n"
    assert tidy.indentation_problems(src, "a.py") == []


@pytest.mark.parametrize(
    ("src", "clue"),
    [
        ("if True:\n  print(1)\n", "pushed in by 2 spaces, but it should be exactly 4"),
        ("def f():\n        return 1\n", "pushed in by 8 spaces, but it should be exactly 4"),
        ("if True:\n\tprint(1)\n", "TAB"),
        ("def f(x):\n    if x:\n      return 1\n", "should be exactly 8"),
    ],
)
def test_wrong_indentation_is_explained(src: str, clue: str) -> None:
    problems = tidy.indentation_problems(src, "a.py")
    assert any(clue in p for p in problems), problems


def test_lines_inside_brackets_and_strings_may_line_up_freely() -> None:
    src = (
        'def f():\n    text = """\n  any indent\n"""\n    pair = (1,\n  2)\n    return text, pair\n'
    )
    assert tidy.indentation_problems(src, "a.py") == []


# --- the True/False shortcut ----------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "def f(e):\n    if e < 20:\n        return True\n    else:\n        return False\n",
        "def f(e):\n    if e < 20:\n        return True\n    return False\n",
        "def f(e):\n    if e < 20:\n        return False\n    return True\n",
        "if is_sleepy == True:\n    pass\n",
        "ok = is_sleepy == False\n",
        "if is_sleepy is True:\n    pass\n",
    ],
)
def test_the_long_way_is_spotted(src: str) -> None:
    assert tidy.bool_shortcut_problems(ast.parse(src), "a.py")


@pytest.mark.parametrize(
    "src",
    [
        "def f(e):\n    return e < 20\n",
        "if is_sleepy:\n    pass\n",
        "def feed(h, s):\n    if h + s > 100:\n        return 100\n    return h + s\n",
        "def f(x):\n    if x:\n        print('hi')\n        return True\n    return False\n",
    ],
)
def test_the_shortcut_and_other_ifs_are_fine(src: str) -> None:
    assert tidy.bool_shortcut_problems(ast.parse(src), "a.py") == []


# --- the checks catch the classic mistakes ---------------------------------------------------


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(tmp_path)


def test_fork_off_we_go_inside_the_if_fails(ws: Workspace) -> None:
    good = solution("crossroads_guided", "fork.py")
    ws.write(
        "practice/fork.py",
        good.replace('\nprint("Off we go!")', '\n#     print("Off we go!")').replace(
            '# print("Off we go!")\n#     print("Off we go!")',
            '# print("Off we go!")\n    print("Off we go!")',
        ),
    )
    assert any("Off we go!" in f for f in failures("crossroads_guided", ws))


def test_fork_two_space_choice_is_an_indentation_error(ws: Workspace) -> None:
    good = solution("crossroads_guided", "fork.py")
    bad = good.replace('    print("Lots of acorns!")', '  print("Lots of acorns!")')
    ws.write("practice/fork.py", bad)
    found = failures("crossroads_guided", ws)
    assert any("valid Python" in f and "indent" in f.lower() for f in found), found


def test_mood_passes_with_the_solution(ws: Workspace) -> None:
    ws.write("mood.py", solution("crossroads", "mood.py"))
    assert failures("crossroads", ws) == []


def test_mood_in_the_wrong_order_fails(ws: Workspace) -> None:
    good = solution("crossroads", "mood.py")
    bad = good.replace("elif health < 20:", "elif health < 1:")
    ws.write("mood.py", bad)
    assert any("health = 10" in f for f in failures("crossroads", ws))


def test_mood_with_two_space_blocks_fails_the_ruler(ws: Workspace) -> None:
    bad = solution("crossroads", "mood.py").replace("\n    print", "\n  print")
    ws.write("mood.py", bad)
    found = failures("crossroads", ws)
    assert any("exactly 4 spaces" in f for f in found), found


def test_mood_done_inside_the_else_fails(ws: Workspace) -> None:
    bad = solution("crossroads", "mood.py").replace(
        '\n\nprint("Mood check done!")', '\n    print("Mood check done!")'
    )
    ws.write("mood.py", bad)
    assert any("Mood check done!" in f for f in failures("crossroads", ws))


def test_shortcut_trail_rejects_the_long_way(ws: Workspace) -> None:
    ws.write("actions.py", solution("function_falls", "actions.py"))  # is_tired via if/else
    ws.write("mood.py", solution("crossroads", "mood.py"))  # if is_sleepy == True:
    found = failures("shortcut_trail", ws)
    assert any("is_full" in f for f in found), found
    assert any("long-way" in f for f in found), found


def test_shortcut_trail_passes_with_the_solution(ws: Workspace) -> None:
    ws.write("actions.py", solution("shortcut_trail", "actions.py"))
    ws.write("mood.py", solution("shortcut_trail", "mood.py"))
    assert failures("shortcut_trail", ws) == []


def test_gap_long_way_choice_fails(ws: Workspace) -> None:
    bad = solution("shortcut_trail_guided", "gap.py").replace(
        "\nneeds_umbrella = is_raining\n", "\nneeds_umbrella = is_raining == True\n"
    )
    ws.write("practice/gap.py", bad)
    assert any("shortcut" in f for f in failures("shortcut_trail_guided", ws))
