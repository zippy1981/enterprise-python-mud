# Azurath: the Python MUD

A text adventure (a MUD) that teaches Python by having you build a real project, one quest
at a time. Each room teaches one topic and ends with a quest, which you complete by writing
real code in a real git repository that you edit in VS Code, vim or any editor. The game
runs *your* code to grade it. Pass, and it commits your work, so by the end the repo's git
history is your journey.

Azurath has two **dungeons** for two very different players:

| Dungeon | For | You build |
|---|---|---|
| **The Realm of Azurath** (`enterprise`) | professional developers who know **C#, PowerShell, unit testing and CI/CD** | `questboard`: a tested, linted, CI-gated **Azure Functions app with a Durable orchestration** |
| **The Pythonwood** (`pythonwood`) | **13-year-olds** with grade-school coding experience (Scratch, a little Python) | `critter-quest`: a tidy, **tested** critter battle game, with a CI robot |

```
╭─ The Durable Sanctum  ·  Durable Functions orchestrations ──────────────────╮
│ A vast circular hall where an orchestra plays without pause, even though    │
│ half the musicians are asleep. Whenever the conductor turns a page, the     │
│ entire symphony replays from the first bar…                                 │
╰─────────────────────────────────────────────────────────────────────────────╯
The Orchestrator is here.  (talk orchestrator)
A tome lies open: 4 pages  (read · 0/4 read)
Quest: Conduct the Symphony · open  (quest)
Exits: south → The Functions Docks  ·  north → The Throne Room 🔒  ·  east → The Gopher Forge 🔒
```

## The Realm of Azurath (`enterprise`)

Every idea is mapped onto its .NET equivalent.

| # | Room | You learn | You build in questboard |
|---|------|-----------|-------------------------|
| 0 | The Gatehouse | the game, running Python, `__name__`, editing with VS Code or vim | `hello.py` |
| 1 | Hall of Basics | syntax vs C#, type hints, comprehensions (LINQ), generators, exceptions, f-strings | `basics.py` |
| 2 | The Venv Crypt | virtual environments, activation (PowerShell & bash), pip, `requirements.txt` | `.venv`, pins, `.gitignore` |
| 3 | The Module Library | modules vs packages, `__init__.py`, `__main__.py`, `sys.path`, flat vs src layout | the `questboard` package |
| 4 | The TOML Forge | TOML, `pyproject.toml` as your `.csproj`, build backends, specifiers | `pyproject.toml` |
| 5 | The uv Speedway | uv as your `dotnet` CLI: `add`, `sync`, `run`, `uv.lock`, Python pinning | dependencies + lock file |
| 6 | The Testing Grounds | pytest for xUnit people: parametrize, fixtures, `raises`, **mutation-checked** | `tests/test_text.py` |
| 7 | The Class Barracks | classes, dunders, dataclasses as records, ABCs vs Protocols, generics | `Reward`, `InMemoryRepository[T]` |
| 8 | The Pydantic Citadel | pydantic v2 models, validators, computed fields, JSON in/out | the `Quest` model |
| 9 | The Settings Observatory | pydantic-settings, env vars, `.env`, `SecretStr`, cached settings ≈ `IOptions<T>` | `Settings` |
| 10 | The YAML Scriptorium | YAML 1.1 footguns (Norway!), anchors, **safe** loading | seed data + loader |
| 11 | The CI/CD Foundry | ruff, mypy/pyright, GitHub Actions with uv (and the Azure Pipelines equivalent) | `ci.yml`, `ruff.toml` |
| 12 | The Functions Docks | Azure Functions v2 model, decorators, HTTP triggers, `host.json`, testing functions | `function_app.py` |
| 13 | The Durable Sanctum | orchestrations as **generators**, replay & determinism, fan-out/fan-in, testing with a fake context | a Durable workflow |
| 14 | The Gopher Forge *(side quest)* | **Go extensions I**: cgo `-buildmode=c-shared` + ctypes (P/Invoke for Python) | `goext/`, `native.py` |
| 15 | The Gopher Sanctum *(side quest)* | **Go extensions II**: a real CPython C-API extension module in Go, GIL, refcounts, stubs | `_goquest` module |
| 16 | The Throne Room | `uv export` for deployment, `.funcignore`, deploying, managed identity, logging/OTel | ready to ship |

Every room has a mentor to `talk` to and `ask` about side topics (asyncio, the GIL, Azure
Artifacts feeds, Key Vault, PyO3, retries, entities…), and every quest rewards an item: a
cheat sheet you can `examine` any time.

## The Pythonwood (`pythonwood`)

