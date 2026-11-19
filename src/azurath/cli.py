"""Command-line entry point: ``azurath [play|check|status|rooms]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from azurath import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="azurath",
        description="Azurath: a MUD that teaches enterprise Python on Azure.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-w",
        "--workspace",
        type=Path,
        help="Folder for your questboard repo (default: ./questboard)",
    )
    parser.add_argument("--editor", help="Editor command for `edit`, e.g. vim or 'code -r'")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("play", help="Play the game (default)")
    check = sub.add_parser("check", help="Run the current room's quest check and exit")
    check.add_argument("room", nargs="?", help="Room id to check instead of the current one")
    sub.add_parser("status", help="Show progress and exit")
    sub.add_parser("rooms", help="List the curriculum and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Imported lazily so `azurath --help` stays fast.
    from pydantic import ValidationError

    from azurath.game import Game
    from azurath.settings import AzurathSettings

    overrides: dict[str, object] = {}
    if args.workspace:
        overrides["workspace"] = args.workspace
    if args.editor:
        overrides["editor"] = args.editor
    if args.no_color:
        overrides["color"] = False
    try:
        settings = AzurathSettings(**overrides)
    except ValidationError as exc:
        print(f"Invalid configuration:\n{exc}", file=sys.stderr)
        return 2

    game = Game(settings)
    command = args.command or "play"
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
            room = game.world.find_room(args.room)
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
