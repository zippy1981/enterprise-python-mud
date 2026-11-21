"""Ctrl+C needs two presses in a row to quit; during a command it only stops that command."""

import io
from collections.abc import Iterable
from pathlib import Path

import pytest
from rich.console import Console

from azurath import game as game_module
from azurath.content import load_dungeon
from azurath.game import Game
from azurath.settings import AzurathSettings


class Keyboard:
    """Feeds the game's prompt: strings are typed lines, exception classes are key presses."""

    def __init__(self, keys: Iterable[object]) -> None:
        self.keys = list(keys)
        self.prompts = 0

    def __call__(self, prompt: str) -> str:
        self.prompts += 1
        if not self.keys:
            raise AssertionError("the game asked for more input than the test provided")
        key = self.keys.pop(0)
        if isinstance(key, type) and issubclass(key, BaseException):
            raise key
        return str(key)


def play(tmp_path: Path, keys: list[object]) -> tuple[str, Keyboard]:
    buffer = io.StringIO()
    keyboard = Keyboard(["y", "Ada", *keys])  # create the workspace, name, then the keys
    game = Game(
        AzurathSettings(workspace=tmp_path / "project"),
        console=Console(file=buffer, width=140, color_system=None),
        input_fn=keyboard,
        dungeon=load_dungeon("pythonwood"),
    )
    game.run()
    return buffer.getvalue(), keyboard


def test_one_ctrl_c_warns_and_keeps_playing(tmp_path: Path) -> None:
    out, keyboard = play(tmp_path, [KeyboardInterrupt, "look", "quit"])
    assert "Press Ctrl+C again to quit" in out
    assert out.count("Farewell") == 1 and not keyboard.keys


def test_two_ctrl_c_in_a_row_quit(tmp_path: Path) -> None:
    out, keyboard = play(tmp_path, [KeyboardInterrupt, KeyboardInterrupt, "never typed"])
    assert "Press Ctrl+C again to quit" in out and "Farewell" in out
    assert keyboard.keys == ["never typed"]


def test_a_command_between_presses_resets_the_count(tmp_path: Path) -> None:
    out, keyboard = play(tmp_path, [KeyboardInterrupt, "look", KeyboardInterrupt, "quit"])
    assert out.count("Press Ctrl+C again to quit") == 2
    assert not keyboard.keys  # the second lone press didn't quit; `quit` did


def test_ctrl_c_during_a_command_only_stops_that_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def slow_command(game: Game, arg: str) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(game_module._LOOKUP["map"], "fn", slow_command)
    out, keyboard = play(tmp_path, ["map", "look", "quit"])
    assert "Stopped. You're still in the game." in out
    assert not keyboard.keys  # carried on to `look` and `quit`


def test_ctrl_d_still_quits_straight_away(tmp_path: Path) -> None:
    out, _ = play(tmp_path, [EOFError])
    assert "Farewell" in out and "Press Ctrl+C again" not in out


def test_stopping_your_own_program_is_explained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("azurath.workspace.Workspace.interactive", lambda self, argv: 130)
    out, _ = play(tmp_path, ["python forever.py", "quit"])
    assert "You stopped your program with Ctrl+C" in out
