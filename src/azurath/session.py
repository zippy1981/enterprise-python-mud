"""Drive the game without a terminal, for other front ends.

The terminal game (``azurath play``) reads lines and prints Rich output. A
graphical front end (the Textual UI, the VS Code extension, the browser map)
needs the same game but wants:

* the output of one command at a time, as plain text, ANSI or HTML;
* the game's state as data: the room, exits, quest, map, inventory and XP;
* the result of a ``check`` as a list of criteria, not a drawn panel;
* to open files itself instead of launching vim;
* programs (``python``, ``pytest``, ``!`` commands) whose output it can show,
  instead of programs that take over the terminal.

:class:`Session` gives it that. ``python -m azurath.session`` speaks the same API
as JSON lines over stdin/stdout (see :func:`serve`), so a front end written in
another language (the VS Code extension is JavaScript) can use it too.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TextIO

from rich.console import Console
from rich.text import Text

from azurath.checks import Report
from azurath.content import Dungeon, Room, load_dungeon
from azurath.game import QUIT, Game
from azurath.settings import AzurathSettings
from azurath.workspace import Workspace

PROTOCOL_VERSION = 1


class CapturingWorkspace(Workspace):
    """A workspace whose programs print into the game's output instead of the terminal."""

    def __init__(self, root: Path, console: Console) -> None:
        super().__init__(root)
        self.console = console

    def interactive(self, argv: list[str]) -> int:
        try:
            proc = subprocess.run(
                argv,
                cwd=self.root,
                env=self.env(),
                stdin=subprocess.DEVNULL,  # nobody can type into a front end's program yet
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
        except FileNotFoundError:
            return 127
        except subprocess.TimeoutExpired:
            self.console.print(Text("(stopped after 5 minutes)", style="yellow"))
            return 124
        if proc.stdout:
            self.console.print(Text(proc.stdout.rstrip("\n")))
        return proc.returncode


@dataclass
class Exit:
    direction: str
    room: str
    name: str
    locked: bool


@dataclass
class MapRoom:
    id: str
    name: str
    zone: str
    order: int
    status: str  # "complete", "visited" or "undiscovered"
    here: bool
    optional: bool
    guided: bool
    exits: dict[str, str]


@dataclass
class Criterion:
    description: str
    ok: bool
    optional: bool
    detail: str | None


@dataclass
class Snapshot:
    """Everything a front end needs to draw the game, as plain data."""

    protocol: int
    dungeon: str
    dungeon_name: str
    player: str
    title: str
    xp: int
    room: str
    room_name: str
    zone: str
    description: str
    npc: str | None
    pages: list[str]
    pages_read: int
    quest: str | None
    quest_brief: str | None
    quest_done: bool
    exits: list[Exit]
    map: list[MapRoom]
    inventory: list[str]
    workspace: str
    last_check: list[Criterion] | None = None
    check_passed: bool | None = None


@dataclass
class Result:
    """What one command did."""

    command: str
    text: str
    ansi: str
    html: str
    opened: list[str] = field(default_factory=list)  # files the game asked to open
    quit: bool = False


class Session:
    """One player's game, driven a command at a time."""

    def __init__(
        self,
        settings: AzurathSettings | None = None,
        *,
        dungeon: Dungeon | None = None,
        width: int = 100,
        answers: Iterable[str] = (),
        open_file: Callable[[Path, str], bool] | None = None,
    ) -> None:
        settings = settings or AzurathSettings()
        self.buffer = io.StringIO()
        self.console = Console(
            file=self.buffer,
            record=True,
            width=width,
            force_terminal=True,
            color_system="truecolor",
            highlight=False,
            no_color=not settings.color,
        )
        self.answers: deque[str] = deque(answers)
        self.prompts: list[str] = []
        self.game = Game(
            settings,
            console=self.console,
            input_fn=self._answer,
            dungeon=dungeon or load_dungeon(settings.dungeon or "enterprise"),
        )
        self.game.ws = CapturingWorkspace(self.game.ws.root, self.console)
        self._opened: list[str] = []
        self._open_file = open_file
        self.game.open_file = self._opening
        self.last_report: Report | None = None
        self.started = False

    # --- input -------------------------------------------------------------------------

    def _answer(self, prompt: str) -> str:
        """Questions the game asks mid-command. Unanswered ones take their default."""
        self.prompts.append(prompt)
        answer = self.answers.popleft() if self.answers else ""
        self.console.print(Text.from_markup(prompt, end="") + Text(answer))
        return answer

    def _opening(self, path: Path, rel: str) -> bool:
        self._opened.append(rel)
        return self._open_file(path, rel) if self._open_file else True

    # --- running -----------------------------------------------------------------------

    def _collect(self, command: str, quit: bool = False) -> Result:
        html = self.console.export_html(clear=False, inline_styles=True, code_format="{code}")
        ansi = self.buffer.getvalue()
        text = self.console.export_text(clear=True)
        self.buffer.seek(0)
        self.buffer.truncate()
        opened, self._opened = self._opened, []
        return Result(command, text, ansi, html, opened, quit)

    def start(self, answers: Iterable[str] = ()) -> Result:
        """Greet the player, creating the workspace if needed (with default answers)."""
        self.answers.extend(answers)
        ok = self.game.start()
        self.started = True
        return self._collect("start", quit=not ok)

    def run(self, line: str, answers: Iterable[str] = ()) -> Result:
        """Run one command, like typing it at the prompt."""
        if not self.started:
            self.start()
        self.answers.extend(answers)
        verb = line.strip().split(" ", 1)[0].lower()
        if verb in {"shell", "terminal"}:
            self.game.out.warn("This window has no terminal to hand over. Use `!<command>`.")
            return self._collect(line)
        result = self.game.handle(line)
        if isinstance(result, Report):
            self.last_report = result
        return self._collect(line, quit=result is QUIT)

    # --- state -------------------------------------------------------------------------

    def snapshot(self) -> Snapshot:
        game, dungeon, state = self.game, self.game.dungeon, self.game.state
        room: Room = game.room
        rooms = []
        for r in dungeon.ordered():
            if game.quest_done(r):
                status = "complete"
            elif r.id in state.visited:
                status = "visited"
            else:
                status = "undiscovered"
            rooms.append(
                MapRoom(
                    r.id,
                    r.name,
                    r.zone,
                    r.order,
                    status,
                    r.id == room.id,
                    r.optional,
                    bool(getattr(r, "guided", False)),
                    dict(r.exits),
                )
            )
        exits = [
            Exit(
                direction,
                target,
                dungeon.rooms[target].name,
                game.exit_locked(dungeon.rooms[target]),
            )
            for direction, target in room.exits.items()
        ]
        report = self.last_report
        return Snapshot(
            protocol=PROTOCOL_VERSION,
            dungeon=dungeon.id,
            dungeon_name=dungeon.name,
            player=state.name,
            title=game.title,
            xp=state.xp,
            room=room.id,
            room_name=room.name,
            zone=room.zone,
            description=room.description,
            npc=room.npc.name if room.npc else None,
            pages=[page.title for page in room.pages],
            pages_read=state.pages.get(room.id, 0),
            quest=room.quest.title if room.quest else None,
            quest_brief=room.quest.brief if room.quest else None,
            quest_done=game.quest_done(room),
            exits=exits,
            map=rooms,
            inventory=list(state.inventory),
            workspace=str(game.ws.root),
            last_check=(
                [Criterion(c.description, c.ok, c.optional, c.detail) for c in report.items]
                if report
                else None
            ),
            check_passed=report.passed if report else None,
        )

    def check(self) -> tuple[Result, Report | None]:
        result = self.run("check")
        return result, self.last_report


# --- JSON lines over stdio ----------------------------------------------------------------


def _handle(session: Session, message: dict[str, Any]) -> dict[str, Any]:
    kind = message.get("type")
    answers = message.get("answers") or []
    if kind == "start":
        result = session.start(answers)
    elif kind == "run":
        result = session.run(str(message.get("line", "")), answers)
    elif kind == "snapshot":
        return {"type": "snapshot", "snapshot": asdict(session.snapshot())}
    else:
        return {"type": "error", "error": f"unknown message type {kind!r}"}
    return {"type": "result", "result": asdict(result), "snapshot": asdict(session.snapshot())}


def serve(session: Session, stdin: TextIO, stdout: TextIO) -> None:
    """Answer one JSON object per line on ``stdin`` with one JSON object per line.

    Requests: ``{"id": 1, "type": "start" | "run" | "snapshot", "line": "look",
    "answers": ["y"]}``. Each reply has the same ``id``, plus ``result`` (the
    command's text, ansi and html, files to open, whether the game quit) and a fresh
    ``snapshot``. ``opened`` paths are relative to ``snapshot.workspace``.
    """
    stdout.write(json.dumps({"type": "ready", "protocol": PROTOCOL_VERSION}) + "\n")
    stdout.flush()
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            reply = _handle(session, message)
        except Exception as exc:  # a front end must never see the game crash
            message = message if isinstance(locals().get("message"), dict) else {}
            reply = {"type": "error", "error": f"{type(exc).__name__}: {exc}"}
        reply["id"] = message.get("id") if isinstance(message, dict) else None
        stdout.write(json.dumps(reply) + "\n")
        stdout.flush()
        if reply.get("result", {}).get("quit"):
            break


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m azurath.session", description="Azurath's JSON-lines API for front ends."
    )
    parser.add_argument("-d", "--dungeon")
    parser.add_argument("-w", "--workspace", type=Path)
    parser.add_argument("--width", type=int, default=100)
    args = parser.parse_args(argv)
    overrides: dict[str, Any] = {}
    if args.dungeon:
        overrides["dungeon"] = args.dungeon
    if args.workspace:
        overrides["workspace"] = args.workspace
    settings = AzurathSettings(**overrides)
    # Opened files are reported to the front end, which opens them itself.
    session = Session(settings, width=args.width, open_file=lambda _path, _rel: True)
    serve(session, sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
