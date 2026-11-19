---
name: add-room
description: Add a new room (lesson + quest) to the Azurath MUD, or substantially rework an existing one. Covers the room YAML schema, scaffold/solution files, writing the check function with the probe API, wiring exits, and verifying. Use whenever the task is "teach X in the game" or "add a lesson/quest/room".
---

# Add a room to Azurath

A room is four pieces that must agree with each other:

| Piece | Location |
|---|---|
| Lesson, mentor, quest text | `src/azurath/content/rooms/NN_<room_id>.yaml` |
| Starter files | `src/azurath/content/files/<room_id>/scaffold/` |
| Reference answer | `src/azurath/content/files/<room_id>/solution/` |
| Grader | a `@check("<room_id>")` function in `src/azurath/checks/*.py` |

## 1. Decide what the quest builds

The audience already knows **C#, PowerShell, unit testing and CI/CD**. Every room adds a
real, useful piece to the player's `questboard` repo, which is a flat-layout Azure
Functions app (`questboard/` package + `function_app.py` at the root). Read the rooms just
before yours (`ls src/azurath/content/rooms/`) to see what already exists: `Quest`
(pydantic), `Settings`, `InMemoryRepository`, `Reward`, `orchestration.py`, and so on.
Build on those; don't reinvent them.

## 2. Write the YAML

Copy the shape of an existing room. `08_pydantic_citadel.yaml` is a good model. The
schema is the pydantic models in `src/azurath/content.py`:

```yaml
id: my_room                      # snake_case, unique
name: The Something Hall
order: 17                        # position on the map; forward exits unlock when this quest passes
zone: Short topic label
optional: false                  # true = side quest (excluded from the main-path count)
description: |                   # 2-4 sentences of flavour; it's a MUD
exits:                           # always two-way: add the reverse exit in the neighbour's YAML
  south: previous_room
npc:
  name: Mentor Name
  aliases: [handle, other]       # first alias is what `talk <handle>` shows
  greeting: |                    # in character; frames the quest in .NET terms
  topics:                        # `ask <topic>`: 3-6 asides that don't fit the main pages
    topic name: |
pages:                           # 3-5 pages; each a focused Markdown lesson
  - title: "Quote titles containing: colons"
    body: |
quest:
  title: Imperative Title
  brief: |                       # exact, testable requirements; numbered steps
  check: my_room                 # name of the @check function
  scaffold:                      # workspace path -> file under files/<id>/scaffold/
    questboard/thing.py: thing.py
  hints: [...]                   # 3-4, from gentle to near-solution
  solution:
    files: {questboard/thing.py: thing.py}
    commands: ["uv add something"]   # run in the workspace after files are written
  commit_message: "Add thing"
  reward:
    xp: 250
    item:                        # a cheat sheet the player can `examine` forever
      name: Unique Item Name
      aliases: [short]
      text: |
```

**Lesson style:**

* Map each idea onto the C#/.NET (or PowerShell) equivalent, usually with a comparison table.
* Show runnable code, and give PowerShell variants for shell commands.
* Point out the traps a C# developer will fall into.
* In-game commands appear in backticks (`` `!uv add x` ``). The `!` prefix runs shell
  commands in the player's workspace.
* Verify every factual claim (library APIs, CLI flags, YAML/TOML behaviour) by actually
  running it. The `lesson-reviewer` agent exists for this.

**YAML gotchas:** quote any plain scalar containing `: ` or starting with a backtick or
`*`. Use `|` blocks for Markdown. Backslashes are literal inside `|` blocks but escapes
inside `"..."`.

## 3. Scaffold and solution files

* The **scaffold** compiles and imports cleanly but leaves `TODO`s that the check *detects*
  (raise `NotImplementedError`, return placeholder values). Never overwrite-safe content:
  `scaffold` skips files that already exist.
* The **solution** is the canonical answer. Later rooms' solutions overwrite cumulative files
  (`.gitignore`, `function_app.py`), so those must include everything from earlier rooms.
* Solution Python must pass the player's ruff config: rules E, F, I, UP, B, line length 100,
  target py311.

## 4. Write the check

Put it in the module for its topic group (`foundations`, `packaging`, `domain`, `azure`,
`golang`) or a new module imported in `_load_all()` in `src/azurath/checks/__init__.py`.

```python
@check("my_room")
def my_room(ws: Workspace, r: Report) -> None:
    tree = r.python_file(ws, "questboard/thing.py")  # requires exists + parses; returns AST or None
    if tree is None:
        return
    r.require(cond, "human-readable criterion with `code`", "hint shown when it fails")
    r.suggest(cond, "nice-to-have; never blocks completion")
    r.probe(
        ws.probe("""
        from questboard.thing import do_it
        expect(do_it(2) == 4, f"do_it(2) returned {do_it(2)!r}, expected 4")
    """),
        "`do_it` behaves as specified",
    )
    run_pytest(ws, r, "tests/test_thing.py", "thing tests pass")  # from checks.packaging
```

Rules:

* **Never import player code into the game process.** Use `ws.probe(...)` (runs in the
  player's `.venv` interpreter, cwd = workspace, with `expect(cond, msg)` available) or
  `ws.run([...])`.
* Each failure message must say what was expected **and** what was observed.
* Return early when a prerequisite is missing, but only after `r.require` has recorded
  the failure. A check that records nothing passes vacuously.
* Prefer behaviour probes over source-text matching. Use AST helpers (`calls`,
  `defined_functions`, `decorator_names`) only for things behaviour can't show, such as
  "uses `yaml.safe_load`" or "no `datetime.now` in the orchestrator".
* The check must not crash on garbage input. `tests/test_game.py::test_checks_survive_garbage_code`
  enforces this.

## 5. Wire it up and verify

1. Add the reverse exit in the neighbouring room's YAML.
2. `uv run pytest -q tests/test_content.py` checks schema, files, exits, reachability and
   item uniqueness.
3. Use the **verify-room** skill: `uv run python .claude/skills/verify-room/verify_room.py my_room`
4. Play it once: use the **playtest** skill, or delegate to the `playtester` agent.
5. `uv run pytest -m slow -q` for the full walkthrough, then `uv run ruff check . && uv run ruff format --check .`
6. Add the room to the curriculum table in `README.md`.
