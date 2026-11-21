# Dungeons

Azurath holds several **dungeons**. Each one is a complete curriculum for one
audience, with its own rooms, mentors, ranks and project.

| Dungeon | id | For | Project the player builds |
|---|---|---|---|
| The Realm of Azurath | `enterprise` | professional C#/PowerShell developers new to Python | `questboard`, an Azure Functions app with a Durable orchestration |
| The Pythonwood | `pythonwood` | 13-year-olds with grade-school coding experience | `critter-quest`, a tested critter battle game with its own uv-managed `.venv` |

## Layout

A dungeon is a self-contained folder, and a Python package, under
`src/azurath/dungeons/<id>/`:

```
dungeons/pythonwood/
  __init__.py
  dungeon.yaml            id, name, tagline, audience, order, start room,
                          default workspace folder, intro, README, ranks
  rooms/NN_<room>.yaml    one file per room (lesson, mentor, quest)
  files/<room>/scaffold/  starter files
  files/<room>/solution/  reference answers (the walkthrough test plays them)
  checks/__init__.py      imports the check modules, which registers them
  checks/*.py             check = checks_for("pythonwood"); @check("<name>") ...
```

The game discovers dungeons by looking for `dungeons/*/dungeon.yaml`
(`azurath.content.load_atlas()`). Nothing else needs registering.

## YAML is strict

All YAML is loaded with `azurath.yamlstrict` (a SafeLoader that **rejects duplicate keys**,
since PyYAML silently keeps the last one) and validated against **JSON Schema** files
(draft 2020-12) in `src/azurath/schemas/`:

* **unknown keys are errors** (`additionalProperties: false`), so a typo like `exit:` for
  `exits:` fails instead of being ignored
* **no type coercion**: `xp: "100"` is an error, not 100
* **string rules**: ids are `snake_case`, exits use real compass directions, visible text
  can't be blank, and file paths must be relative with forward slashes and no `..`

| Schema | For |
|---|---|
| `room.schema.json` | `dungeons/<id>/rooms/*.yaml` |
| `dungeon.schema.json` | `dungeons/<id>/dungeon.yaml` |
| `workflow.schema.json` | GitHub Actions workflows (this repo's and the ones players write) |
| `quests.schema.json` | the YAML Scriptorium's quest seed data |
| `common.schema.json` | shared `$defs` (identifier, text, relative path, file map) |

The JSON files are the single source of truth. `azurath.yamlschema` validates against them
when the game loads its content (so a bad room stops the game with the file and the path to
the problem), `tests/test_yaml_schemas.py` validates **every** tracked `.yaml`/`.yml` file
and fails if a new one has no schema rule, and `.vscode/settings.json` points the YAML
extension at the same files, so mistakes are underlined as you type. The pydantic models in
`azurath/content.py` still hold the loaded data; a test checks the schemas cover every
model field, so add a new field to both.

## How a session picks its dungeon

1. `--dungeon` / `AZURATH_DUNGEON` / `dungeon = "..."` in `azurath.toml`
2. otherwise, the dungeon recorded in the save file of `--workspace`, if given
3. otherwise, the one dungeon with a save in its default folder under the
   current directory (`./questboard`, `./critter-quest`)
4. otherwise `azurath` (play) shows a menu, and scripted commands (`check`,
   `status`, `rooms`) ask for `--dungeon`

A workspace belongs to exactly one dungeon. Its save (`.azurath/save.json`)
records the dungeon id, and opening it with a different dungeon is an error.
Saves written before there were several dungeons have no `dungeon` field, so
they load as `enterprise`.

## What a dungeon controls

* **Rooms and progression**: forward exits unlock when the current room's quest passes
* **Ranks**: `ranks: [[xp, title], ...]`, starting at 0. Make the top threshold
  reachable from the main path's total XP (a test checks the main path's end
  has an epilogue; the walkthrough checks finishing earns the top rank).
* **Intro and README**: shown when a new workspace is created
* **Workspace folder name**: must be unique across dungeons (a test checks this)
* **Checks**: registered under `(dungeon_id, check_name)`, so two dungeons may
  reuse room or check names without clashing

## Projects nested inside other projects

By default a workspace is created under the current directory, which is often
this repo (itself a uv project). Plain `uv init` in a nested folder would add
it to the outer project as a **uv workspace member**: it edits the outer
`pyproject.toml` and puts packages in the *outer* virtualenv, which can be the
game's own. So:

* the Pythonwood teaches `uv init --bare --no-workspace`
* the game refuses a `!uv init` without `--no-workspace` when an enclosing
  `pyproject.toml` exists (`Workspace.enclosing_project`), explaining why
* the Backpack Burrow check detects a workspace that was already joined
  (`Workspace.joined_uv_workspace`) and names the file to fix

## Plan: connecting dungeons (not built yet)

The goal is to let a room in one dungeon lead to a room in another: for
example, the Pythonwood's arena could open a portal to the enterprise
Gatehouse for players who outgrow it. The refactor was shaped so this can be
added without reworking content.

**Already in place**

* `RoomRef.parse("dungeon:room")` is the single parser for exit targets.
  Unqualified targets are local to the current dungeon.
* `Atlas.resolve(current_dungeon, target)` is the single place an exit is
  followed. It already handles qualified refs.
* `Dungeon` validation **rejects** qualified exits today, with a message
  pointing here, so no content can depend on half-built behaviour.
* Check registration, room files and ranks are all namespaced by dungeon, so
  rooms from two dungeons can coexist in one session.
* Saves record which dungeon they belong to.

**Still to do when portals are built**

1. **Allow qualified exits**: drop the rejection in `Dungeon._check_links`, and
   validate cross-dungeon targets in a new `Atlas`-level validator (the target
   dungeon and room must exist).
2. **Player profile**: today progress lives in each workspace's save. Add a
   profile in the user's data directory (`platformdirs.user_data_dir("azurath")`)
   holding the player's name and a map of `dungeon_id -> workspace path`, so
   crossing a portal knows where that dungeon's project lives (or offers to
   create it).
3. **Switching dungeons in `Game`**: `cmd_go` currently resolves within
   `self.dungeon`. Route it through `Atlas.resolve`. When the target is in
   another dungeon, save, then swap `self.dungeon`, `self.ws` and `self.state`
   for the other dungeon's (from the profile).
4. **Locking rules across portals**: decide whether a portal requires the
   source room's quest (as forward exits do now), a rank, or completion of the
   whole source dungeon. Express it in YAML as a portal property, not as code.
5. **Shared items** (optional): cheat-sheet items are per dungeon today. If a
   portal should carry them over, move `inventory` into the profile.
6. **Tests**: a two-dungeon walkthrough that crosses a portal, and a content
   test that every portal has a matching way back.
