"""The player's workspace: the git repo they build while playing.

Checks never ``import`` the player's code into the game process. They run it in
a subprocess using the workspace's own ``.venv`` interpreter when one exists, so
a typo in the player's code can't crash the game and the game's dependencies
never leak into the player's project.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".azurath",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    ".python_packages",
}

INITIAL_GITIGNORE = """\
# Azurath keeps your save game here. It is not part of your project.
.azurath/

# Python bytecode caches (like bin/ and obj/ in .NET)
__pycache__/
*.py[cod]
"""

INITIAL_README = """\
# questboard

A guild quest board service, built while playing **Azurath**, the enterprise
Python MUD.

Every commit in this repository is a lesson you completed.
"""

PROBE_MARKER = "@@AZURATH@@"

PROBE_TEMPLATE = """\
import json as _json, sys as _sys, traceback as _tb, os as _os
_sys.path.insert(0, _os.getcwd())
_failures = []

def expect(cond, message):
    if not cond:
        _failures.append(str(message))
    return bool(cond)

def _where(exc):
    root = _os.getcwd()
    for frame in reversed(_tb.extract_tb(exc.__traceback__)):
        if frame.filename.startswith(root) and ".venv" not in frame.filename:
            return f" (at {{_os.path.relpath(frame.filename, root)}}:{{frame.lineno}})"
    return ""

def _main():
{body}

try:
    _main()
except BaseException as _e:  # report, never crash silently
    _msg = "".join(_tb.format_exception_only(type(_e), _e)).strip()
    _failures.append("Unexpected error: " + _msg + _where(_e))
