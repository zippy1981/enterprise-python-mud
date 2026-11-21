"""Making sure git can save the player's work.

The game commits after every quest, so before play starts we check that git is
installed, that it actually runs (a broken ``~/.gitconfig`` makes every git
command fail), and that ``user.name`` and ``user.email`` are set globally:
without them ``git commit`` refuses to run. When a commit does fail later, the
error is classified so the player gets a specific explanation and, where it's
safe, an offer to fix it.
"""

from __future__ import annotations

import enum
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from azurath.workspace import RunResult

EMAIL = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")

INSTALL_HELP = {
    "win32": "Install it with `winget install --id Git.Git -e`, or from https://git-scm.com/downloads",
    "darwin": "Install it with `xcode-select --install` or `brew install git`",
    "linux": "Install it with your package manager, e.g. `sudo apt install git`",
}


def install_help() -> str:
    return INSTALL_HELP.get(sys.platform, INSTALL_HELP["linux"])


def run_git(*args: str, cwd: Path | None = None) -> RunResult:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return RunResult(127, "", "git is not installed")
    except subprocess.TimeoutExpired:
        return RunResult(124, "", f"git {' '.join(args)} timed out")
    return RunResult(proc.returncode, proc.stdout, proc.stderr)


@dataclass
class GitHealth:
    installed: bool
    version: str | None = None
    name: str | None = None
    email: str | None = None
    problem: str | None = None  # git ran but failed, e.g. a broken global config

    @property
    def has_identity(self) -> bool:
        return bool(self.name and self.email)

    @property
    def ok(self) -> bool:
        return self.installed and self.problem is None and self.has_identity


def _config_value(key: str) -> tuple[str | None, str | None]:
    """(value, problem). ``git config --get`` exits 1 when a key is simply unset."""
    res = run_git("config", "--global", "--get", key)
    if res.returncode == 0:
        return res.stdout.strip() or None, None
    if res.returncode == 1 and not res.stderr.strip():
        return None, None
    return None, res.tail(4) or f"git config failed (exit {res.returncode})"


def check_git() -> GitHealth:
    if shutil.which("git") is None:
        return GitHealth(installed=False)
    version = run_git("--version")
    if not version.ok:
        return GitHealth(installed=True, problem=version.tail(4) or "`git --version` failed")
    name, name_problem = _config_value("user.name")
    email, email_problem = _config_value("user.email")
    return GitHealth(
        installed=True,
        version=version.stdout.strip(),
        name=name,
        email=email,
        problem=name_problem or email_problem,
    )


def valid_name(text: str) -> bool:
    text = text.strip()
    return bool(text) and len(text) <= 100 and not any(c in text for c in "<>\n")


def valid_email(text: str) -> bool:
    return bool(EMAIL.match(text.strip()))


def set_global_identity(name: str, email: str) -> RunResult:
    """Run ``git config --global user.name/user.email``. Returns the first failure."""
    for key, value in (("user.name", name.strip()), ("user.email", email.strip())):
        res = run_git("config", "--global", key, value)
        if not res.ok:
            return res
    return RunResult(0, "", "")


def trust_directory(path: Path) -> RunResult:
    return run_git("config", "--global", "--add", "safe.directory", str(path))


class CommitFailure(enum.Enum):
    NO_GIT = "git isn't installed"
    NOT_A_REPO = "the project folder isn't a git repository"
    IDENTITY = "git doesn't know who you are (user.name / user.email)"
    LOCKED = "another git command left a lock file behind"
    DUBIOUS_OWNERSHIP = "git doesn't trust this folder (it's owned by another user)"
    OTHER = "git commit failed"


def classify_commit_failure(result: RunResult) -> CommitFailure:
    text = result.output.lower()
    if result.returncode == 127 or "git is not available" in text or "not installed" in text:
        return CommitFailure.NO_GIT
    if "dubious ownership" in text or "safe.directory" in text:
        return CommitFailure.DUBIOUS_OWNERSHIP
    if "not a git repository" in text or "not a git repo" in text:
        return CommitFailure.NOT_A_REPO
    if "index.lock" in text:
        return CommitFailure.LOCKED
    identity_clues = (
        "tell me who you are",
        "user.email",
        "user.name",
        "empty ident",
        "auto-detect",
    )
    if any(clue in text for clue in identity_clues):
        return CommitFailure.IDENTITY
    return CommitFailure.OTHER