Short, friendly lessons with animal mentors and lots of Scratch comparisons. It stresses
**variables, functions and organizing code well**, and teaches testing and CI at a
grade-school level: write the test first and watch it go 🔴 red, make it 🟢 green, then 🧹
tidy. When you `check`, *Grizzle the gnome* breaks your functions on purpose, and your
tests have to catch him. For the first five rooms there's nothing to install: the game's
`python` and `pytest` commands just work. Then the Backpack Burrow introduces **packages,
virtual environments and uv**: the project gets its own `.venv` "backpack", and from then
on the game's commands (and the CI robot) use it.

| # | Room | You learn | You build in critter-quest |
|---|------|-----------|----------------------------|
| 0 | The Trailhead | running a program, `print`, comments, reading errors | `hello.py` |
| 1 | Variable Grove | variables as labelled jars, types, **good names**, f-strings | `critter.py` |
| 2 | Function Falls | `def`, parameters, **return vs print**, `if`, one job per function | `actions.py` |
| 3 | The Testing Meadow | tests with `assert` and pytest, **red → green → tidy**, edge cases | `tests/test_actions.py` + `rest()` written test-first |
| 4 | The Tidy Treehouse | packages and imports, **named constants instead of magic numbers**, docstrings, refactoring safely | the `critters/` package |
| 5 | The Backpack Burrow | **packages** (code you can borrow from PyPI), **virtual environments** as a project's own backpack, **uv** (`init`, `add`, `add --dev`, `run`, `sync`), the packing list and the receipt | `pyproject.toml`, `uv.lock`, `.venv`, `fun.py` |
| 6 | The Looping Lagoon | lists, dictionaries, `for` loops, the empty-list edge case | `critters/team.py` |
| 7 | The Robot Tower | git commits as save points, **CI as a robot that runs every test** (with uv) | `.github/workflows/tests.yml` |
| 8 | The Critter Arena | planning, `while` loops, `main()`, all the tidy-code rules together | `critters/battle.py`, `main.py` |

**For parents and teachers:** a grown-up may need to help install uv and git (see Quick
start). After that, everything happens inside the game. The CI room's optional step of
putting the project on GitHub needs an account, and GitHub's minimum age is 13; the game
tells players to ask a parent, guardian or teacher first.

## Quick start

