"""Each dungeon's checksum is stored in the code and must match its files."""

from __future__ import annotations

from pathlib import Path

import pytest

from azurath import checksums

FIX = "uv run python -m azurath.checksums"


@pytest.mark.parametrize("dungeon_id", checksums.dungeon_ids())
def test_stored_checksum_matches_the_files(dungeon_id: str) -> None:
    assert checksums.expected(dungeon_id) is not None, f"no checksum stored: run `{FIX}`"
    assert checksums.mismatch(dungeon_id) is None, f"the dungeon changed: run `{FIX}`"


def make_dungeon(root: Path) -> Path:
    folder = root / "dungeons" / "demo"
    (folder / "rooms").mkdir(parents=True)
    (folder / "dungeon.yaml").write_text("id: demo\n", encoding="utf-8")
    (folder / "rooms" / "a.yaml").write_text("id: a\n", encoding="utf-8")
    return folder


def test_any_change_changes_the_checksum(tmp_path: Path) -> None:
    folder = make_dungeon(tmp_path)
    before = checksums.compute(folder)
    (folder / "rooms" / "a.yaml").write_text("id: b\n", encoding="utf-8")
    edited = checksums.compute(folder)
    (folder / "rooms" / "a.yaml").rename(folder / "rooms" / "b.yaml")
    renamed = checksums.compute(folder)
    (folder / "rooms" / "c.yaml").write_text("", encoding="utf-8")
    added = checksums.compute(folder)
    assert len({before, edited, renamed, added}) == 4


def test_line_endings_and_junk_files_dont_count(tmp_path: Path) -> None:
    folder = make_dungeon(tmp_path)
    before = checksums.compute(folder)
    (folder / "rooms" / "a.yaml").write_bytes(b"id: a\r\n")  # a Windows checkout
    (folder / "__pycache__").mkdir()
    (folder / "__pycache__" / "x.cpython-313.pyc").write_bytes(b"\0")
    (folder / ".DS_Store").write_bytes(b"\0")
    (folder / "checksum.py").write_text('CHECKSUM = "old"\n', encoding="utf-8")
    assert checksums.compute(folder) == before


def test_update_writes_checksum_files(tmp_path: Path) -> None:
    folder = make_dungeon(tmp_path)
    assert checksums.update(tmp_path) == ["demo"]
    text = (folder / "checksum.py").read_text(encoding="utf-8")
    assert checksums.compute(folder) in text
    assert checksums.update(tmp_path) == []  # already up to date


def test_mismatch_explains_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checksums, "expected", lambda _id: "0" * 64)
    problem = checksums.mismatch("pythonwood")
    assert problem and "don't match this version of Azurath" in problem


# --- the game -------------------------------------------------------------------------


def test_game_warns_when_files_dont_match(make_player, monkeypatch: pytest.MonkeyPatch) -> None:
    player = make_player(dungeon="pythonwood")
    assert player.game.check_dungeon_files()
    monkeypatch.setattr(checksums, "expected", lambda _id: "0" * 64)
    start = player.buffer.tell()
    assert not player.game.check_dungeon_files()
    player.buffer.seek(start)
    out = player.buffer.read()
    assert "don't match this version of Azurath" in out
    assert "--reinstall" in out and FIX in out


def test_returning_player_hears_about_changes(make_player, monkeypatch) -> None:
    player = make_player(dungeon="pythonwood")
    game = player.game
    game.state.dungeon_checksum = None  # an old save, from before checksums
    game.notice_dungeon_changes()
    assert game.state.dungeon_checksum == checksums.actual("pythonwood")
    assert "has changed since you last played" not in player.buffer.getvalue()

    game.state.dungeon_checksum = "f" * 64  # saved by an older version of the dungeon
    game.notice_dungeon_changes()
    assert "has changed since you last played" in player.buffer.getvalue()
    assert game.state.dungeon_checksum == checksums.actual("pythonwood")
