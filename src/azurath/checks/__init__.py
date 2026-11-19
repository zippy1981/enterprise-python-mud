"""Quest checks: small functions that inspect the player's workspace.

Each room's quest names a check (``check: venv_crypt`` in its YAML). Checks
register themselves with the ``@check`` decorator into ``REGISTRY``, a plain
dict. Decorator-based registration like this is everywhere in Python: pytest
fixtures, FastAPI routes and Azure Functions triggers all work this way. The C#
equivalent is attribute scanning with reflection, without the reflection.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, field

from azurath.workspace import ProbeResult, Workspace


@dataclass
class Criterion:
    description: str
    ok: bool
    detail: str | None = None
    optional: bool = False


@dataclass
class Report:
    items: list[Criterion] = field(default_factory=list)

    def require(self, ok: bool, description: str, detail: str | None = None) -> bool:
        self.items.append(Criterion(description, bool(ok), None if ok else detail))
        return bool(ok)

    def suggest(self, ok: bool, description: str, detail: str | None = None) -> bool:
        self.items.append(Criterion(description, bool(ok), None if ok else detail, optional=True))
        return bool(ok)

    def probe(self, result: ProbeResult, description: str) -> bool:
        if result.crashed:
            return self.require(False, description, result.output)
        return self.require(result.ok, description, "\n".join(result.failures))

    def file(self, ws: Workspace, rel: str, hint: str | None = None) -> bool:
        return self.require(
            ws.exists(rel), f"`{rel}` exists", hint or "Try `scaffold` for a starter."
        )

    def python_file(self, ws: Workspace, rel: str) -> ast.Module | None:
        """Require that ``rel`` exists and parses. Returns the AST or None."""
        if not self.file(ws, rel):
            return None
        tree, error = ws.parse(rel)
        self.require(tree is not None, f"`{rel}` is valid Python", error)
        return tree

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.items if not c.optional)


CheckFn = Callable[[Workspace, Report], None]
REGISTRY: dict[str, CheckFn] = {}


def check(name: str) -> Callable[[CheckFn], CheckFn]:
    def register(fn: CheckFn) -> CheckFn:
        if name in REGISTRY:
            raise ValueError(f"duplicate check {name}")
        REGISTRY[name] = fn
        return fn

    return register


def run_check(name: str, ws: Workspace) -> Report:
    _load_all()
    report = Report()
    fn = REGISTRY.get(name)
    if fn is None:
        report.require(False, f"check {name!r} exists", "This is a bug in the game content.")
        return report
    try:
        fn(ws, report)
    except Exception as exc:  # a bug in a check shouldn't kill the game
        report.require(False, "the check ran", f"{type(exc).__name__}: {exc}")
    return report


def _load_all() -> None:
    # Importing the modules runs their @check decorators.
    from azurath.checks import azure, domain, foundations, golang, packaging  # noqa: F401


# --- small AST helpers shared by checks -----------------------------------------


def defined_functions(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def defined_classes(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}


def imported_modules(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def dotted(node: ast.AST) -> str:
    """``a.b.c`` for Attribute/Name chains, '' otherwise."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return ""


def calls(tree: ast.AST) -> list[str]:
    return [dotted(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]


def decorator_names(fn: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    return [dotted(d) for d in fn.decorator_list]


def has_main_guard(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
            names = {dotted(node.test.left)} | {dotted(c) for c in node.test.comparators}
            consts = {c.value for c in node.test.comparators if isinstance(c, ast.Constant)}
            if isinstance(node.test.left, ast.Constant):
                consts.add(node.test.left.value)
            if "__name__" in names and "__main__" in consts:
                return True
    return False
