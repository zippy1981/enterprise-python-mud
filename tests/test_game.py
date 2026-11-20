"""Gameplay: movement, locks, reading, scaffolding, checking and committing."""

import sys
from pathlib import Path

import pytest

from azurath.checks import Report, run_check
from azurath.cli import main
from azurath.content import load_dungeon
from azurath.editor import choose_editor
from azurath.game import QUIT
from azurath.settings import AzurathSettings
from azurath.state import PlayerState
from azurath.workspace import Workspace


def solve_gatehouse(ws: Workspace) -> None:
    source = load_dungeon("enterprise").room_file("gatehouse", "solution", "hello.py")
    ws.write("hello.py", source.read_text(encoding="utf-8"))


def test_new_workspace_is_a_git_repo_with_an_initial_commit(make_player) -> None:
    ws = make_player().game.ws
    assert (ws.root / ".git").is_dir()
    assert ".azurath/" in ws.read(".gitignore")
    assert len(ws.git("log", "--oneline").stdout.splitlines()) == 1


def test_forward_exit_is_locked_until_the_quest_is_done(make_player) -> None:
    player = make_player()
    out = player("north")
    assert "ward blocks" in out
    assert player.game.state.room == "gatehouse"

    solve_gatehouse(player.game.ws)
    out = player("check")
    assert "QUEST COMPLETE" in out
    assert "way to Hall of Basics is open" in out
    out = player("n")
    assert player.game.state.room == "hall_of_basics"
    assert "Hall of Basics" in out
    player("south")  # backwards is always open
    assert player.game.state.room == "gatehouse"


def test_completing_a_quest_rewards_and_commits(make_player) -> None:
    player = make_player()
    solve_gatehouse(player.game.ws)
    player("check")
    state = player.game.state
    assert "gatehouse" in state.completed
    assert state.xp == 100
    assert "Warden's Lantern" in state.inventory
    log = player.game.ws.git("log", "--oneline").stdout
    assert "hello.py" in log
    assert "main guard" in player("examine lantern")

    again = player("check")  # re-checking doesn't double-reward
    assert "already completed" in again
    assert player.game.state.xp == 100


def test_auto_commit_can_be_disabled(make_player) -> None:
    player = make_player(auto_commit=False)
    solve_gatehouse(player.game.ws)
    player("check")
    assert len(player.game.ws.git("log", "--oneline").stdout.splitlines()) == 1
    assert "committed" in player("commit my message")
    assert "my message" in player.game.ws.git("log", "--oneline").stdout


def test_reading_pages_advances_and_wraps(make_player) -> None:
    player = make_player()
    pages = player.game.room.pages
    assert pages[0].title in player("read")
    assert pages[1].title in player("read")
    assert pages[0].title in player("read back")
    assert pages[3].title in player("read 4")
    assert "last page" in player("read 4")
    assert pages[0].title in player("read")  # wraps around after the last page
    assert "The tome has pages" in player("read 99")


def test_talk_and_ask(make_player) -> None:
    player = make_player()
    assert "Warden Pip" in player("talk")
    assert "vim" in player("ask pip about editing")
    assert "vim" in player("ask editing")
    assert "I can tell you about" in player("ask about dragons")


def test_scaffold_never_overwrites(make_player) -> None:
    player = make_player()
    ws = player.game.ws
    ws.write("hello.py", "# mine\n")
    assert "already exists" in player("scaffold")
    assert ws.read("hello.py") == "# mine\n"


def test_scaffold_then_check_fails_with_a_useful_report(make_player) -> None:
    player = make_player()
    player("scaffold")
    out = player("check")
    assert "Not yet" in out
    assert "__name__" in out


def test_hints_are_revealed_one_at_a_time(make_player) -> None:
    player = make_player()
    hints = player.game.room.quest.hints
    assert "Hint 1/" in player("hint")
    assert "Hint 2/" in player("hint")
    for _ in hints:
        out = player("hint")
    assert "Out of hints" in out


def test_solution_requires_confirmation_and_apply_backs_up(make_player) -> None:
    player = make_player(answers=["n"])
    assert "Hello, Azurath" not in player("solution")  # declined the spoiler
    player.game.ws.write("hello.py", "# draft\n")
    out = player("solution apply")  # answers default to "y" from here on
    assert "wrote hello.py" in out
    assert player.game.ws.read("hello.py.bak") == "# draft\n"
    assert "Hello, Azurath!" in player.game.ws.read("hello.py")


def test_unknown_commands_suggest_a_fix(make_player) -> None:
    assert "Did you mean `look`" in make_player()("lok")


