"""The Pythonwood's VS Code setup: AI assistants off, regular autocomplete on."""

import io
import json
import re
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from azurath.content import load_dungeon
from azurath.game import Game
from azurath.settings import AzurathSettings

PYTHONWOOD = load_dungeon("pythonwood")


def jsonc(text: str) -> dict:
    """VS Code settings files allow // comments on their own lines."""
    return json.loads(re.sub(r"(?m)^\s*//.*$", "", text))


@pytest.fixture
def settings() -> dict:
    return jsonc(PYTHONWOOD.template_text("vscode-settings.json"))


def test_ai_assistants_are_switched_off(settings: dict) -> None:
    assert settings["chat.disableAIFeatures"] is True
    assert settings["github.copilot.enable"] == {"*": False}
    assert settings["github.copilot.nextEditSuggestions.enabled"] is False
    assert settings["editor.inlineSuggest.enabled"] is False  # ghost text from any extension


def test_regular_autocomplete_stays_on(settings: dict) -> None:
    assert settings["editor.quickSuggestions"]["other"] == "on"
    assert settings["editor.suggestOnTriggerCharacters"] is True
    assert settings.get("editor.suggest.showWords", True) is not False
    assert "editor.acceptSuggestionOnEnter" not in settings or (
        settings["editor.acceptSuggestionOnEnter"] != "off"
    )


def test_learner_friendly_defaults(settings: dict) -> None:
    assert settings["files.autoSave"] == "afterDelay"  # `check` always sees the latest code
    assert settings["editor.tabSize"] == 4 and settings["editor.insertSpaces"] is True


def test_ai_extensions_are_unwanted() -> None:
    extensions = jsonc(PYTHONWOOD.template_text("vscode-extensions.json"))
    assert extensions["recommendations"] == ["ms-python.python"]
    unwanted = {e.lower() for e in extensions["unwantedRecommendations"]}
    assert {"github.copilot", "github.copilot-chat", "anthropic.claude-code"} <= unwanted


def make_game(tmp_path: Path, dungeon: str = "pythonwood") -> tuple[Game, io.StringIO]:
    # A git identity in the isolated global config, so a startup git check (if the game
    # has one) doesn't stop to ask for it: these tests are about VS Code settings.
    for key, value in (("user.name", "Ada Lovelace"), ("user.email", "ada@example.com")):
        subprocess.run(["git", "config", "--global", key, value], check=True)
    buffer = io.StringIO()
    console = Console(file=buffer, width=140, color_system=None)
    answers = iter(["y", "Maya"])
    game = Game(
        AzurathSettings(workspace=tmp_path / "project"),
        console=console,
        input_fn=lambda prompt: next(answers, ""),
        dungeon=load_dungeon(dungeon),
    )
    return game, buffer


def test_a_new_project_gets_the_settings_in_its_first_commit(tmp_path: Path) -> None:
    game, _ = make_game(tmp_path)
    assert game.start()
    assert game.ws.exists(".vscode/settings.json") and game.ws.exists(".vscode/extensions.json")
    tracked = game.ws.git("ls-files").stdout.split()
    assert ".vscode/settings.json" in tracked


def test_the_players_own_settings_are_never_overwritten(tmp_path: Path) -> None:
    game, _ = make_game(tmp_path)
    game.start()
    game.ws.write(".vscode/settings.json", "{}\n")
    game.ws.path(".vscode/extensions.json").unlink()
    assert game.install_workspace_files() == [".vscode/extensions.json"]
    assert game.ws.read(".vscode/settings.json") == "{}\n"


def test_the_enterprise_dungeon_is_left_alone(tmp_path: Path) -> None:
    game, _ = make_game(tmp_path, "enterprise")
    game.start()
    assert not game.ws.exists(".vscode/settings.json")


def test_code_opens_the_kid_profile_and_installs_python_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil
    import subprocess

    game, buffer = make_game(tmp_path)
    game.start()
    launched, installs = [], []
    monkeypatch.setattr(
        shutil, "which", lambda name, *a, **k: "/bin/code" if name == "code" else None
    )
    monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: launched.append(argv))

    def fake_run(argv, **kw):
        installs.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    game.handle("code")
    game.handle("code")
    assert launched[0] == ["/bin/code", "--profile", "Pythonwood", str(game.ws.root)]
    assert installs == [
        ["/bin/code", "--profile", "Pythonwood", "--install-extension", "ms-python.python"]
    ]  # only the first time
    assert "no AI helpers" in buffer.getvalue()
