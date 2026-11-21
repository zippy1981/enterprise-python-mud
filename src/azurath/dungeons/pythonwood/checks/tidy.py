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


def values_in_fstring_braces(tree: ast.Module) -> list[str]:
    """f-string ``{...}`` slots holding a plain value (``{30}``, ``{"Sparky"}``) instead of a name."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and isinstance(node.value, ast.Constant):
            found.append(
                f"line {node.lineno}: `{{{node.value.value!r}}}` has a value in the braces. "
                "Put the variable's NAME there instead, like `{health}`"
            )
    return found


def indentation_problems(source: str, rel: str) -> list[str]:
    """Blocks that aren't indented with exactly 4 more spaces than the line that opens them.

    Python itself accepts any consistent indent (2 spaces, a tab, 8 spaces), but the
    Pythonwood insists on 4 spaces, the way almost every Python project does. Only the
    lines that *start* a block are checked, so lines that carry on inside brackets or a
    triple-quoted string may line up however they like.
    """
    import io
    import tokenize

    problems: list[str] = []
    levels = [0]
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return problems  # the "valid Python" check explains this one
    for tok in tokens:
        if tok.type == tokenize.INDENT:
            line = tok.start[0]
            if "\t" in tok.string:
                problems.append(
                    f"{rel} line {line} is indented with a TAB. Use 4 spaces instead "
                    "(in VS Code, the Tab key types 4 spaces for you in a .py file)"
                )
                levels.append(levels[-1] + 4)
                continue
            width, want = len(tok.string), levels[-1] + 4
            if width != want:
                problems.append(
                    f"{rel} line {line} is pushed in by {width} spaces, but it should be "
                    f"exactly {want} (4 more than the line that starts its block)"
                )
            levels.append(want)  # judge the lines inside by where this one should be
        elif tok.type == tokenize.DEDENT:
            levels.pop()
    return problems


def bool_shortcut_problems(tree: ast.Module, rel: str) -> list[str]:
    """Long ways of writing a True/False answer that have a shortcut.

    * ``if x < 20: return True`` / ``else: return False`` is just ``return x < 20``
    * ``x == True`` is just ``x``, and ``x == False`` is ``not x``
    """

    def returns_bool(body: list[ast.stmt]) -> bool | None:
        if len(body) == 1 and isinstance(body[0], ast.Return):
            value = body[0].value
            if isinstance(value, ast.Constant) and type(value.value) is bool:
                return value.value
        return None

    problems: list[str] = []
    for fn in functions(tree):
        statements = fn.body
        for i, node in enumerate(statements):
            if not isinstance(node, ast.If):
                continue
            first = returns_bool(node.body)
            other = returns_bool(node.orelse) if node.orelse else None
            if other is None and not node.orelse and i + 1 < len(statements):
                other = returns_bool([statements[i + 1]])
            if first is not None and other is not None and first != other:
                answer = "the comparison" if first else "`not` the comparison"
                problems.append(
                    f"`{fn.name}()` in {rel} (line {node.lineno}) uses an if to return True or "
                    f"False. Return {answer} directly, like `return energy < 20`"
                )
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for op, right in zip(node.ops, node.comparators, strict=True):
                if (
                    isinstance(op, ast.Eq | ast.NotEq | ast.Is | ast.IsNot)
                    and isinstance(right, ast.Constant)
                    and type(right.value) is bool
                ):
                    problems.append(
                        f"{rel} line {node.lineno} compares with `{right.value}`. "
                        "`if is_sleepy:` already means 'if it's True' "
                        "(and `if not is_sleepy:` means 'if it's False')"
                    )
    return problems
