"""Verify one Azurath room end to end, without playing the whole game.

    uv run python .claude/skills/verify-room/verify_room.py <room_id> [--dungeon ID] [--keep]

Builds a throwaway workspace for the room's dungeon, replays the reference solution of every
earlier room on the target's path (each must pass its check and is committed, as
in the game), then asserts three things about the target room:

1. its check FAILS on the workspace as earlier rooms left it,
2. it still FAILS after `scaffold` (starter files are not answers),
3. it PASSES after the room's reference solution files and commands are applied.

Exit code 0 means all three held. `--keep` leaves the workspace on disk so you can
poke at it (cd there and run `uv run --project <repo> azurath check`).

`--setup-only DIR` replays the earlier rooms into DIR/<project>, records them as
completed in the save file, puts the player in the target room, and stops. Then
`cd DIR && uv run --project <repo> azurath` plays the target room for real.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from azurath.checks import Report, run_check
from azurath.content import Dungeon, Room, load_atlas
from azurath.state import PlayerState
from azurath.workspace import Workspace


def print_report(label: str, report: Report, *, show_passes: bool = False) -> None:
    verdict = "PASS" if report.passed else "FAIL"
    print(f"  [{verdict}] {label}")
    for item in report.items:
        if item.ok and not show_passes:
            continue
        mark = "ok " if item.ok else ("opt" if item.optional else "XX ")
        print(f"      {mark} {item.description}")
        if item.detail and not item.ok:
            for line in item.detail.strip().splitlines()[:12]:
                print(f"            {line}")


def apply_solution(ws: Workspace, dungeon: Dungeon, room: Room) -> None:
    quest = room.quest
    assert quest is not None
    for target, source in quest.solution.files.items():
        ws.write(target, dungeon.room_text(room.id, "solution", source))
    for command in quest.solution.commands:
        proc = subprocess.run(
            command, shell=True, cwd=ws.root, env=ws.env(), capture_output=True, text=True
        )
        if proc.returncode:
            raise SystemExit(
                f"{room.id}: solution command failed: {command}\n{proc.stdout}{proc.stderr}"
            )


def apply_scaffold(ws: Workspace, dungeon: Dungeon, room: Room) -> list[str]:
    quest = room.quest
    assert quest is not None
    written = []
    for target, source in quest.scaffold.items():
        if not ws.exists(target):
            ws.write(target, dungeon.room_text(room.id, "scaffold", source))
            written.append(target)
    return written


def path_to(dungeon: Dungeon, target: Room) -> list[Room]:
    """Earlier rooms the target depends on. Side-quest rooms only for side-quest targets."""
    rooms = dungeon.ordered()
    return [r for r in rooms if r.order < target.order and (target.optional or not r.optional)]


def prepare_environment(scratch: Path) -> None:
    """Make `python` resolvable and give git an identity, as the test suite does."""
    shim = scratch / "shim-bin"
    shim.mkdir()
    base = Path(getattr(sys, "_base_executable", sys.executable))
    (shim / ("python.exe" if os.name == "nt" else "python")).symlink_to(base)
    os.environ["PATH"] = f"{shim}{os.pathsep}{os.environ.get('PATH', '')}"
    for var, value in {
        "GIT_AUTHOR_NAME": "Azurath Verify",
        "GIT_AUTHOR_EMAIL": "verify@azurath.invalid",
        "GIT_COMMITTER_NAME": "Azurath Verify",
        "GIT_COMMITTER_EMAIL": "verify@azurath.invalid",
    }.items():
        os.environ.setdefault(var, value)
    for key in list(os.environ):
        if key.startswith("QUESTBOARD_"):
            del os.environ[key]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("room", help="room id, e.g. pydantic_citadel (see `uv run azurath rooms`)")
    parser.add_argument("--dungeon", help="dungeon id; needed only if the room id is ambiguous")
    parser.add_argument("--keep", action="store_true", help="keep the scratch workspace")
    parser.add_argument(
        "--setup-only",
        type=Path,
        metavar="DIR",
        help="replay earlier rooms into DIR/<project folder> and stop, ready to play the room",
    )
    args = parser.parse_args(argv)

    atlas = load_atlas()
    pool = [atlas.get(args.dungeon)] if args.dungeon else atlas.ordered()
    matches = [
        (d, d.rooms.get(args.room) or d.find_room(args.room))
        for d in pool
        if d.rooms.get(args.room) or d.find_room(args.room)
    ]
    if not matches:
        known = "; ".join(f"{d.id}: {', '.join(d.rooms)}" for d in pool)
        print(f"unknown room {args.room!r}. Rooms by dungeon: {known}", file=sys.stderr)
        return 2
    if len(matches) > 1:
        names = ", ".join(d.id for d, _ in matches)
        print(f"{args.room!r} is in several dungeons ({names}); pass --dungeon", file=sys.stderr)
        return 2
    dungeon, target = matches[0]

    if args.setup_only:
        scratch = args.setup_only.resolve()
        if (scratch / dungeon.workspace).exists():
            print(
                f"{scratch / dungeon.workspace} already exists; pick an empty DIR", file=sys.stderr
            )
            return 2
        scratch.mkdir(parents=True, exist_ok=True)
        args.keep = True
    else:
        scratch = Path(tempfile.mkdtemp(prefix=f"azurath-verify-{target.id}-"))
    prepare_environment(scratch)
    ws = Workspace(scratch / dungeon.workspace)
    ws.initialize()
    state = PlayerState.new(dungeon.id, dungeon.start, name="Playtester")
    state.save(ws.root)
    ok = True
    try:
        prior = path_to(dungeon, target)
        print(f"Replaying {len(prior)} earlier room(s) into {ws.root}")
        for room in prior:
            apply_solution(ws, dungeon, room)
            report = run_check(dungeon, room.quest.check, ws)
            if not report.passed:
                print_report(f"{room.id}: reference solution", report)
                print(f"\nAn EARLIER room ({room.id}) is broken; fix it first.")
                return 1
            ws.commit(room.quest.commit_message or f"Complete quest: {room.quest.title}")
            if state.complete(room.id):  # award what the game would have
                state.xp += room.quest.reward.xp
                if room.quest.reward.item:
                    state.inventory.append(room.quest.reward.item.name)
            state.visit(room.id)
            print(f"  [PASS] {room.id}")

        if args.setup_only:
            state.visit(target.id)
            state.save(ws.root)
            print(f"\nReady: you're in {target.name}. Play it with:")
            print(f"  cd {scratch} && uv run --project <repo> azurath")
            return 0

        print(f"\nVerifying {target.id} ({target.name})")
        empty = run_check(dungeon, target.quest.check, ws)
        print_report("1. check fails before any work", empty)
        ok &= not empty.passed

        if target.quest.scaffold:
            written = apply_scaffold(ws, dungeon, target)
            print(f"     scaffold wrote: {', '.join(written) or 'nothing new'}")
            scaffolded = run_check(dungeon, target.quest.check, ws)
            print_report("2. check still fails after scaffold", scaffolded)
            ok &= not scaffolded.passed
        else:
            print("  [skip] 2. no scaffold for this quest")

        apply_solution(ws, dungeon, target)
        solved = run_check(dungeon, target.quest.check, ws)
        print_report("3. check passes with the reference solution", solved, show_passes=True)
        ok &= solved.passed
    finally:
        if args.keep:
            print(f"\nWorkspace kept at {ws.root}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)
        if args.setup_only:
            shutil.rmtree(scratch / "shim-bin", ignore_errors=True)

    expectations = "empty fails, scaffold fails, solution passes"
    print(f"\n{'VERIFIED' if ok else 'BROKEN'}: {target.id} ({expectations})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
