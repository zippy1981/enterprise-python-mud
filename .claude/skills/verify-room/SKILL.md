---
name: verify-room
description: Verify one Azurath room end to end (its check fails on an empty workspace, still fails after scaffold, and passes with the reference solution) without running the whole slow walkthrough. Use after editing any room's YAML, scaffold/solution files, or its check function in src/azurath/checks/.
---

# Verify a room

Every room must satisfy three rules, and the slow walkthrough test enforces them for
the whole game:

1. its check **fails** before the player does any work
2. it still **fails** after `scaffold` (starter files are never answers)
3. it **passes** once the reference solution files and commands are applied

`verify_room.py` checks the same three rules for **one** room. It replays the reference
solutions of every earlier room into a throwaway workspace first, because rooms build on
each other (the pydantic room needs the package, the uv lock and the tests from earlier
rooms).

## Run it

```bash
uv run python .claude/skills/verify-room/verify_room.py <room_id>
uv run python .claude/skills/verify-room/verify_room.py <room_id> --keep   # keep the workspace to inspect
uv run python .claude/skills/verify-room/verify_room.py <room_id> --setup-only DIR  # stop before the room, ready to play it
```

Room ids are the YAML `id:` values (`uv run azurath rooms` lists them), e.g. `gatehouse`,
`pydantic_citadel`, `durable_sanctum`, `gopher_forge`.

* Exit 0 and `VERIFIED` means all three rules hold.
* `BROKEN` names the rule that failed and prints each ✘ criterion with its detail.
* "An EARLIER room is broken" means a change rippled backwards. Verify that room first.

Rooms from `uv_speedway` on need network access, because the solutions run `uv add`. The
`gopher_*` rooms need Go and a C compiler. Side-quest rooms (`optional: true`) are only
replayed when the target is itself a side quest.

## Reading failures

| Symptom | Usual cause |
|---|---|
| rule 1 fails (check passes on an empty workspace) | a criterion uses `r.suggest` where it should use `r.require`, or the check returns early *before* recording a failure |
| rule 2 fails (scaffold passes) | the scaffold file is too complete; leave a `TODO` that the check actually tests for |
| rule 3 fails | the solution and the check disagree. Fix whichever one is wrong, and keep the brief, hints and solution consistent |
| `Unexpected error: ... (at questboard/x.py:12)` | the probe raised inside player code; the location points at the culprit |
| ruff failures from `cicd_foundry` onward | solution files must stay clean under the player's `ruff.toml` (E, F, I, UP, B at line length 100) |

## When done

After a room passes, run the fast suite (`uv run pytest -q`). Before opening a PR that
touches content, run the full walkthrough too (`uv run pytest -m slow -q`).
