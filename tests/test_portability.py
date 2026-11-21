"""Cross-platform rules from CLAUDE.md: no symlinks, and deletions that work on Windows."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from azurath.workspace import remove_tree, write_python_shim

ROOT = Path(__file__).parents[1]
SYMLINK_CALL = re.compile(r"\.symlink_to\(|os\.symlink\(|\bln\s+-s\b|\bmklink\b")
SOURCE_SUFFIXES = {".py", ".sh", ".ps1", ".yml", ".yaml", ".toml", ".cmd", ".bat"}


def tracked_files() -> list[tuple[str, str]]:
    """(mode, path) for every file git tracks."""
    res = subprocess.run(
        ["git", "ls-files", "-s"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    rows = []
    for line in res.stdout.splitlines():
        meta, _, path = line.partition("\t")
        rows.append((meta.split()[0], path))
    return rows


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs a git checkout"
)


def test_no_symlinks_are_committed() -> None:
    links = [path for mode, path in tracked_files() if mode == "120000"]
    assert not links, f"symlinks are not allowed (see CLAUDE.md): {links}"


def test_no_code_creates_symlinks() -> None:
    offenders = []
    for _, path in tracked_files():
        if Path(path).suffix not in SOURCE_SUFFIXES or path == "tests/test_portability.py":
            continue
        text = (ROOT / path).read_text(encoding="utf-8", errors="replace")
        offenders += [
            f"{path}:{n}"
            for n, line in enumerate(text.splitlines(), 1)
            if SYMLINK_CALL.search(line)
        ]
    assert not offenders, f"don't create symlinks (see CLAUDE.md): {offenders}"


def test_python_shim_runs_the_interpreter(tmp_path: Path) -> None:
    shim = write_python_shim(tmp_path, sys.executable)
    assert not shim.is_symlink()
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"}
    out = subprocess.run(
        "python -c \"print('shim ok')\"", shell=True, env=env, capture_output=True, text=True
    )
    assert out.returncode == 0 and "shim ok" in out.stdout, out.stderr


def test_remove_tree_deletes_read_only_git_objects(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.txt").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)  # writes a read-only object
    readonly = tmp_path / "locked.txt"
    readonly.write_text("x", encoding="utf-8")
    readonly.chmod(0o444)
    remove_tree(repo)
    assert not repo.exists()
    remove_tree(tmp_path / "does-not-exist")  # missing paths are fine