def test_goto_only_reaches_visited_rooms(make_player) -> None:
    player = make_player()
    assert "haven't found" in player("goto durable")
    player.game.state.visit("durable_sanctum")
    player("goto gatehouse")
    player("goto durable")
    assert player.game.state.room == "durable_sanctum"


def test_quit_saves_progress(make_player) -> None:
    player = make_player()
    player.game.state.xp = 42
    assert player.game.handle("quit") is QUIT
    loaded = PlayerState.load(player.game.ws.root)
    assert loaded is not None and loaded.xp == 42


def test_corrupt_save_is_set_aside(tmp_path: Path) -> None:
    save = PlayerState.path_for(tmp_path)
    save.parent.mkdir(parents=True)
    save.write_text("{not json")
    assert PlayerState.load(tmp_path) is None
    assert save.with_suffix(".corrupt.json").exists()


def test_help_shows_usage_with_brackets(make_player) -> None:
    out = make_player()("help")
    assert "read [n | back | all]" in out
    assert "edit [file]" in out


@pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shell syntax")
def test_shell_commands_run_in_the_workspace(
    make_player, capfd: pytest.CaptureFixture[str]
) -> None:
    player = make_player()
    player("!echo azurath-$((6*7)) > out.txt")
    assert player.game.ws.read("out.txt").strip() == "azurath-42"


# --- settings & CLI ------------------------------------------------------------------


def test_settings_layering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "azurath.toml").write_text('editor = "nano"\nauto_commit = false\n')
    s = AzurathSettings()
    assert s.editor == "nano" and s.auto_commit is False
    assert s.workspace is None  # each dungeon picks its own default folder
    assert AzurathSettings(workspace="here").workspace == (tmp_path / "here").resolve()
    monkeypatch.setenv("AZURATH_EDITOR", "vim")
    assert AzurathSettings().editor == "vim"  # env beats the TOML file
    assert AzurathSettings(editor="code").editor == "code"  # init kwargs beat env


def test_cli_check_exit_codes(make_player, capsys: pytest.CaptureFixture[str]) -> None:
    player = make_player()
    ws = str(player.game.ws.root)
    assert main(["--workspace", ws, "--no-color", "check"]) == 1
    solve_gatehouse(player.game.ws)
    assert main(["--workspace", ws, "--no-color", "check"]) == 0
    assert main(["--workspace", ws, "--no-color", "check", "hall_of_basics"]) == 1
    state = PlayerState.load(player.game.ws.root)
    assert state.room == "gatehouse"  # `check <room>` doesn't move you


