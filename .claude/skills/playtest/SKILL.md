---
name: playtest
description: Drive the Azurath MUD non-interactively to see exactly what a player sees, for checking rendering, command behaviour, lesson flow and quest feedback after a change. Use when asked to try, run, demo or screenshot the game, or to confirm a gameplay change works in the real CLI rather than just in unit tests.
---

# Playtest the game

The game reads commands from stdin, so you can script a session by piping input. Run it
in a scratch directory so the project folder it creates is disposable. Pick the dungeon
with `--dungeon` (`uv run azurath dungeons` lists them); without it, a fresh folder shows a
menu, which takes one more line of input.

```bash
PLAY=$(mktemp -d) && cd "$PLAY"
printf 'y\nTester\nlook\nread\ntalk\nquest\nscaffold\ncheck\nhint\nmap\nquit\n' \
  | COLUMNS=100 uv run --project /path/to/enterprise-python-mud azurath --dungeon pythonwood
```

* On a fresh workspace the first two answers are **"Create it now? → y"** and **your
  name**. On later runs the game greets you and goes straight to the prompt.
* `COLUMNS=100` gives stable wrapping. Add `--no-color` for plain text, or leave colour on
  to check styling.
* State persists in `<project>/.azurath/save.json` (`questboard/` for enterprise,
  `critter-quest/` for pythonwood), so a second piped session resumes
  where the first stopped.
* Editors are interactive. To exercise `edit` in a script, set `EDITOR=cat` (or `true`),
  which stands in for a blocking editor.

## Jump to a room without solving everything

Forward exits only open once the earlier quests are complete. To start a session standing
in a later room, with every earlier room solved, committed and marked complete in the save:

```bash
uv run python .claude/skills/verify-room/verify_room.py <room_id> --setup-only "$PLAY"
cd "$PLAY"
printf 'look\nread\nquest\nscaffold\ncheck\nquit\n' | COLUMNS=100 uv run --project /path/to/enterprise-python-mud azurath
```

`$PLAY` must not already contain that dungeon's project folder.

## What to look for

* Markdown renders cleanly: tables have no stray `|`, code blocks are highlighted, and
  nothing in square brackets has vanished (rich markup eats unescaped `[...]`).
* `check` output: every ✘ explains what was expected and what was found, and the hint
  text points somewhere useful.
* Completing a quest shows the XP, the item, the git commit and the unlocked exit.
* Lock behaviour: forward exits are blocked until the quest passes; backward exits are
  always open.

For automated assertions, prefer the `make_player` fixture in `tests/conftest.py`, which
drives `Game.handle()` and returns the captured output of each command. See
`tests/test_game.py` for examples.
