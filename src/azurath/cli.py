"""Command-line entry point: ``azurath [play|check|status|rooms|dungeons]``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from azurath import __version__

if TYPE_CHECKING:
    from rich.console import Console

    from azurath.content import Atlas, Dungeon
    from azurath.settings import AzurathSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="azurath",
        description="Azurath: a MUD that teaches Python by having you build a real project.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-d", "--dungeon", help="Which dungeon to play (see `azurath dungeons`)")
    parser.add_argument(
        "-w",
        "--workspace",
        type=Path,
        help="Folder for the project you build (default: ./<the dungeon's project name>)",
    )
    parser.add_argument("--editor", help="Editor command for `edit`, e.g. vim or 'code -r'")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("play", help="Play the game (default)")
    check = sub.add_parser("check", help="Run the current room's quest check and exit")
    check.add_argument("room", nargs="?", help="Room id to check instead of the current one")
    sub.add_parser("status", help="Show progress and exit")
    sub.add_parser("rooms", help="List the dungeon's rooms and exit")
    sub.add_parser("dungeons", help="List the dungeons you can play and exit")
    return parser


def saved_dungeons(atlas: Atlas, cwd: Path) -> list[Dungeon]:
    """Dungeons with a save file in their default workspace under ``cwd``."""
    from azurath.state import PlayerState

    return [d for d in atlas.ordered() if PlayerState.path_for(cwd / d.workspace).exists()]


def resolve_dungeon(
    settings: AzurathSettings,
    atlas: Atlas,
    *,
    ask: Callable[[list[Dungeon]], Dungeon | None] | None = None,
) -> Dungeon | None:
    """Work out which dungeon to play. Returns None when it can't be decided without asking."""
    from azurath.state import PlayerState

    if settings.dungeon:
        return atlas.get(settings.dungeon)
    if settings.workspace is not None:
        saved = PlayerState.load(settings.workspace)
        if saved is not None:
            return atlas.get(saved.dungeon)
    elif len(found := saved_dungeons(atlas, Path.cwd())) == 1:
        return found[0]
    if len(atlas.dungeons) == 1:
        return atlas.ordered()[0]
    return ask(atlas.ordered()) if ask else None


def list_dungeons(console: Console, atlas: Atlas) -> None:
    from rich.table import Table

    started = {d.id for d in saved_dungeons(atlas, Path.cwd())}
    table = Table(title="Dungeons", header_style="bold", show_lines=True)
    table.add_column("#", justify="right")
    table.add_column("Dungeon")
    table.add_column("For")
    table.add_column("Rooms", justify="right")
    for i, dungeon in enumerate(atlas.ordered(), start=1):
        label = f"[bold]{dungeon.name}[/bold]  [dim]({dungeon.id})[/dim]\n{dungeon.tagline}"
        if dungeon.id in started:
            label += "\n[green]you've started this one[/green]"
        audience = " ".join(dungeon.audience.split())  # drop the YAML line breaks
        table.add_row(str(i), label, audience, str(len(dungeon.rooms)))
    console.print(table)


def chooser(console: Console) -> Callable[[list[Dungeon]], Dungeon | None]:
    def ask(dungeons: list[Dungeon]) -> Dungeon | None:
        from azurath.content import load_atlas

        list_dungeons(console, load_atlas())
        while True:
            try:
                answer = console.input(f"Which dungeon? [1-{len(dungeons)}] ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(dungeons):
                return dungeons[int(answer) - 1]
            match = [d for d in dungeons if d.id == answer.lower()]
            if match:
                return match[0]
            console.print(f"Type a number from 1 to {len(dungeons)}.")

    return ask


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Imported lazily so `azurath --help` stays fast.
    from pydantic import ValidationError
    from rich.console import Console

    from azurath.content import load_atlas
    from azurath.game import Game, WrongDungeonError
    from azurath.settings import AzurathSettings

    overrides: dict[str, object] = {}
    for key in ("dungeon", "workspace", "editor"):
        if getattr(args, key):
            overrides[key] = getattr(args, key)
    if args.no_color:
        overrides["color"] = False
    try:
        settings = AzurathSettings(**overrides)
    except ValidationError as exc:
        print(f"Invalid configuration:\n{exc}", file=sys.stderr)
        return 2

    console = Console(no_color=not settings.color, highlight=False)
    atlas = load_atlas()
    command = args.command or "play"
    if command == "dungeons":
        list_dungeons(console, atlas)
        return 0

    try:
        dungeon = resolve_dungeon(
            settings, atlas, ask=chooser(console) if command == "play" else None
        )
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 2
    if dungeon is None:
        if command == "play":
            return 1  # the player backed out of the menu
        names = ", ".join(atlas.dungeons)
        print(f"Which dungeon? Pass --dungeon ({names}).", file=sys.stderr)
        return 2

    try:
        game = Game(settings, console=console, dungeon=dungeon)
    except WrongDungeonError as exc:
        print(exc, file=sys.stderr)
        return 2
    if command == "play":
        game.run()
        return 0
    if command == "rooms":
        game.cmd_map("")
        return 0
    if not game.ws.root.exists():
        print(f"No workspace at {game.ws.root}. Run `azurath` to start.", file=sys.stderr)
        return 1
    if command == "status":
        game.cmd_status("")
        game.cmd_map("")
        return 0
    if command == "check":
        original = game.state.room
        if args.room:
            room = game.dungeon.find_room(args.room)
            if room is None:
                print(f"Unknown room {args.room!r}", file=sys.stderr)
                return 1
            game.state.room = room.id
        report = game.cmd_check("")
        game.state.room = original  # checking a room doesn't move you there
        game.save()
        return 0 if report is not None and report.passed else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
