"""Tidy-code rules for the Pythonwood: names, docstrings, short functions, no magic numbers.

Each helper returns a list of plain-language problems (empty means tidy), so a
check can show a young player exactly what to fix.
"""

from __future__ import annotations

import ast
import re

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
CONSTANT_CASE = re.compile(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$")

Function = ast.FunctionDef | ast.AsyncFunctionDef


def functions(tree: ast.Module) -> list[Function]:
    return [n for n in ast.walk(tree) if isinstance(n, Function)]


def top_level_names(tree: ast.Module) -> list[str]:
    """Variable names assigned at the top of a file (not inside functions)."""
    names: list[str] = []
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if isinstance(node, ast.AnnAssign | ast.AugAssign):
            targets = [node.target]
        names.extend(t.id for t in targets if isinstance(t, ast.Name))
    return names


def name_problems(names: list[str]) -> list[str]:
    problems = []
    for name in dict.fromkeys(names):  # keep order, drop repeats
        if CONSTANT_CASE.match(name):
            continue  # a CAPITALS setting is fine
        if len(name) < 3:
            problems.append(f"`{name}` is too short to explain itself; try a longer, clearer name")
        elif not SNAKE_CASE.match(name):
            problems.append(f"`{name}` isn't snake_case (lowercase words joined by underscores)")
    return problems


def missing_docstrings(tree: ast.Module, rel: str) -> list[str]:
    return [
        f"`{fn.name}()` in {rel} (line {fn.lineno}) has no docstring"
        for fn in functions(tree)
        if not ast.get_docstring(fn)
    ]


def long_functions(tree: ast.Module, rel: str, limit: int = 25) -> list[str]:
    problems = []
    for fn in functions(tree):
        length = (fn.end_lineno or fn.lineno) - fn.lineno + 1
        if length > limit:
            problems.append(
                f"`{fn.name}()` in {rel} is {length} lines long (the limit is {limit}); "
                "split it into smaller helper functions"
            )
    return problems


def magic_numbers(tree: ast.Module, numbers: set[int]) -> list[str]:
    """Places where one of ``numbers`` appears as a bare literal inside a function."""
    found = []
    for fn in functions(tree):
        for node in ast.walk(fn):
            if isinstance(node, ast.Constant) and type(node.value) is int and node.value in numbers:
                found.append(f"line {node.lineno}: `{node.value}` (give it a name in rules.py)")
    return found


def prints_inside_functions(tree: ast.Module) -> list[str]:
    return [
        f"`{fn.name}()` calls print() (line {node.lineno}); return the value instead"
        for fn in functions(tree)
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def has_loop(tree: ast.AST) -> bool:
    return any(isinstance(n, ast.For | ast.While | ast.comprehension) for n in ast.walk(tree))
