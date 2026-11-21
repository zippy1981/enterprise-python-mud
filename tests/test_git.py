"""The startup git check, setting the player's identity, and handling commit failures."""

import io
import shutil
from pathlib import Path

import pytest
from rich.console import Console

from azurath import gitcheck
from azurath.content import load_dungeon
from azurath.game import Game
from azurath.settings import AzurathSettings
from azurath.workspace import RunResult

GIT_ENV = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


@pytest.fixture
def no_identity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A global git config with no user, where git may not guess one from the system."""
    for var in GIT_ENV:
        monkeypatch.delenv(var, raising=False)
    config = tmp_path / "gitconfig"  # conftest points GIT_CONFIG_GLOBAL here
    config.write_text("[user]\n\tuseConfigOnly = true\n")
    return config


class Session:
    def __init__(self, tmp_path: Path, answers: list[str], dungeon: str = "enterprise") -> None:
        self.buffer = io.StringIO()
        self.answers = list(answers)
        console = Console(file=self.buffer, width=140, color_system=None)
        settings = AzurathSettings(workspace=tmp_path / "project")
        self.game = Game(
            settings, console=console, input_fn=self._answer, dungeon=load_dungeon(dungeon)
        )

    def _answer(self, prompt: str) -> str:
        return self.answers.pop(0) if self.answers else ""  # like pressing Enter / EOF

    @property
    def output(self) -> str:
        return self.buffer.getvalue()

    def log(self) -> list[str]:
        res = self.game.ws.git("log", "--oneline")
        return res.stdout.splitlines() if res.ok else []


def global_config(key: str) -> str:
    return gitcheck.run_git("config", "--global", "--get", key).stdout.strip()


# --- the health check ------------------------------------------------------------------


def test_check_git_reports_a_missing_identity(no_identity: Path) -> None:
    health = gitcheck.check_git()
    assert health.installed and health.version and health.problem is None
    assert not health.has_identity and not health.ok


def test_set_global_identity_writes_the_global_config(no_identity: Path) -> None:
    assert gitcheck.set_global_identity("Ada Lovelace", "ada@example.com").ok
    health = gitcheck.check_git()
    assert health.ok and health.name == "Ada Lovelace" and health.email == "ada@example.com"
    assert "ada@example.com" in no_identity.read_text()


def test_a_broken_global_config_is_reported(tmp_path: Path) -> None:
    (tmp_path / "gitconfig").write_text("[user\nname = oops\n")
    assert gitcheck.check_git().problem


@pytest.mark.parametrize(
    ("text", "valid"),
    [
        ("ada@example.com", True),
        ("a.b+c@sub.example.org", True),
        ("nope", False),
        ("a@b", False),
        ("two words@example.com", False),
        ("", False),
    ],
)
def test_email_validation(text: str, valid: bool) -> None:
    assert gitcheck.valid_email(text) is valid


# --- at the start of the game ------------------------------------------------------------


def test_new_player_without_an_identity_is_asked_for_one(no_identity: Path, tmp_path: Path) -> None:
    session = Session(
        tmp_path,
        ["y", "Ada Lovelace", "not-an-email", "ada@example.com", "y", "Ada"],
    )
    assert session.game.start()
    assert "git needs to know who you are" in session.output
    assert "doesn't look like an email" in session.output
    assert global_config("user.name") == "Ada Lovelace"
    assert global_config("user.email") == "ada@example.com"
    assert len(session.log()) == 1  # the first commit worked


def test_the_game_name_defaults_to_the_git_name(no_identity: Path, tmp_path: Path) -> None:
    session = Session(tmp_path, ["y", "Ada Lovelace", "ada@example.com", "y", ""])
    assert session.game.start()
    assert session.game.state.name == "Ada"


def test_declining_still_lets_you_play_and_asks_again_on_commit(
    no_identity: Path, tmp_path: Path
) -> None:
    session = Session(tmp_path, ["n", "y", "Ada", "n"])
    assert session.game.start()
    assert "can't commit your work until git knows who you are" in session.output
    assert "Couldn't commit your work: git doesn't know who you are" in session.output
    assert session.log() == []
    assert not global_config("user.name")

    # Later, a quest is completed: the commit fails, the game offers to fix it, then retries.
    hello = load_dungeon("enterprise").room_text("gatehouse", "solution", "hello.py")
    session.game.ws.write("hello.py", hello)
    session.answers = ["y", "Ada Lovelace", "ada@example.com"]
    session.game.handle("check")
    assert global_config("user.email") == "ada@example.com"
    assert any("hello.py" in line for line in session.log())


def test_a_configured_git_is_confirmed_quietly(tmp_path: Path) -> None:
    gitcheck.set_global_identity("Grace Hopper", "grace@example.com")
    session = Session(tmp_path, ["y", "Grace"])
    assert session.game.start()
    assert "git ✔" in session.output and "Grace Hopper" in session.output
    assert "git needs to know who you are" not in session.output


def test_missing_git_is_explained_and_the_game_continues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_which = shutil.which
    monkeypatch.setattr(
        shutil, "which", lambda name, *a, **k: None if name == "git" else real_which(name, *a, **k)
    )
    session = Session(tmp_path, ["y", "Ada"])
    assert session.game.start()
    assert "git isn't installed" in session.output
    assert session.game.ws.exists("README.md") and not session.game.ws.is_git_repo()


def test_a_broken_git_config_is_shown_at_startup(tmp_path: Path) -> None:
    (tmp_path / "gitconfig").write_text("[user\nname = oops\n")
    session = Session(tmp_path, ["y", "Ada"])
    assert session.game.start()
    assert "isn't working" in session.output and "--edit" in session.output


# --- commit failures --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stderr", "kind"),
    [
        ("Author identity unknown\n*** Please tell me who you are.", "IDENTITY"),
        ("fatal: unable to auto-detect email address", "IDENTITY"),
        ("fatal: Unable to create '/x/.git/index.lock': File exists.", "LOCKED"),
        ("fatal: detected dubious ownership in repository at '/x'", "DUBIOUS_OWNERSHIP"),
        ("fatal: not a git repository (or any of the parent directories): .git", "NOT_A_REPO"),
        ("git is not installed", "NO_GIT"),
        ("error: pre-commit hook failed", "OTHER"),
    ],
)
def test_commit_failures_are_classified(stderr: str, kind: str) -> None:
    result = RunResult(128, "", stderr)
    assert gitcheck.classify_commit_failure(result) is gitcheck.CommitFailure[kind]


def test_a_lost_git_repo_can_be_recreated(tmp_path: Path) -> None:
    session = Session(tmp_path, ["y", "Ada"])
    session.game.start()
    shutil.rmtree(session.game.ws.root / ".git")
    session.answers = ["y"]
    session.game.handle("commit after the accident")
    assert "isn't a git repository" in session.output
    assert any("after the accident" in line for line in session.log())


def test_a_lock_file_is_explained_not_deleted(tmp_path: Path) -> None:
    session = Session(tmp_path, ["y", "Ada"])
    session.game.start()
    lock = session.game.ws.root / ".git" / "index.lock"
    lock.write_text("")
    session.game.ws.write("new.txt", "hi\n")
    session.game.handle("commit stuck")
    assert "lock file" in session.output and lock.exists()
