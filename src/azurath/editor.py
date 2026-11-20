"""Opening files for editing: VS Code when you're in its terminal, else vim and friends."""

from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EditorChoice:
    argv: list[str]
    blocking: bool
    label: str


def in_vscode_terminal() -> bool:
    return os.environ.get("TERM_PROGRAM") == "vscode" or "VSCODE_IPC_HOOK_CLI" in os.environ


def _vscode_cli() -> str | None:
    return shutil.which("code") or shutil.which("code-insiders") or shutil.which("cursor")


def choose_editor(
    path: Path, configured: str | None = None, force: str | None = None
) -> EditorChoice | None:
    """Work out which editor to launch for ``path``.

    Priority: an explicit command (``vim foo.py``), then the ``AZURATH_EDITOR``
    setting, then VS Code if we're inside its integrated terminal, then
    ``$VISUAL``/``$EDITOR``, then whatever terminal editor is installed.
    """
    target = str(path)
    if force == "code":
        cli = _vscode_cli()
        return EditorChoice([cli, "-r", "-g", target], False, "VS Code") if cli else None
    if force:
        exe = shutil.which(force)
        return EditorChoice([exe, target], True, force) if exe else None

    if configured:
        argv = shlex.split(configured, posix=os.name != "nt")
        gui = Path(argv[0]).stem.lower() in {"code", "code-insiders", "cursor", "subl", "gedit"}
        blocking = not gui or "--wait" in argv or "-w" in argv
        return EditorChoice([*argv, target], blocking, argv[0])

    if in_vscode_terminal() and (cli := _vscode_cli()):
        return EditorChoice([cli, "-r", "-g", target], False, "VS Code")

    for var in ("VISUAL", "EDITOR"):
        if value := os.environ.get(var):
            argv = shlex.split(value, posix=os.name != "nt")
            return EditorChoice([*argv, target], True, argv[0])

    for name in ("vim", "nvim", "vi", "nano", "notepad"):
        if exe := shutil.which(name):
            return EditorChoice([exe, target], name != "notepad", name)
    return None


VIM_CHEATSHEET = """\
**vim survival kit**: you are in *normal* mode when vim opens.

| Keys | What it does | Closest thing in VS Code |
|------|--------------|--------------------------|
| `i` | insert mode (start typing) | click in the editor |
| `Esc` | back to normal mode | |
| `:w` Enter | save | Ctrl+S |
| `:wq` Enter | save and quit (back to the MUD) | |
| `:q!` Enter | quit **without** saving | close + Don't Save |
| `u` / `Ctrl+r` | undo / redo | Ctrl+Z / Ctrl+Y |
| `/text` Enter | search, `n` for next | Ctrl+F |
| `dd` / `p` | cut line / paste | Ctrl+X / Ctrl+V |
| `:set paste` | stop auto-indent mangling pasted code | |
"""