You need **Python 3.11+**, **git** and **[uv](https://docs.astral.sh/uv/)**.

```powershell
# Windows
winget install --id=astral-sh.uv -e
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then:

```bash
git clone https://github.com/zippy1981/enterprise-python-mud.git
cd enterprise-python-mud
uv run azurath
```

The first run asks which dungeon you want (or pass `--dungeon pythonwood` /
`--dungeon enterprise`), then creates your project in `./questboard` or `./critter-quest`.
Both are ignored by this repo's git. Next time, `uv run azurath` finds your save and carries
on. Choose another location with `--workspace PATH` or `AZURATH_WORKSPACE`, and list the
dungeons with `uv run azurath dungeons`.

Optional extras, for later rooms:

* [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
  and [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) to run your
  app locally (the quests don't require them)
* [Go](https://go.dev/dl/) and a C compiler (gcc / Xcode CLT / MinGW-w64) for the Gopher side quests

## Playing in VS Code

1. Open this folder in VS Code and install the recommended extensions when prompted.
2. Run the **Azurath: play** task (`Ctrl+Shift+B`), or just `uv run azurath` in the integrated
   terminal.
3. `edit hello.py` opens the file in the editor next to the terminal (the game detects VS Code's
   terminal and uses `code -r`). Save, switch back, `check`.

Your `questboard/` folder shows up in the Explorer. When you reach the venv rooms, select
`questboard/.venv` as the interpreter (**Python: Select Interpreter**) for IntelliSense on your
dependencies. You can also run **Azurath: check current quest** from a second terminal
without leaving your editor.

## Playing with vim (or anything else)

Outside VS Code, `edit <file>` uses `$VISUAL`/`$EDITOR`, falling back to vim. `vim <file>` always
uses vim and shows a survival cheat sheet first. `:wq` returns you to the game. Set
`AZURATH_EDITOR` (e.g. `nano`, `hx`, `code -r --wait`) to choose explicitly.

## Commands

| | |
|---|---|
| **Explore** | `look` · `north`/`n` … · `go <dir>` · `goto <room>` · `map` · `talk` · `ask <topic>` |
| **Learn** | `read` / `read 3` / `read back` · `pages` · `quest` · `hint` · `check` · `scaffold` · `solution [apply]` |
| **Code** | `edit <file>` · `vim <file>` · `code [file]` · `ls` · `cat <file>` · `python <file>` · `pytest` · `!<shell command>` · `shell` · `commit` · `log` · `workspace` |
| **You** | `inventory` · `examine <item>` · `status` · `save` · `quit` · `help [command]` |

`!` commands run in your workspace with its `.venv` activated, so `!uv add pydantic`,
`!python -m pytest -q` and `!git status` all do what you'd expect. The game removes its *own*
virtualenv from `PATH` first, so nothing leaks between the two.

`python <file>` and `pytest` run your code and tests with your project's interpreter (its
`.venv` if it has one, otherwise the game's own). `pytest` reports the result as GREEN or RED.

From your shell: `azurath check` (exit code 0/1), `azurath check <room>`, `azurath status`,
`azurath rooms`, `azurath dungeons`. Add `--dungeon <id>` when it can't tell which you mean.

## Configuration

Settings are loaded with **pydantic-settings**, the same pattern you build in the Settings
Observatory (see [`src/azurath/settings.py`](src/azurath/settings.py)). Priority: CLI flags →
`AZURATH_*` environment variables → `azurath.toml` in the current directory. See
[`azurath.example.toml`](azurath.example.toml) for every option (`workspace`, `editor`, `shell`,
`auto_commit`, `code_theme`, `color`).

## How it works

```
src/azurath/
  cli.py            argparse entry point (azurath = "azurath.cli:main"); picks the dungeon
  game.py           the game loop and every command (registered with a decorator)
  content.py        pydantic models: Atlas → Dungeon → Room; loads YAML via importlib.resources
  workspace.py      runs the player's code in subprocesses with *their* interpreter; git helpers
  checks/           the check framework (Report, the registry, shared pytest/mutation helpers)
  editor.py         VS Code / $EDITOR / vim selection
  state.py          the save file (a pydantic model → JSON in <project>/.azurath/)
  dungeons/
    enterprise/     dungeon.yaml · rooms/*.yaml · files/<room>/{scaffold,solution}/ · checks/
    pythonwood/     the same layout, for the second dungeon
```

See [docs/dungeons.md](docs/dungeons.md) for how dungeons work, and the plan for connecting
them to each other in future.

The game's own code deliberately uses the techniques it teaches: pyproject + uv, pydantic
models for the YAML content, pydantic-settings with a TOML source, decorator registries,
dataclasses, `importlib.resources`, pytest fixtures. Reading it after you finish is a good
final exam.

Checks never import your code into the game process. Each one runs a small probe script with
your workspace's interpreter and reports a ✔/✘ list, and some go further: the Testing Grounds
mutates your code to prove your tests can fail, and the YAML Scriptorium feeds your loader a
malicious payload.

## Developing

```bash
uv sync
uv run pytest            # fast tests
uv run pytest -m slow    # plays the ENTIRE game with the reference solutions (network; Go optional)
uv run ruff check . && uv run ruff format --check .
```

The walkthrough test is the safety net for content changes. For every room it asserts the check
fails on an empty workspace, still fails after `scaffold`, and passes once the reference solution
and commands are applied.

To add a room: drop a YAML file in `src/azurath/dungeons/<dungeon>/rooms/`, put its files under
`dungeons/<dungeon>/files/<room_id>/{scaffold,solution}/`, write a `@check("<room_id>")`
function in `dungeons/<dungeon>/checks/`, and link it with `exits`. To add a dungeon, copy
the layout of an existing one and write a `dungeon.yaml`; the game discovers it. `tests/test_content.py` will tell you what you
forgot.

### Working on Azurath with Claude Code

The repo ships project [skills](.claude/skills) and [subagents](.claude/agents) for
maintaining the game:

| | Name | Use it to |
|---|---|---|
| skill | `add-room` | add or rework a room: YAML schema, scaffold/solution files, writing the check, wiring exits |
| skill | `verify-room` | check one room end to end (fails empty, fails after scaffold, passes with the solution) in seconds, or set up a workspace already standing in a given room (`--setup-only`) |
| skill | `playtest` | drive the real CLI with scripted input and see exactly what a player sees |
| agent | `lesson-reviewer` | audit a room's lesson for technical accuracy and .NET comparisons, verifying claims by running code |
| agent | `playtester` | play a room as a C# developer new to Python, without spoilers, and report friction |
| agent | `quest-breaker` | red-team a check: wrong code that passes, and valid code that fails |

A typical content change: `add-room`, then `verify-room`, then the `lesson-reviewer`,
`quest-breaker` and `playtester` agents, then `uv run pytest -m slow`.

## License

MIT
