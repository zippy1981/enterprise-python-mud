"""Play the whole game with the reference solutions.

For every room, in curriculum order, this checks that:

1. the quest check FAILS before any work is done,
2. it still FAILS after `scaffold` (starter files aren't answers),
3. it PASSES after applying the room's reference solution and commands,
4. completing it commits to git and unlocks the next room.

It needs network access (uv installs packages), and Go plus a C compiler for
the optional Gopher rooms. Run it with:  uv run pytest -m slow
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from azurath.checks import run_check
from azurath.content import load_world, room_file

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv"),
    pytest.mark.skipif(shutil.which("git") is None, reason="needs git"),
]

HAVE_GO = shutil.which("go") is not None


def _failures(report) -> str:
    return "\n".join(
        f"✘ {c.description}\n    {c.detail or ''}"
        for c in report.items
        if not c.ok and not c.optional
    )


def test_full_walkthrough(make_player, python_on_path) -> None:
    player = make_player()
    game, ws = player.game, player.game.ws
    rooms = [r for r in load_world().ordered() if HAVE_GO or not r.id.startswith("gopher")]

    for room in rooms:
        quest = room.quest
        assert quest is not None
        game.state.visit(room.id)

        before = run_check(quest.check, ws)
        assert not before.passed, f"{room.id}: check passed before any work was done"

        if quest.scaffold:
            player("scaffold")
            scaffolded = run_check(quest.check, ws)
            assert not scaffolded.passed, f"{room.id}: the scaffold alone passes the check"

        for target, source in quest.solution.files.items():
            ws.write(target, room_file(room.id, "solution", source).read_text(encoding="utf-8"))
        for command in quest.solution.commands:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=ws.root,
                env=ws.env(),
                capture_output=True,
                text=True,
                timeout=900,
            )
            assert proc.returncode == 0, (
                f"{room.id}: `{command}` failed\n{proc.stdout}\n{proc.stderr}"
            )

        out = player("check")
        assert room.id in game.state.completed, f"{room.id}: solution failed its check\n{out}"
        assert "QUEST COMPLETE" in out

    log = ws.git("log", "--oneline").stdout.splitlines()
    assert len(log) == len(rooms) + 1, log  # one commit per quest + the initial commit
    assert ws.git("status", "--porcelain").stdout.strip() == ""
    if HAVE_GO:
        assert game.state.title == "Archmage of Azurath"