def test_cli_rooms_lists_the_curriculum(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-color", "--dungeon", "enterprise", "rooms"]) == 0
    assert "Durable Sanctum" in capsys.readouterr().out


# --- editors -------------------------------------------------------------------------


def test_vscode_terminal_prefers_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    monkeypatch.setattr("azurath.editor._vscode_cli", lambda: "/usr/bin/code")
    choice = choose_editor(tmp_path / "x.py")
    assert choice.argv[:3] == ["/usr/bin/code", "-r", "-g"] and not choice.blocking


def test_configured_editor_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    choice = choose_editor(tmp_path / "x.py", configured="nano -l")
    assert choice.argv == ["nano", "-l", str(tmp_path / "x.py")] and choice.blocking


def test_editor_env_vars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDITOR", "myeditor --flag")
    choice = choose_editor(tmp_path / "x.py")
    assert choice.argv == ["myeditor", "--flag", str(tmp_path / "x.py")]


# --- the check framework itself ------------------------------------------------------


def test_probe_reports_failures_and_crashes(tmp_path: Path) -> None:
    ws = Workspace(tmp_path)
    ok = ws.probe("expect(1 + 1 == 2, 'math works')")
    assert ok.ok
    bad = ws.probe("expect(False, 'nope')\nexpect(False, 'still nope')")
    assert bad.failures == ["nope", "still nope"]
    ws.write("broken.py", "def f(:\n")
    crashed = ws.probe("import broken")
    assert not crashed.ok and "SyntaxError" in crashed.failures[0]


def test_unknown_check_is_reported_not_raised(tmp_path: Path) -> None:
    report = run_check(load_dungeon("enterprise"), "no_such_check", Workspace(tmp_path))
    assert isinstance(report, Report) and not report.passed


def test_checks_survive_garbage_code(make_player) -> None:
    """Every check must report (not crash) when the workspace is full of junk."""
    from azurath.content import load_atlas

    player = make_player()
    ws = player.game.ws
    for rel in (
        "hello.py",
        "basics.py",
        "questboard/__init__.py",
        "questboard/text.py",
        "function_app.py",
        "questboard/orchestration.py",
        "questboard/models.py",
    ):
        ws.write(rel, "this is not python (\n")
    ws.write("pyproject.toml", "[[[ not toml")
    ws.write("data/quests.yaml", "{ not: [yaml")
    ws.write(".github/workflows/ci.yml", ":\n  - [")
    for dungeon in load_atlas().ordered():
        for room in dungeon.ordered():
            report = run_check(dungeon, room.quest.check, ws)
            assert not report.passed, (dungeon.id, room.id)
            assert all(c.description != "the check ran" for c in report.items), (
                dungeon.id,
                room.id,
                report.items,
            )


@pytest.mark.skipif(sys.platform == "win32", reason="uses `true` as the editor")
def test_editing_a_missing_quest_file_starts_from_the_scaffold(
    make_player, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EDITOR", "true")  # a "blocking editor" that exits immediately
    player = make_player()
    out = player("edit hello.py")
    assert "starter template" in out
    assert "TODO" in player.game.ws.read("hello.py")
    assert "outside your workspace" in player("edit ../escape.py")


# --- several dungeons ----------------------------------------------------------------


def test_cli_lists_dungeons(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-color", "dungeons"]) == 0
    out = capsys.readouterr().out
    assert "Pythonwood" in out and "Realm of Azurath" in out


def test_cli_needs_a_dungeon_when_it_cant_tell(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--no-color", "rooms"]) == 2
    assert "--dungeon" in capsys.readouterr().err
    assert main(["--no-color", "--dungeon", "nope", "rooms"]) == 2


def test_cli_finds_the_dungeon_from_a_save_in_this_folder(
    make_player, capsys: pytest.CaptureFixture[str]
) -> None:
    from azurath.content import load_dungeon

    make_player(dungeon="pythonwood")  # creates ./pythonwood with a save
    # the default workspace for this dungeon is ./critter-quest, so point at it explicitly
    assert main(["--no-color", "--workspace", "pythonwood", "status"]) == 0
    assert load_dungeon("pythonwood").name in capsys.readouterr().out


def test_a_workspace_belongs_to_one_dungeon(
    make_player, capsys: pytest.CaptureFixture[str]
) -> None:
    player = make_player(dungeon="pythonwood")
    ws = str(player.game.ws.root)
    assert main(["--no-color", "--dungeon", "enterprise", "--workspace", ws, "status"]) == 2
    assert "pythonwood" in capsys.readouterr().err


def test_each_dungeon_has_its_own_start_intro_and_ranks(make_player) -> None:
    kid = make_player(dungeon="pythonwood")
    assert kid.game.state.room == "trailhead"
    assert kid.game.title == "Seedling"
    assert "Ranger Juniper" in kid("look")
    assert "critter-quest" in kid.game.ws.read("README.md")


def test_pytest_command_reports_red_and_green(
    make_player, capfd: pytest.CaptureFixture[str]
) -> None:
    player = make_player(dungeon="pythonwood")
    ws = player.game.ws
    ws.write("tests/test_math.py", "def test_math():\n    assert 1 + 1 == 3\n")
    out = player("pytest")
    assert "RED" in out and "game's Python" in out
    ws.write("tests/test_math.py", "def test_math():\n    assert 1 + 1 == 2\n")
    assert "GREEN" in player("pytest")
    ws.write("hello.py", 'print("hi from", __name__)\n')
    player("python hello.py")
    assert "hi from __main__" in capfd.readouterr().out


def test_uv_init_inside_another_project_is_refused(make_player, tmp_path: Path) -> None:
    player = make_player(dungeon="pythonwood")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "outer"\nversion = "0"\n')
    out = player("!uv init --bare")
    assert "--no-workspace" in out and "Careful" in out
    assert not player.game.ws.exists("pyproject.toml")  # nothing ran


def test_check_explains_a_project_joined_to_an_outer_workspace(make_player, tmp_path: Path) -> None:
    from azurath.checks import run_check

    player = make_player(dungeon="pythonwood")
    outer = tmp_path / "pyproject.toml"
    outer.write_text(
        '[project]\nname = "o"\nversion = "0"\n[tool.uv.workspace]\nmembers = ["pythonwood"]\n'
    )
    report = run_check(player.game.dungeon, "backpack_burrow", player.game.ws)
    assert not report.passed
    assert str(outer) in report.items[0].detail
