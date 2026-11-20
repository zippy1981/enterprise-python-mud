"""Shared helpers for checks that run the player's pytest suite."""

from __future__ import annotations

import ast
import shutil
import tempfile
from pathlib import Path

from azurath.checks import Report
from azurath.workspace import Workspace

__test__ = False  # tell pytest the `test_*` helpers below are not tests


def _copy_workspace(ws: Workspace, dest: Path) -> None:
    shutil.copytree(
        ws.root,
        dest,
        ignore=shutil.ignore_patterns(
            ".venv",
            ".git",
            ".azurath",
            "__pycache__",
            "*.so",
            "*.dll",
            "*.dylib",
            "*.pyd",
            "node_modules",
            ".pytest_cache",
        ),
        dirs_exist_ok=True,
    )


def mutation_survives(
    ws: Workspace, test_file: str, module_rel: str, mutant: str
) -> tuple[bool, str]:
    """Run ``test_file`` against a mutated copy of the workspace. True means the mutant *survived*."""
    with tempfile.TemporaryDirectory(prefix="azurath-mutant-") as tmp:
        dest = Path(tmp) / "ws"
        _copy_workspace(ws, dest)
        target = dest / module_rel
        target.write_text(target.read_text(encoding="utf-8") + mutant, encoding="utf-8")
        res = ws.run(
            [ws.python(), "-m", "pytest", "-q", "-p", "no:cacheprovider", test_file], cwd=dest
        )
        return res.returncode != 1, res.tail(8)


def test_functions(tree: ast.Module) -> list[str]:
    return [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test")
    ]


def parametrize_case_counts(tree: ast.Module) -> list[int]:
    counts = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and "parametrize" in ast.unparse(node.func)
            and len(node.args) >= 2
        ):
            values = node.args[1]
            if isinstance(values, ast.List | ast.Tuple):
                counts.append(len(values.elts))
            else:
                counts.append(3)  # computed lists: give the benefit of the doubt
    return counts


def run_pytest(ws: Workspace, r: Report, target: str, description: str) -> bool:
    res = ws.run([ws.python(), "-m", "pytest", "-q", "-p", "no:cacheprovider", target], timeout=600)
    if res.returncode == 5:
        return r.require(False, description, "pytest collected no tests")
    return r.require(res.ok, description, res.tail(20))


def stub_out(names: list[str]) -> str:
    """Source that replaces each named function with one that does nothing useful.

    Appending it to a module simulates "the code isn't written yet": a test
    that still passes against it can't be testing anything (TDD's red step).
    """
    return "".join(
        f"\n\ndef {name}(*args, **kwargs):  # stub injected by the runes\n    return None\n"
        for name in names
    )
