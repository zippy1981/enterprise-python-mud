import io
import os
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from rich.console import Console

from azurath.game import Game
from azurath.settings import AzurathSettings


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the player's real config, editor and git identity out of the tests."""
    for key in list(os.environ):
        if key.startswith(("AZURATH_", "QUESTBOARD_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Azurath Tests")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "tests@azurath.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Azurath Tests")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "tests@azurath.invalid")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    monkeypatch.chdir(tmp_path)


class Player:
    """Drives a Game like a person at the keyboard and captures what it prints."""

    def __init__(self, game: Game, buffer: io.StringIO, answers: list[str]) -> None:
        self.game = game
        self.buffer = buffer
        self.answers = answers

    def __call__(self, line: str) -> str:
        start = self.buffer.tell()
        self.game.handle(line)
        self.buffer.seek(start)
        out = self.buffer.read()
        self.buffer.seek(0, io.SEEK_END)
        return out


@pytest.fixture
def make_player(tmp_path: Path) -> Iterator[Callable[..., Player]]:
    def factory(auto_commit: bool = True, answers: list[str] | None = None) -> Player:
        buffer = io.StringIO()
        console = Console(file=buffer, width=140, color_system=None, force_terminal=False)
        queue = list(answers or [])

        def answer(prompt: str) -> str:
            return queue.pop(0) if queue else "y"

        settings = AzurathSettings(workspace=tmp_path / "questboard", auto_commit=auto_commit)
        game = Game(settings, console=console, input_fn=answer)
        game.ws.initialize()
        game.save()
        return Player(game, buffer, queue)

    yield factory


@pytest.fixture
def python_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Make `python` resolve to a real interpreter (CI images often only have python3)."""
    shim = tmp_path / "shim-bin"
    shim.mkdir()
    base = Path(getattr(sys, "_base_executable", sys.executable))
    target = shim / ("python.exe" if os.name == "nt" else "python")
    target.symlink_to(base)
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ.get('PATH', '')}")
    return shim
