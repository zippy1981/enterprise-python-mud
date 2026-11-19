"""Checks for TOML, uv, pytest and CI/CD."""

from __future__ import annotations

import ast
import re
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import yaml

from azurath.checks import Report, calls, check
from azurath.workspace import Workspace

_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_names(reqs: list[Any]) -> set[str]:
    names = set()
    for req in reqs:
        if isinstance(req, str) and (m := _NAME.match(req)):
            names.add(normalize(m.group(1)))
    return names


def load_pyproject(ws: Workspace, r: Report | None = None) -> dict[str, Any] | None:
    text = ws.read("pyproject.toml")
    if text is None:
        if r:
            r.require(False, "`pyproject.toml` exists", "Back to the TOML Forge with you.")
        return None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        if r:
            r.require(False, "`pyproject.toml` is valid TOML", str(exc))
        return None
    if r:
        r.require(True, "`pyproject.toml` is valid TOML")
    return data


def runtime_deps(pyproject: dict[str, Any]) -> set[str]:
    return requirement_names(pyproject.get("project", {}).get("dependencies", []) or [])


def dev_deps(pyproject: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    groups = pyproject.get("dependency-groups", {}) or {}
    for name in ("dev", "test", "lint"):
        found |= requirement_names(groups.get(name, []) or [])
    found |= requirement_names(
        pyproject.get("tool", {}).get("uv", {}).get("dev-dependencies", []) or []
    )
    found |= requirement_names(
        pyproject.get("project", {}).get("optional-dependencies", {}).get("dev", []) or []
    )
    return found


@check("toml_forge")
def toml_forge(ws: Workspace, r: Report) -> None:
    data = load_pyproject(ws, r)
    if data is None:
        return
    project = data.get("project")
    if not r.require(isinstance(project, dict), "there is a `[project]` table"):
        return
    r.require(
        normalize(str(project.get("name", ""))) == "questboard",
        '`name = "questboard"`',
        f"found {project.get('name')!r}",
    )
    version = project.get("version")
    r.require(
        (
            isinstance(version, str)
            and re.fullmatch(r"\d+(\.\d+)*([abrc]+\d+)?(\.post\d+)?(\.dev\d+)?", version)
        )
        or "version" in project.get("dynamic", []),
        '`version` is a valid version string (e.g. `"0.1.0"`)',
        f"found {version!r}",
    )
    r.require(bool(project.get("description")), "there is a `description`")
    rp = project.get("requires-python")
    r.require(
        isinstance(rp, str) and re.search(r"[<>=~]=?\s*3\.\d+", rp or ""),
        '`requires-python` is set (e.g. `">=3.11"`)',
        f"found {rp!r}",
    )
    r.require(
        isinstance(project.get("dependencies"), list),
        "`dependencies` is an array (may be empty)",
        "`dependencies = []`",
    )
    build = data.get("build-system", {})
    r.require(
        build.get("build-backend") == "hatchling.build",
        '`[build-system]` uses `build-backend = "hatchling.build"`',
        f"found {build.get('build-backend')!r}",
    )
    r.require(
        any("hatchling" in str(x) for x in build.get("requires", [])),
        "`[build-system]` requires `hatchling`",
    )
    pytest_opts = data.get("tool", {}).get("pytest", {}).get("ini_options", {})
    r.require(
        "tests" in (pytest_opts.get("testpaths") or []),
        '`[tool.pytest.ini_options]` has `testpaths = ["tests"]`',
    )
    init = ws.read("questboard/__init__.py") or ""
    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", init)
    if match and isinstance(version, str):
        r.suggest(
            match.group(1) == version,
            "`questboard.__version__` matches the pyproject version",
            f"{match.group(1)} vs {version}. `ask tomasz about version` for how to single-source it.",
        )


@check("uv_speedway")
def uv_speedway(ws: Workspace, r: Report) -> None:
    uv = shutil.which("uv")
    r.require(
        uv is not None, "`uv` is installed", "`ask astral about install`, then restart the MUD."
    )
    data = load_pyproject(ws, r)
    if data is None:
        return
    deps = runtime_deps(data)
    missing = {"pydantic", "pydantic-settings", "pyyaml"} - deps
    r.require(
        not missing,
        "runtime dependencies include pydantic, pydantic-settings and pyyaml",
        "missing: " + ", ".join(sorted(missing)) + ". Use `!uv add ...`.",
    )
    dev = dev_deps(data)
    missing_dev = {"pytest", "ruff"} - dev
    r.require(
        not missing_dev,
        "dev dependencies include pytest and ruff",
        "missing: " + ", ".join(sorted(missing_dev)) + ". Use `!uv add --dev ...`.",
    )
    leaked = {"pytest", "ruff"} & deps
    r.require(
        not leaked,
        "pytest/ruff are dev-only (not runtime dependencies)",
        "Move them: `!uv remove " + " ".join(sorted(leaked)) + "` then `!uv add --dev ...`",
    )
    r.require(ws.exists("uv.lock"), "`uv.lock` exists", "`!uv lock` (or any `uv add`) creates it.")
    venv = ws.venv_python()
    if r.require(venv is not None, "`.venv` exists", "`!uv sync`"):
        imp = ws.run(
            [str(venv), "-c", "import pydantic, pydantic_settings, yaml, pytest; print('ok')"]
        )
        r.require(
            imp.ok,
            "`.venv` has pydantic, pydantic-settings, PyYAML and pytest installed",
            imp.tail(4) + "\nRun `!uv sync`.",
        )
    r.require(
        not ws.exists("requirements.txt"),
        "the hand-made `requirements.txt` is gone",
        "pyproject.toml + uv.lock are the source of truth now: `!git rm requirements.txt`",
    )
    r.suggest(
        ws.exists(".python-version"),
        "Python version pinned in `.python-version`",
        "`!uv python pin 3.12`",
    )


MUTANTS = {
    "slugify": "\n\ndef slugify(title):  # mutant injected by the runes\n    return title.lower()\n",
    "parse_rank": "\n\ndef parse_rank(text):  # mutant injected by the runes\n    return text.strip().upper()\n",
}


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


@check("testing_grounds")
def testing_grounds(ws: Workspace, r: Report) -> None:
    rel = "tests/test_text.py"
    tree = r.python_file(ws, rel)
    if tree is None:
        return
    tests = test_functions(tree)
    r.require(
        len(tests) >= 4,
        "at least 4 test functions",
        f"found {len(tests)}: {', '.join(tests) or 'none'}",
    )
    counts = parametrize_case_counts(tree)
    r.require(
        any(c >= 3 for c in counts),
        "a `@pytest.mark.parametrize` with 3+ cases",
        f"parametrize case counts found: {counts or 'none'}",
    )
    r.require(any(c.endswith("raises") for c in calls(tree)), "uses `pytest.raises`")
    venv = ws.venv_python()
    if not r.require(venv is not None, "a `.venv` to run pytest in", "`!uv sync`"):
        return
    if not run_pytest(ws, r, rel, "all tests pass"):
        return
    for name, mutant in MUTANTS.items():
        survived, output = mutation_survives(ws, rel, "questboard/text.py", mutant)
        r.require(
            not survived,
            f"your tests catch a broken `{name}`",
            f"The runes replaced {name} with a wrong version and your tests still passed.\n{output}",
        )


# --- CI/CD -----------------------------------------------------------------------------


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for job in (workflow.get("jobs") or {}).values():
        if isinstance(job, dict):
            steps.extend(s for s in job.get("steps") or [] if isinstance(s, dict))
    return steps


@check("cicd_foundry")
def cicd_foundry(ws: Workspace, r: Report) -> None:
    rel = ".github/workflows/ci.yml"
    if not ws.exists(rel) and ws.exists(".github/workflows/ci.yaml"):
        rel = ".github/workflows/ci.yaml"
    if not r.file(ws, rel):
        return
    try:
        workflow = yaml.safe_load(ws.read(rel) or "")
    except yaml.YAMLError as exc:
        r.require(False, f"`{rel}` is valid YAML", str(exc))
        return
    if not r.require(isinstance(workflow, dict), f"`{rel}` is a YAML mapping"):
        return
    # PyYAML is YAML 1.1: the key `on` is parsed as the boolean True. (See the YAML Scriptorium!)
    triggers = workflow.get("on", workflow.get(True))
    trigger_names = set(triggers) if isinstance(triggers, dict | list) else {triggers}
    r.require(
        bool({"push", "pull_request"} & trigger_names),
        "runs `on` push and/or pull_request",
        f"triggers found: {trigger_names}",
    )
    steps = _steps(workflow)
    uses = [str(s.get("uses", "")) for s in steps]
    runs = "\n".join(str(s.get("run", "")) for s in steps)
    r.require(
        any(u.startswith("actions/checkout") for u in uses),
        "checks out the code (`actions/checkout`)",
    )
    r.require(
        any(u.startswith("astral-sh/setup-uv") for u in uses), "installs uv (`astral-sh/setup-uv`)"
    )
    r.require(re.search(r"uv\s+sync[^\n]*--(locked|frozen)", runs), "runs `uv sync --locked`")
    r.require(re.search(r"ruff\s+check", runs), "runs `ruff check`")
    r.require("pytest" in runs, "runs `pytest`")

    pyproject = load_pyproject(ws) or {}
    has_config = (
        "ruff" in pyproject.get("tool", {}) or ws.exists("ruff.toml") or ws.exists(".ruff.toml")
    )
    r.require(has_config, "ruff is configured (`[tool.ruff]` in pyproject.toml or a `ruff.toml`)")
    if ws.venv_python():
        lint = ws.run([ws.python(), "-m", "ruff", "check", "."])
        r.require(
            lint.ok,
            "`ruff check .` passes on your code",
            lint.tail(20) + "\nTry `!uv run ruff check --fix .`",
        )
        fmt = ws.run([ws.python(), "-m", "ruff", "format", "--check", "."])
        r.suggest(fmt.ok, "`ruff format --check .` passes", "`!uv run ruff format .`")
    if ws.is_git_repo():
        remote = ws.git("remote", "-v")
        r.suggest(
            remote.ok and "origin" in remote.stdout,
            "pushed to GitHub (an `origin` remote exists)",
            "`ask ruff about github` for how to publish your repo.",
        )
