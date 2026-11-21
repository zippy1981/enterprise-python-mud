"""The headless Session (and its JSON-lines protocol) that other front ends drive."""

from __future__ import annotations

import io
import json
from pathlib import Path

from azurath import gitcheck
from azurath.content import load_dungeon
from azurath.session import Session, serve
from azurath.settings import AzurathSettings


def make_session(tmp_path: Path, **kwargs) -> Session:
    assert gitcheck.set_global_identity("Ada Lovelace", "ada@example.com").ok
    settings = AzurathSettings(workspace=tmp_path / "proj", dungeon="pythonwood")
    return Session(settings, dungeon=load_dungeon("pythonwood"), **kwargs)


def test_start_creates_the_workspace_with_default_answers(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    result = session.start()
    assert not result.quit
    assert (tmp_path / "proj" / ".azurath").is_dir()
    assert "Create it now?" in result.text  # the question is shown, with its default taken
    snap = session.snapshot()
    assert snap.dungeon == "pythonwood" and snap.room == snap.map[0].id
    assert snap.map[0].here and snap.map[0].status == "visited"


def test_each_result_holds_only_its_own_output(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    session.start()
    first = session.run("help")
    second = session.run("status")
    assert "look" in first.text
    assert "look" not in second.text and "XP" in second.text
    assert "<span style=" in second.html  # an HTML fragment with inline styles
    assert "\x1b[" in second.ansi  # colours for front ends that draw ANSI


def test_answers_are_used_in_order(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    session.start(answers=["y", "Grace"])
    assert session.snapshot().player == "Grace"


def test_editing_is_reported_not_launched(tmp_path: Path) -> None:
    seen: list[str] = []
    session = make_session(tmp_path, open_file=lambda path, rel: seen.append(rel) or True)
    session.start()
    session.run("scaffold")
    target = session.snapshot().quest and session.game.room.quest.scaffold
    rel = next(iter(target))
    result = session.run(f"edit {rel}")
    assert result.opened == [rel] and seen == [rel]
    assert "opened" in result.text


def test_programs_print_into_the_result(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    session.start()
    (tmp_path / "proj" / "hi.py").write_text('print("hello from the player")\n', encoding="utf-8")
    result = session.run("python hi.py")
    assert "hello from the player" in result.text


def test_check_results_are_data(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    session.start()
    session.run("check")
    snap = session.snapshot()
    assert snap.check_passed is False
    assert snap.last_check and any(not c.ok for c in snap.last_check)


def test_the_shell_command_is_refused(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    session.start()
    assert "no terminal" in session.run("shell").text


def test_json_lines_protocol(tmp_path: Path) -> None:
    session = make_session(tmp_path)
    requests = [
        {"id": 1, "type": "start"},
        {"id": 2, "type": "run", "line": "look"},
        {"id": 3, "type": "snapshot"},
        {"id": 4, "type": "bogus"},
        {"id": 5, "type": "run", "line": "quit"},
        {"id": 6, "type": "run", "line": "look"},  # never reached: the game quit
    ]
    stdin = io.StringIO("".join(json.dumps(r) + "\n" for r in requests))
    stdout = io.StringIO()
    serve(session, stdin, stdout)
    replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert replies[0] == {"type": "ready", "protocol": 1}
    by_id = {r.get("id"): r for r in replies[1:]}
    assert by_id[2]["result"]["command"] == "look"
    assert by_id[2]["snapshot"]["room_name"] in by_id[2]["result"]["text"]
    assert by_id[3]["type"] == "snapshot"
    assert by_id[4]["type"] == "error"
    assert by_id[5]["result"]["quit"] is True
    assert 6 not in by_id
