---
name: add-room
description: Add a new room (lesson + quest) to one of the Azurath MUD's dungeons, rework an existing room, or add a whole new dungeon. Covers the dungeon layout, the room YAML schema, scaffold/solution files, writing the check function with the probe API, wiring exits, and verifying. Use whenever the task is "teach X in the game" or "add a lesson/quest/room".
---

# Add a room to Azurath

Azurath has several **dungeons**, each a self-contained curriculum for one audience,
under `src/azurath/dungeons/<dungeon>/` (see `docs/dungeons.md`). Pick the dungeon first,
and read its `dungeon.yaml`: the `audience` field decides how you write.

A room is four pieces that must agree with each other:

| Piece | Location |
|---|---|
| Lesson, mentor, quest text | `src/azurath/dungeons/<dungeon>/rooms/NN_<room_id>.yaml` |
| Starter files | `src/azurath/dungeons/<dungeon>/files/<room_id>/scaffold/` |
| Reference answer | `src/azurath/dungeons/<dungeon>/files/<room_id>/solution/` |
| Grader | a `@check("<room_id>")` function in `src/azurath/dungeons/<dungeon>/checks/*.py` |

## 1. Decide what the quest builds

Every room adds a real, useful piece to the project the player is building. Read the rooms
just before yours (`ls src/azurath/dungeons/<dungeon>/rooms/`) to see what already exists,
and build on it; don't reinvent it.

* **enterprise**: audience knows C#, PowerShell, unit testing and CI/CD. The project is
  `questboard`, a flat-layout Azure Functions app (`questboard/` package plus
  `function_app.py` at the root) with `Quest` (pydantic), `Settings`, `InMemoryRepository`,
  `Reward`, `orchestration.py` and so on.
* **pythonwood**: 13-year-olds with grade-school coding experience. The project is
  `critter-quest`, a critter battle game with a `critters/` package (`rules.py`,
  `actions.py`, `team.py`, `battle.py`) and `tests/`. Players use the game's `python` and
  `pytest` commands throughout. Until the Backpack Burrow (room 5) those run on the game's
  own interpreter. From then on the project has a uv-managed `.venv` (made with
  `uv init --bare --no-workspace`), `pyproject.toml` and `uv.lock`, and every command and
  check uses that `.venv`. Rooms after it may `uv add` packages.

## 2. Write the YAML

YAML here is **strict**: unknown keys, duplicate keys, wrong types and blank text are all
errors (see "YAML is strict" in `docs/dungeons.md`). The schemas are JSON Schema files in
`src/azurath/schemas/`; if you add a field to a model in `content.py`, add it to the
matching schema too (a test fails until you do).

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

**Lesson style (enterprise):**

* Map each idea onto the C#/.NET (or PowerShell) equivalent, usually with a comparison table.
* Show runnable code, and give PowerShell variants for shell commands.
* Point out the traps a C# developer will fall into.

**Lesson style (pythonwood):**

* Short pages, short sentences, friendly animal mentors, and concrete analogies (jars,
  recipes, save points). Compare with Scratch blocks where it helps.
* Introduce each new word before using it. Never condescend.
* Keep the story going: Grizzle the gnome (mutation testing) and Bolt the CI robot.
* Online safety: anything involving accounts or sharing (GitHub) is optional, and says to
  ask a parent, guardian or teacher.
* Failure messages in checks must tell a 13-year-old exactly what to try next.
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

Checks live in `src/azurath/dungeons/<dungeon>/checks/`. Each module gets its decorator with
`check = checks_for("<dungeon>")`, and `checks/__init__.py` imports every module (that's
what registers them). Enterprise groups checks by topic (`foundations`, `packaging`,
`domain`, `azure`, `golang`); pythonwood uses `quests.py`, with tidy-code helpers in
`tidy.py` (docstrings, function length, magic numbers, names). Shared pytest and mutation
helpers (`run_pytest`, `mutation_survives`, `stub_out`) are in `azurath.checks.testing`.

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
    run_pytest(ws, r, "tests/test_thing.py", "thing tests pass")  # from azurath.checks.testing
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
3. Use the **verify-room** skill: `uv run python .claude/skills/verify-room/verify_room.py my_room --dungeon <id>`
4. Play it once: use the **playtest** skill, or delegate to the `playtester` agent.
5. `uv run pytest -m slow -q` for the full walkthrough, then `uv run ruff check . && uv run ruff format --check .`
6. Add the room to the curriculum table in `README.md`.

## Pythonwood: every lesson is two rooms

Each Pythonwood lesson has a **guided room** (`<id>_guided`, `guided: true`) right before
its main room, wired between the previous main room and this one. The guided room's
scaffold is a file in `practice/` with numbered `# STEP n:` blocks, each offering a few
commented-out choices, and the solution is the scaffold with the right lines uncommented.
Keep practice files in `practice/` so they can never complete the main room's quest. Its
check lives in `checks/guided.py` (use `guided_file()`, `output_is()` and `quiz()`) and
judges behaviour, so uncommenting a wrong choice fails with a message about that STEP.
Guided rooms need two pages (a how-to and a step-by-step), award 50 XP, and have no item.

## Adding a whole dungeon

1. Create `src/azurath/dungeons/<id>/` with an `__init__.py`, and copy the layout of an
   existing dungeon (`rooms/`, `files/`, `checks/`).
2. Write `dungeon.yaml`: `id` (must match the folder), `name`, `tagline`, `audience`,
   `order`, `start`, `workspace` (a default project folder name that no other dungeon
   uses), `intro`, `readme` and `ranks` (starting at 0, with the top rank reachable from
   the main path's total XP).
3. Create `checks/__init__.py` importing your check modules.
4. Exits stay inside the dungeon. Cross-dungeon exits (`"other:room"`) are rejected until
   portals are built (see `docs/dungeons.md`).
5. `uv run pytest -q` (content tests run for every dungeon) and
   `uv run pytest -m slow -k <id>` (plays the whole dungeon).
