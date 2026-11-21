"""Keep the repo's Claude Code skills working as the game evolves."""

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / ".claude" / "skills" / "verify-room" / "verify_room.py"


@pytest.fixture
def verify_room(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))  # the script prepends a shim; undo it
    spec = importlib.util.spec_from_file_location("verify_room", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_room_passes_an_early_room(verify_room, capsys: pytest.CaptureFixture[str]) -> None:
    assert verify_room.main(["hall_of_basics"]) == 0
    out = capsys.readouterr().out
    assert "[PASS] gatehouse" in out
    assert "VERIFIED: hall_of_basics" in out


def test_setup_only_leaves_a_playable_workspace(verify_room, tmp_path: Path) -> None:
    from azurath.state import PlayerState

    assert verify_room.main(["hall_of_basics", "--setup-only", str(tmp_path)]) == 0
    state = PlayerState.load(tmp_path / "questboard")
    assert state.room == "hall_of_basics"
    assert "gatehouse" in state.completed and state.xp == 100
    assert not (tmp_path / "questboard" / "basics.py").exists()  # the target room is untouched


def test_unknown_room_is_rejected(verify_room) -> None:
    assert verify_room.main(["no_such_room"]) == 2