print("\\n{marker}" + _json.dumps(_failures))
"""


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        return (self.stdout + ("\n" if self.stdout and self.stderr else "") + self.stderr).strip()

    def tail(self, lines: int = 15) -> str:
        return "\n".join(self.output.splitlines()[-lines:])


@dataclass
class ProbeResult:
    failures: list[str] = field(default_factory=list)
    crashed: bool = False
    output: str = ""

    @property
    def ok(self) -> bool:
        return not self.crashed and not self.failures


def _without_game_venv(env: dict[str, str]) -> dict[str, str]:
    """Strip the *game's* virtualenv from PATH so player commands use their own."""
    env = dict(env)
    for var in ("VIRTUAL_ENV", "VIRTUAL_ENV_PROMPT", "PYTHONHOME", "PYTHONPATH", "CONDA_PREFIX"):
        env.pop(var, None)
    if sys.prefix != sys.base_prefix:
        game_bin = str(Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin"))
        parts = env.get("PATH", "").split(os.pathsep)
        env["PATH"] = os.pathsep.join(
            p for p in parts if os.path.normcase(p) != os.path.normcase(game_bin)
        )
    return env


class Workspace:
    """Helpers for inspecting and running code in the player's repo."""

    def __init__(self, root: Path) -> None:
        self.root = root

    # --- files ---------------------------------------------------------------

    def path(self, rel: str) -> Path:
        return self.root / rel

    def exists(self, rel: str) -> bool:
        return self.path(rel).exists()

    def read(self, rel: str) -> str | None:
        p = self.path(rel)
        if not p.is_file():
            return None
        try:
            return p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return p.read_text(encoding="utf-8", errors="replace")

    def write(self, rel: str, content: str) -> Path:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
        return p

    def parse(self, rel: str) -> tuple[ast.Module | None, str | None]:
        """Parse a Python file. Returns ``(tree, error_message)``."""
        source = self.read(rel)
        if source is None:
            return None, f"{rel} does not exist"
        try:
            return ast.parse(source, filename=rel), None
        except SyntaxError as exc:
            return None, f"SyntaxError in {rel} line {exc.lineno}: {exc.msg}"

    def files(self, sub: str = "") -> list[str]:
        """Project files (relative, posix-style), skipping caches and venvs."""
        base = self.path(sub) if sub else self.root
        out: list[str] = []
        if not base.exists():
            return out
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
            for name in sorted(filenames):
                full = Path(dirpath) / name
                out.append(full.relative_to(self.root).as_posix())
        return out

    def gitignore_patterns(self) -> list[str]:
        text = self.read(".gitignore") or ""
        return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]

    # --- interpreters & environment ---------------------------------------------

    def venv_dir(self) -> Path:
        return self.root / ".venv"

    def venv_python(self) -> Path | None:
        candidates = [
            self.venv_dir() / "bin" / "python",
            self.venv_dir() / "Scripts" / "python.exe",
        ]
        return next((c for c in candidates if c.exists()), None)

    def python(self) -> str:
        """The interpreter checks should use: the project's venv if it has one."""
        venv = self.venv_python()
        return str(venv) if venv else sys.executable

    def env(self, extra: dict[str, str] | None = None, *, activate: bool = True) -> dict[str, str]:
        """Environment for running player commands, with their .venv 'activated'."""
        env = _without_game_venv(dict(os.environ))
        venv = self.venv_python()
        if activate and venv:
            env["VIRTUAL_ENV"] = str(self.venv_dir())
            env["PATH"] = str(venv.parent) + os.pathsep + env.get("PATH", "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.setdefault("PYTHONIOENCODING", "utf-8")
        if extra:
            env.update(extra)
        return env

    # --- running ----------------------------------------------------------------

    def run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 300,
    ) -> RunResult:
        try:
            proc = subprocess.run(
                args,
                cwd=cwd or self.root,
                env=self.env(env),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return RunResult(127, "", f"command not found: {args[0]}")
        except subprocess.TimeoutExpired:
            return RunResult(124, "", f"timed out after {timeout:.0f}s: {' '.join(args)}")
        return RunResult(proc.returncode, proc.stdout, proc.stderr)

    def run_python(
        self, *args: str, env: dict[str, str] | None = None, timeout: float = 120
    ) -> RunResult:
        return self.run([self.python(), *args], env=env, timeout=timeout)

    def probe(
        self, body: str, *, env: dict[str, str] | None = None, timeout: float = 60
    ) -> ProbeResult:
        """Run ``body`` in the workspace interpreter. ``expect(cond, msg)`` records failures."""
        script = PROBE_TEMPLATE.format(
            body=textwrap.indent(textwrap.dedent(body).strip("\n"), "    "),
            marker=PROBE_MARKER,
        )
        result = self.run_python("-c", script, env=env, timeout=timeout)
        out = result.stdout
        if PROBE_MARKER in out:
            before, _, data = out.rpartition(PROBE_MARKER)
            try:
                failures = json.loads(data.strip().splitlines()[0])
            except (json.JSONDecodeError, IndexError):
                return ProbeResult(crashed=True, output=result.tail())
            return ProbeResult(failures=failures, output=before.strip())
        return ProbeResult(crashed=True, output=result.tail() or "the probe produced no output")

    # --- git --------------------------------------------------------------------

    @staticmethod
    def git_available() -> bool:
        return shutil.which("git") is not None

    def git(self, *args: str) -> RunResult:
        return self.run(["git", *args], timeout=60)

    def is_git_repo(self) -> bool:
        return (self.root / ".git").exists()

    def initialize(self) -> list[str]:
        """Create the workspace folder and git repo. Returns human-readable notes."""
        notes: list[str] = []
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.exists(".gitignore"):
            self.write(".gitignore", INITIAL_GITIGNORE)
            notes.append("wrote .gitignore")
        if not self.exists("README.md"):
            self.write("README.md", INITIAL_README)
            notes.append("wrote README.md")
        if self.git_available() and not self.is_git_repo():
            res = self.git("init", "-b", "main")
            if not res.ok:  # very old git without -b
                res = self.git("init")
            notes.append("git init" if res.ok else f"git init failed: {res.tail()}")
            if res.ok:
                commit = self.commit("Enter the realm of Azurath")
                if commit and not commit.ok:
                    notes.append(commit.tail())
        return notes

    def commit(self, message: str) -> RunResult | None:
        """``git add -A && git commit``. Returns None when there's nothing to commit."""
        if not self.git_available() or not self.is_git_repo():
            return RunResult(1, "", "git is not available or this folder is not a git repo")
        add = self.git("add", "-A")
        if not add.ok:
            return add
        status = self.git("status", "--porcelain")
        if status.ok and not status.stdout.strip():
            return None
        return self.git("commit", "-q", "-m", message)

    def git_ignores(self, rel: str) -> bool:
        if not self.git_available() or not self.is_git_repo():
            return rel.rstrip("/") in {p.rstrip("/") for p in self.gitignore_patterns()}
        return self.git("check-ignore", "-q", rel).ok

    def git_tracks(self, rel: str) -> bool:
        res = self.git("ls-files", "--", rel)
        return res.ok and bool(res.stdout.strip())

    # --- interactive shell ------------------------------------------------------

    def shell_argv(self, command: str | None, configured: str | None = None) -> list[str]:
        """Build argv for running ``command`` (or an interactive shell) in the user's shell."""
        if configured:
            shell = configured
        elif os.name == "nt":
            shell = shutil.which("pwsh") or shutil.which("powershell") or "cmd"
        else:
            shell = os.environ.get("SHELL") or "/bin/sh"
        name = Path(shell).stem.lower()
        if command is None:
            return [shell]
        if name in {"pwsh", "powershell"}:
            return [shell, "-NoLogo", "-NoProfile", "-Command", command]
        if name == "cmd":
            return [shell, "/c", command]
        return [shell, "-c", command]

    def interactive(self, argv: list[str]) -> int:
        """Run a command attached to the real terminal (editors, shells, pytest output)."""
        try:
            return subprocess.call(argv, cwd=self.root, env=self.env())
        except FileNotFoundError:
            return 127
        except KeyboardInterrupt:
            return 130
