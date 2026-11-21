"""The game loop and every command the player can type."""

from __future__ import annotations

import difflib
import os
import shlex
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.tree import Tree

from azurath import __version__, gitcheck
from azurath.checks import Report, run_check
from azurath.content import DIRECTIONS, Dungeon, Item, Room, load_dungeon
from azurath.editor import VIM_CHEATSHEET, choose_editor, in_vscode_terminal
from azurath.render import Renderer
from azurath.settings import AzurathSettings
from azurath.state import PlayerState
from azurath.workspace import Workspace

QUIT = object()

BANNER = r"""
[bold cyan]    _                       _   _
   / \    _____   _ _ __ __ _| |_| |__
  / _ \  |_  / | | | '__/ _` | __| '_ \
 / ___ \  / /| |_| | | | (_| | |_| | | |
/_/   \_\/___|\__,_|_|  \__,_|\__|_| |_|[/bold cyan]
[dim]      the Python MUD  ·  v{version}[/dim]
"""


class WrongDungeonError(Exception):
    """The workspace's save file belongs to a different dungeon."""


@dataclass
class Command:
    name: str
    aliases: tuple[str, ...]
    usage: str
    help: str
    fn: Callable[[Game, str], object]


COMMANDS: dict[str, Command] = {}
_LOOKUP: dict[str, Command] = {}


def command(name: str, *aliases: str, usage: str = "", help: str = "") -> Callable:
    def register(fn: Callable[[Game, str], object]) -> Callable[[Game, str], object]:
        cmd = Command(name, aliases, usage or name, help, fn)
        COMMANDS[name] = cmd
        for key in (name, *aliases):
            _LOOKUP[key] = cmd
        return fn

    return register


class Game:
    def __init__(
        self,
        settings: AzurathSettings,
        console: Console | None = None,
        input_fn: Callable[[str], str] | None = None,
        dungeon: Dungeon | None = None,
    ) -> None:
        self.settings = settings
        self.console = console or Console(no_color=not settings.color, highlight=False)
        self.out = Renderer(self.console, settings.code_theme)
        self._input = input_fn or (lambda prompt: self.console.input(prompt))
        self.dungeon = dungeon or load_dungeon(settings.dungeon or "enterprise")
        root = settings.workspace or (Path.cwd() / self.dungeon.workspace)
        self.ws = Workspace(root.resolve())
        saved = PlayerState.load(self.ws.root)
        if saved is not None and saved.dungeon != self.dungeon.id:
            raise WrongDungeonError(
                f"{self.ws.root} holds a save for the {saved.dungeon!r} dungeon, "
                f"not {self.dungeon.id!r}. Pick a different --workspace."
            )
        self.state = saved or PlayerState.new(self.dungeon.id, self.dungeon.start)

    @property
    def title(self) -> str:
        """The player's rank in this dungeon, from their XP."""
        return self.dungeon.rank_for(self.state.xp)

    # --- plumbing --------------------------------------------------------------

    @property
    def room(self) -> Room:
        return self.dungeon.rooms.get(self.state.room) or self.dungeon.rooms[self.dungeon.start]

    def save(self) -> None:
        if self.ws.root.exists():
            self.state.save(self.ws.root)

    def ask(self, prompt: str) -> str:
        try:
            return self._input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def confirm(self, question: str, default: bool = False) -> bool:
        suffix = " [Y/n] " if default else " [y/N] "
        answer = self.ask(question + suffix).lower()
        if not answer:
            return default
        return answer in {"y", "yes"}

    def quest_done(self, room: Room | None = None) -> bool:
        return (room or self.room).id in self.state.completed

    def exit_locked(self, target: Room) -> bool:
        """Forward exits (to a higher-order room) open once this room's quest is done."""
        here = self.room
        return target.order > here.order and here.quest is not None and not self.quest_done(here)

    # --- lifecycle ----------------------------------------------------------------

    def start(self) -> bool:
        """Greet the player and make sure the workspace exists. False means abort."""
        self.out.say(BANNER.format(version=__version__))
        git = self.check_git()
        if not self.ws.root.exists() or not (self.ws.root / ".azurath").exists():
            if self.dungeon.intro:
                self.out.md(self.dungeon.intro)
            self.out.info(f"Your project will be created at: {self.ws.root}")
            self.out.info("(change it with --workspace PATH or the AZURATH_WORKSPACE env var)")
            if not self.confirm("Create it now?", default=True):
                self.out.warn("No workspace, no quests. Farewell!")
                return False
            suggested = (git.name or "").split(" ")[0]
            prompt = f"What should we call you?{f' [{suggested}]' if suggested else ''} "
            name = self.ask(prompt) or suggested or "Adventurer"
            self.state.name = name[:40]
            for note in self.ws.initialize(readme=self.dungeon.readme, commit=False):
                self.out.info(f"  · {note}")
            self.save()
            if self.ws.is_git_repo():
                self.commit_work(f"Begin {self.dungeon.workspace} in {self.dungeon.name}")
            if in_vscode_terminal():
                self.out.info(
                    "You're in a VS Code terminal: `edit <file>` opens files in the editor."
                )
        else:
            name = escape(self.state.name)
            self.out.ok(f"Welcome back to {self.dungeon.name}, {name} the {self.title}.")
        self.cmd_look("")
        return True

    def run(self) -> None:
        if not self.start():
            return
        self._setup_readline()
        while True:
            try:
                line = self._input(f"\n[bold magenta]{self.room.name}[/bold magenta] [dim]›[/dim] ")
            except (EOFError, KeyboardInterrupt):
                self.console.print()
                self.cmd_quit("")
                break
            if self.handle(line) is QUIT:
                break

    def handle(self, line: str) -> object:
        line = line.strip()
        if not line:
            return None
        if line.startswith("!"):
            result = self.cmd_exec(line[1:].strip())
        else:
            verb, _, arg = line.partition(" ")
            verb = verb.lower()
            arg = arg.strip()
            if verb in DIRECTIONS or verb in DIRECTIONS.values():
                result = self.cmd_go(verb)
            elif cmd := _LOOKUP.get(verb):
                result = cmd.fn(self, arg)
            else:
                guess = difflib.get_close_matches(verb, list(_LOOKUP), n=1)
                tip = f" Did you mean `{guess[0]}`?" if guess else ""
                self.out.warn(f"I don't know how to '{verb}'.{tip} Type `help` for commands.")
                return None
        self.save()
        return result

    def _setup_readline(self) -> None:
        try:
            import readline
        except ImportError:  # Windows without pyreadline3
            return

        words = sorted(set(_LOOKUP) | set(DIRECTIONS.values()))
        file_verbs = {"edit", "vim", "code", "cat", "ls", "nano"}

        def complete(text: str, index: int) -> str | None:
            buffer = readline.get_line_buffer()
            parts = buffer.split()
            if len(parts) <= 1 and not buffer.endswith(" "):
                options = [w for w in words if w.startswith(text)]
            elif parts and parts[0] in file_verbs:
                options = [f for f in self.ws.files() if f.startswith(text)]
            else:
                options = []
            return options[index] if index < len(options) else None

        readline.set_completer(complete)
        readline.set_completer_delims(" ")
        readline.parse_and_bind("tab: complete")

    # --- git ------------------------------------------------------------------------

    def check_git(self) -> gitcheck.GitHealth:
        """Startup check: git installed, working, and user.name/user.email set globally."""
        health = gitcheck.check_git()
        if not health.installed:
            self.out.warn(
                "git isn't installed, so the game can't save your work as commits. "
                "You can still play."
            )
            self.out.md(gitcheck.install_help() + ", then restart the game.")
        elif health.problem:
            self.out.error("git is installed but isn't working:")
            self.console.print(health.problem, markup=False, highlight=False)
            self.out.md(
                "This is usually a broken global config file. "
                "Open it with `!git config --global --edit` and fix the line it mentions."
            )
        elif not health.has_identity:
            if self.setup_git_identity(health) is not None:
                health = gitcheck.check_git()
        else:
            self.out.say(
                f"[dim]git ✔  commits will be signed {escape(health.name or '')} "
                f"<{escape(health.email or '')}>[/dim]"
            )
        return health

    def setup_git_identity(self, health: gitcheck.GitHealth | None = None) -> str | None:
        """Ask for a name and email and save them in git's global config.

        Returns the name that was saved, or None if the player declined or it failed.
        """
        health = health or gitcheck.check_git()
        missing = [
            key
            for key, value in (("user.name", health.name), ("user.email", health.email))
            if not value
        ]
        self.out.md(
            "**git needs to know who you are.** Every commit (a save point of your project) "
            "is signed with a name and an email, and git refuses to commit without them. "
            f"Missing: {', '.join(f'`{k}`' for k in missing) or 'nothing'}.\n\n"
            "They're saved in your *global* git settings, so every project on this computer "
            "uses them. **They become part of every commit**, so anyone you share the "
            "project with can see them. A made-up email like `sparky@example.com` works "
            "fine, and on GitHub you can use your private *noreply* address. "
            "(If you're under 18, ask a parent, guardian or teacher which to use.)"
        )
        if not self.confirm("Set them now?", default=True):
            self._identity_commands_hint()
            return None
        default_name = health.name or (self.state.name if self.state.name != "Adventurer" else "")
        name = self._ask_valid(
            f"Your name for commits{f' [{default_name}]' if default_name else ''}: ",
            gitcheck.valid_name,
            "That doesn't look like a name. Try again (letters and spaces are fine).",
            default=default_name,
        )
        if name is None:
            self._identity_commands_hint()
            return None
        email = self._ask_valid(
            f"Email for commits{f' [{health.email}]' if health.email else ''}: ",
            gitcheck.valid_email,
            "That doesn't look like an email address (like name@example.com). Try again.",
            default=health.email or "",
        )
        if email is None:
            self._identity_commands_hint()
            return None
        result = gitcheck.set_global_identity(name, email)
        if not result.ok:
            self.out.error("Couldn't save your git identity:")
            self.console.print(result.tail(), markup=False, highlight=False)
            self._identity_commands_hint()
            return None
        self.out.ok(f"git will sign your commits as {name} <{email}>")
        return name

    def _ask_valid(self, prompt: str, valid, error: str, default: str = "") -> str | None:
        for _ in range(3):
            answer = self.ask(prompt) or default
            if not answer:
                return None
            if valid(answer):
                return answer.strip()
            self.out.warn(error)
        return None

    def _identity_commands_hint(self) -> None:
        self.out.md(
            "No problem. The game can't commit your work until git knows who you are. "
            "You can set it any time:\n\n"
            '```\n!git config --global user.name "Your Name"\n'
            "!git config --global user.email you@example.com\n```"
        )

    def commit_work(self, message: str) -> bool:
        """``git add -A && git commit``, explaining (and where safe, fixing) any failure."""
        for attempt in range(2):
            result = self.ws.commit(message)
            if result is None:
                self.out.info("git: nothing new to commit.")
                return True
            if result.ok:
                self.out.ok(f'git commit -m "{message}"')
                return True
            if attempt == 0 and self._fix_commit_failure(result):
                continue  # fixed: try once more
            return False
        return False

    def _fix_commit_failure(self, result) -> bool:
        """Explain a failed commit. Returns True if it was fixed and is worth retrying."""
        kind = gitcheck.classify_commit_failure(result)
        self.out.warn(f"Couldn't commit your work: {kind.value}.")
        if kind is gitcheck.CommitFailure.OTHER or kind is gitcheck.CommitFailure.IDENTITY:
            self.console.print(result.tail(8), markup=False, highlight=False, style="dim")
        if kind is gitcheck.CommitFailure.IDENTITY:
            return self.setup_git_identity() is not None
        if kind is gitcheck.CommitFailure.NO_GIT:
            self.out.md(
                gitcheck.install_help() + ". Your files are safe; they just aren't committed."
            )
            return False
        if kind is gitcheck.CommitFailure.NOT_A_REPO:
            if not self.confirm("Make your project folder a git repository now?", default=True):
                return False
            init = self.ws.git("init", "-b", "main")
            if not init.ok:
                init = self.ws.git("init")
            if not init.ok:
                self.out.error(init.tail())
            return init.ok
        if kind is gitcheck.CommitFailure.DUBIOUS_OWNERSHIP:
            self.out.md(
                "git protects you from repositories owned by another user account. If this "
                f"is your own project, you can tell git to trust it:\n\n"
                f"```\n!git config --global --add safe.directory {self.ws.root}\n```"
            )
            if not self.confirm("Trust this folder now?", default=False):
                return False
            return gitcheck.trust_directory(self.ws.root).ok
        if kind is gitcheck.CommitFailure.LOCKED:
            self.out.md(
                "A git command is still running, or one crashed and left `.git/index.lock` "
                "behind. Close any other git tools (VS Code's source control too), then try "
                "`commit` again. If nothing else is running, delete the lock file:\n\n"
                "```\n!rm .git/index.lock\n```"
            )
            return False
        self.out.md("Try `!git status` to see what git thinks is going on, then `commit`.")
        return False

    # --- looking around -------------------------------------------------------------

    @command("look", "l", help="Describe the room you're in.")
    def cmd_look(self, arg: str) -> None:
        room = self.room
        if arg:
            return self.cmd_examine(arg)
        self.out.panel(room.description, f"{room.name}  ·  {room.zone}", style="magenta")
        if room.npc:
            npc = room.npc
            self.out.say(f"[bold]{npc.name}[/bold] is here.  [dim](talk {npc.handle})[/dim]")
        if room.pages:
            read = self.state.pages.get(room.id, 0)
            total = len(room.pages)
            progress = f"[dim](read · {read}/{total} read)[/dim]"
            self.out.say(f"A tome lies open: [bold]{total} pages[/bold]  {progress}")
        if room.quest:
            status = "[green]✔ complete[/green]" if self.quest_done() else "[yellow]open[/yellow]"
            self.out.say(f"Quest: [bold]{room.quest.title}[/bold] · {status}  [dim](quest)[/dim]")
        exits = []
        for direction, target_id in room.exits.items():
            target = self.dungeon.rooms[target_id]
            lock = " 🔒" if self.exit_locked(target) else ""
            exits.append(f"[bold]{direction}[/bold] → {target.name}{lock}")
        self.out.say("Exits: " + ("  ·  ".join(exits) if exits else "none"))

    @command(
        "go",
        "walk",
        "move",
        usage="go <direction>",
        help="Move through an exit (or just type `north`, `n`, ...).",
    )
    def cmd_go(self, arg: str) -> None:
        direction = DIRECTIONS.get(arg.lower(), arg.lower())
        target_id = self.room.exits.get(direction)
        if not target_id:
            self.out.warn(f"You can't go '{arg}' from here.")
            return
        target = self.dungeon.rooms[target_id]
        if self.exit_locked(target):
            self.out.warn(
                f"A shimmering ward blocks the way to {target.name}. "
                f"Complete '{self.room.quest.title}' first (`quest`, then `check`)."
            )
            return
        self.state.visit(target.id)
        self.cmd_look("")

    @command(
        "goto",
        "teleport",
        usage="goto <room>",
        help="Travel instantly to a room you've already visited.",
    )
    def cmd_goto(self, arg: str) -> None:
        if not arg:
            self.cmd_map("")
            return
        room = self.dungeon.find_room(arg)
        if not room:
            self.out.warn(f"No room matches '{arg}'. See `map`.")
        elif room.id not in self.state.visited:
            self.out.warn(f"You haven't found the way to {room.name} yet.")
        else:
            self.state.visit(room.id)
            self.cmd_look("")

    @command("map", "rooms", help="Show the realm and your progress through it.")
    def cmd_map(self, arg: str) -> None:
        table = Table(title=escape(self.dungeon.name), show_lines=False, header_style="bold")
        table.add_column("#", justify="right")
        table.add_column("Room")
        table.add_column("Topic")
        table.add_column("Status")
        for room in self.dungeon.ordered():
            here = room.id == self.state.room
            if self.quest_done(room):
                status = "[green]✔ complete[/green]"
            elif room.id in self.state.visited:
                status = "[yellow]in progress[/yellow]"
            else:
                status = "[dim]🔒 undiscovered[/dim]"
            name = f"[bold magenta]▶ {room.name}[/bold magenta]" if here else room.name
            if room.optional:
                name += " [dim](side quest)[/dim]"
            table.add_row(str(room.order), name, room.zone, status)
        self.console.print(table)
        self.out.say("[dim]`goto <room>` jumps to any room you've visited.[/dim]")

    # --- learning ------------------------------------------------------------------------

    @command(
        "read",
        "study",
        usage="read [n | back | all]",
        help="Read the next page of this room's tome (or page n).",
    )
    def cmd_read(self, arg: str) -> None:
        room = self.room
        if not room.pages:
            self.out.warn("There's nothing to read here.")
            return
        last = self.state.pages.get(room.id, 0)  # 1-based index of the last page read
        arg = arg.lower()
        if arg == "all":
            for i, _ in enumerate(room.pages, start=1):
                self._show_page(room, i)
            return
        if arg.isdigit():
            index = int(arg)
        elif arg in {"back", "prev", "previous"}:
            index = max(1, last - 1)
        elif arg in {"again", "this"}:
            index = max(1, last)
        else:
            index = last + 1 if last < len(room.pages) else 1
        if not 1 <= index <= len(room.pages):
            self.out.warn(f"The tome has pages 1-{len(room.pages)}.")
            return
        self._show_page(room, index)

    def _show_page(self, room: Room, index: int) -> None:
        page = room.pages[index - 1]
        self.out.panel(
            page.body, f"📖 {page.title}  ·  page {index}/{len(room.pages)}", style="cyan"
        )
        self.state.pages[room.id] = index
        if index < len(room.pages):
            self.out.say("[dim]`read` for the next page · `read back` · `pages` for contents[/dim]")
        elif room.quest:
            self.out.say("[dim]That's the last page. Type `quest` to see your task.[/dim]")

    @command("pages", "toc", help="List the pages in this room's tome.")
    def cmd_pages(self, arg: str) -> None:
        last = self.state.pages.get(self.room.id, 0)
        for i, page in enumerate(self.room.pages, start=1):
            mark = "[green]✔[/green]" if i <= last else " "
            self.out.say(f" {mark} {i}. {page.title}")

    @command("next", help="Read the next page.")
    def cmd_next(self, arg: str) -> None:
        self.cmd_read("")

    @command("talk", "greet", usage="talk [name]", help="Talk to the mentor in this room.")
    def cmd_talk(self, arg: str) -> None:
        npc = self.room.npc
        if not npc:
            self.out.warn("You talk to the walls. The walls are unimpressed.")
            return
        if arg and not npc.matches(arg):
            self.out.warn(f"There's no '{arg}' here. {npc.name} raises an eyebrow.")
            return
        self.out.panel(npc.greeting, f"💬 {npc.name}", style="green")
        if npc.topics:
            topics = ", ".join(f"`{t}`" for t in npc.topics)
            self.out.md(f"*Ask about:* {topics}  (e.g. `ask {next(iter(npc.topics))}`)")

    @command("ask", usage="ask [name] [about] <topic>", help="Ask the mentor about a topic.")
    def cmd_ask(self, arg: str) -> None:
        npc = self.room.npc
        if not npc:
            self.out.warn("Nobody here to ask.")
            return
        words = [w for w in arg.lower().split() if w != "about"]
        if words and npc.matches(words[0]) and len(words) > 1:
            words = words[1:]
        topic = " ".join(words)
        if not topic:
            self.cmd_talk("")
            return
        key = (
            topic
            if topic in npc.topics
            else next((t for t in npc.topics if topic in t.lower() or t.lower() in topic), None)
        )
        if key is None:
            self.out.say(f'{npc.name} shrugs. "I can tell you about: {", ".join(npc.topics)}."')
            return
        self.out.panel(npc.topics[key], f"💬 {npc.name} on {key}", style="green")

    # --- quests ----------------------------------------------------------------------------

    @command("quest", "task", "q", help="Show this room's quest.")
    def cmd_quest(self, arg: str) -> None:
        quest = self.room.quest
        if not quest:
            self.out.warn("There's no quest here.")
            return
        done = self.quest_done()
        self.out.panel(quest.brief, f"⚔ {quest.title}" + ("  ✔" if done else ""), style="yellow")
        tips = ["`check` to test your work", "`hint` if stuck"]
        if quest.scaffold:
            tips.insert(0, "`scaffold` for starter files")
        self.out.say("[dim]" + " · ".join(tips) + f" · workspace: {self.ws.root}[/dim]")

    @command("check", "verify", help="Check your work against the quest's requirements.")
    def cmd_check(self, arg: str) -> Report | None:
        room = self.room
        quest = room.quest
        if not quest:
            self.out.warn("Nothing to check here.")
            return None
        with self.console.status("The runes examine your code…"):
            report = run_check(self.dungeon, quest.check, self.ws)
        self.out.report(report, f"Check: {quest.title}")
        if report.passed:
            self._complete(room, report)
        return report

    def _complete(self, room: Room, report: Report) -> None:
        quest = room.quest
        assert quest is not None
        if not self.state.complete(room.id):
            self.out.info("(You've already completed this quest. Your code still passes. Nice.)")
            return
        reward = quest.reward
        self.state.xp += reward.xp
        self.out.ok(f"+{reward.xp} XP · rank: {self.title} ({self.state.xp} XP)")
        if reward.item and reward.item.name not in self.state.inventory:
            self.state.inventory.append(reward.item.name)
            self.out.ok(f"You receive: {reward.item.name}  (examine {reward.item.handle})")
        if self.settings.auto_commit:
            self.commit_work(quest.commit_message or f"Complete quest: {quest.title}")
        opened = [
            self.dungeon.rooms[t].name
            for t in room.exits.values()
            if self.dungeon.rooms[t].order > room.order
        ]
        if opened:
            self.out.say(
                f"[bold green]The ward fades. The way to {', '.join(opened)} is open.[/bold green]"
            )
        if quest.epilogue:
            self.out.panel(quest.epilogue, "🏆 Epilogue", style="bold yellow")

    @command("hint", help="Reveal the next hint for this quest.")
    def cmd_hint(self, arg: str) -> None:
        quest = self.room.quest
        if not quest or not quest.hints:
            self.out.warn("No hints here.")
            return
        shown = self.state.hints.get(self.room.id, 0)
        if shown < len(quest.hints):
            shown += 1
            self.state.hints[self.room.id] = shown
        for i, hint in enumerate(quest.hints[:shown], start=1):
            self.out.panel(hint, f"💡 Hint {i}/{len(quest.hints)}", style="yellow")
        if shown == len(quest.hints):
            self.out.say("[dim]Out of hints. `solution` shows the reference answer.[/dim]")

    @command(
        "scaffold",
        "starter",
        help="Write starter files for this quest (never overwrites your work).",
    )
    def cmd_scaffold(self, arg: str) -> None:
        quest = self.room.quest
        if not quest or not quest.scaffold:
            self.out.warn("This quest has no starter files. You start from a blank page.")
            return
        for target, source in quest.scaffold.items():
            if self.ws.exists(target):
                self.out.info(f"  · {target} already exists, leaving it alone")
                continue
            content = self.dungeon.room_text(self.room.id, "scaffold", source)
            self.ws.write(target, content)
            self.out.ok(f"wrote {target}")
        first = next(iter(quest.scaffold))
        self.out.say(f"[dim]Next: `edit {first}` (or open it in your editor), then `check`.[/dim]")

    @command(
        "solution",
        "spoiler",
        usage="solution [apply]",
        help="Show the reference solution (apply writes it).",
    )
    def cmd_solution(self, arg: str) -> None:
        quest = self.room.quest
        if not quest:
            self.out.warn("No quest here.")
            return
        sol = quest.solution
        apply = arg.lower() == "apply"
        if not self.quest_done() and not self.confirm(
            "Peek at the reference solution? Struggling a little first is how it sticks."
        ):
            return
        for target, source in sol.files.items():
            text = self.dungeon.room_text(self.room.id, "solution", source)
            self.out.code(text, target)
        if sol.commands:
            cmds = "\n".join(sol.commands)
            self.out.panel(
                f"Run these (prefix with `!` to run them from the MUD):\n\n```\n{cmds}\n```",
                "Commands",
            )
        if sol.notes:
            self.out.md(sol.notes)
        if apply and sol.files:
            if not self.confirm(
                "Write these files into your workspace? Existing files get a .bak copy."
            ):
                return
            for target, source in sol.files.items():
                text = self.dungeon.room_text(self.room.id, "solution", source)
                existing = self.ws.path(target)
                if existing.exists():
                    shutil.copy2(existing, existing.with_name(existing.name + ".bak"))
                self.ws.write(target, text)
                self.out.ok(f"wrote {target}")
            if sol.commands:
                self.out.warn("Don't forget to run the commands above.")
        elif sol.files:
            self.out.say("[dim]`solution apply` writes these files for you.[/dim]")

    # --- editing & files -----------------------------------------------------------------

    def _resolve(self, arg: str) -> Path | None:
        rel = arg.strip().strip('"').strip("'")
        if not rel:
            quest = self.room.quest
            if quest and quest.scaffold:
                rel = next(iter(quest.scaffold))
            else:
                self.out.warn("Which file? e.g. `edit hello.py`")
                return None
        path = (self.ws.root / rel).resolve()
        if self.ws.root not in path.parents and path != self.ws.root:
            self.out.warn("That's outside your workspace.")
            return None
        return path

    def _edit(self, arg: str, force: str | None = None) -> None:
        path = self._resolve(arg)
        if path is None:
            return
        if path.is_dir():
            self.out.warn(f"{path.name} is a folder.")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        rel = path.relative_to(self.ws.root).as_posix()
        quest = self.room.quest
        if not path.exists() and quest and rel in quest.scaffold:
            starter = self.dungeon.room_file(self.room.id, "scaffold", quest.scaffold[rel])
            self.ws.write(rel, starter.read_text(encoding="utf-8"))
            self.out.info(f"(created {rel} from the quest's starter template)")
        choice = choose_editor(path, self.settings.editor, force=force)
        if choice is None:
            self.out.error("No editor found. Set AZURATH_EDITOR (e.g. `vim`, `nano`, `code -r`).")
            return
        if choice.blocking:
            if "vim" in choice.label or choice.label == "vi":
                self.out.md(VIM_CHEATSHEET)
                self.ask("Press Enter to open vim… ")
            self.ws.interactive(choice.argv)
            self.out.ok(f"back from {choice.label}. `check` when ready.")
        else:
            import subprocess

            subprocess.Popen(choice.argv, cwd=self.ws.root, env=self.ws.env())
            self.out.ok(f"opened {rel} in {choice.label}. Save it there, then `check` here.")

    @command(
        "edit",
        "e",
        usage="edit [file]",
        help="Open a workspace file in your editor (VS Code, $EDITOR, vim…).",
    )
    def cmd_edit(self, arg: str) -> None:
        self._edit(arg)

    @command(
        "vim", "vi", usage="vim [file]", help="Open a file in vim (with a survival cheat sheet)."
    )
    def cmd_vim(self, arg: str) -> None:
        self._edit(arg, force="vim" if shutil.which("vim") else "vi")

    @command("nano", usage="nano [file]", help="Open a file in nano.")
    def cmd_nano(self, arg: str) -> None:
        self._edit(arg, force="nano")

    @command("code", usage="code [file]", help="Open the workspace (or a file) in VS Code.")
    def cmd_code(self, arg: str) -> None:
        if arg:
            self._edit(arg, force="code")
            return
        cli = shutil.which("code") or shutil.which("code-insiders")
        if not cli:
            self.out.warn(
                f"VS Code's `code` command isn't on PATH. Open this folder manually: {self.ws.root}"
            )
            return
        import subprocess

        subprocess.Popen([cli, str(self.ws.root)], env=self.ws.env())
        self.out.ok("opened the workspace in VS Code")

    @command("ls", "dir", usage="ls [folder]", help="List files in your workspace.")
    def cmd_ls(self, arg: str) -> None:
        files = self.ws.files(arg.strip())
        if not files:
            self.out.warn("Nothing there yet.")
            return
        tree = Tree(f"[bold]{self.ws.root.name}/{arg.strip()}[/bold]")
        nodes: dict[str, Tree] = {"": tree}
        for f in files:
            parts = f.split("/")
            for depth in range(1, len(parts)):
                key = "/".join(parts[:depth])
                if key not in nodes:
                    nodes[key] = nodes["/".join(parts[: depth - 1])].add(
                        f"[bold blue]{parts[depth - 1]}/[/bold blue]"
                    )
            nodes["/".join(parts[:-1])].add(parts[-1])
        self.console.print(tree)

    @command(
        "cat",
        "show",
        "type",
        usage="cat <file>",
        help="Show a workspace file with syntax highlighting.",
    )
    def cmd_cat(self, arg: str) -> None:
        path = self._resolve(arg)
        if path is None:
            return
        if not path.is_file():
            self.out.warn(f"No such file: {arg}")
            return
        rel = path.relative_to(self.ws.root).as_posix()
        self.out.code(self.ws.read(rel) or "", rel)

    @command(
        "sh",
        "run",
        "exec",
        usage="!<command>  or  sh <command>",
        help="Run a shell command in your workspace (venv activated).",
    )
    def cmd_exec(self, arg: str) -> None:
        if not arg:
            self.out.warn("Run what? e.g. `!uv --version` or `!pytest -q`")
            return
        if self._unsafe_uv_init(arg):
            return
        argv = self.ws.shell_argv(arg, self.settings.shell)
        self.out.say(f"[dim]$ {arg}[/dim]")
        code = self.ws.interactive(argv)
        if code == 127:
            self.out.error("command not found")
        elif code:
            self.out.warn(f"exit code {code}")

    def _unsafe_uv_init(self, command: str) -> bool:
        """Refuse `uv init` that would join this project to an enclosing one."""
        words = self._args(command)
        if words[:2] != ["uv", "init"] or "--no-workspace" in words:
            return False
        outer = self.ws.enclosing_project()
        if outer is None:
            return False
        self.out.warn(
            f"Careful! Your project is inside another project ({outer}). Plain `uv init` "
            "would change that project's pyproject.toml and put your packages in ITS "
            "virtual environment. Add `--no-workspace` to keep your project separate:"
        )
        self.out.say(f"[bold]  !{escape(command)} --no-workspace[/bold]")
        return True

    def _which_python(self) -> str:
        if self.ws.venv_python():
            return "using your project's .venv"
        return "using the game's Python; your project has no .venv yet"

    def _args(self, arg: str) -> list[str]:
        try:
            return shlex.split(arg, posix=os.name != "nt")
        except ValueError:
            return arg.split()

    @command(
        "python",
        "py",
        usage="python <file.py> [args]",
        help="Run a Python file with your project's Python (its .venv if it has one).",
    )
    def cmd_python(self, arg: str) -> None:
        args = self._args(arg)
        if not args:
            self.out.warn("Run which file? e.g. `python hello.py`")
            return
        self.out.say(f"[dim]$ python {escape(arg)}   ({self._which_python()})[/dim]")
        code = self.ws.interactive([self.ws.python(), *args])
        if code:
            self.out.warn(f"your program stopped with exit code {code} (read the error above)")

    @command(
        "pytest",
        "test",
        "tests",
        usage="pytest [args]",
        help="Run your project's tests and say whether they're green (pass) or red (fail).",
    )
    def cmd_pytest(self, arg: str) -> None:
        args = self._args(arg) or ["-q"]
        self.out.say(f"[dim]$ pytest {escape(' '.join(args))}   ({self._which_python()})[/dim]")
        code = self.ws.interactive(
            [self.ws.python(), "-m", "pytest", "-p", "no:cacheprovider", *args]
        )
        if code == 0:
            self.out.ok("GREEN: every test passed.")
        elif code == 1:
            self.out.warn("RED: some tests failed. Read the first failure above and fix one thing.")
        elif code == 5:
            self.out.warn("No tests found. Test files are named test_*.py, tests are def test_*().")
        else:
            self.out.error(
                f"pytest couldn't run your tests (exit code {code}). See the error above."
            )

    @command(
        "shell",
        "terminal",
        help="Open an interactive shell in your workspace. `exit` returns to the MUD.",
    )
    def cmd_shell(self, arg: str) -> None:
        argv = self.ws.shell_argv(None, self.settings.shell)
        self.out.info(
            f"Opening {Path(argv[0]).name} in {self.ws.root}. Type `exit` to return to the game."
        )
        self.ws.interactive(argv)
        self.out.ok(f"Welcome back to {self.dungeon.name}.")

    @command("commit", usage="commit [message]", help="git add -A && git commit in your workspace.")
    def cmd_commit(self, arg: str) -> None:
        self.commit_work(arg or f"Work in progress in {self.room.name}")

    @command("log", "history", help="Show your repo's git history (one commit per quest).")
    def cmd_log(self, arg: str) -> None:
        result = self.ws.git("log", "--oneline", "--decorate", "-n", "30")
        self.console.print(result.output or "no commits yet", highlight=False)

    @command("workspace", "where", "pwd", help="Show where your project lives and how to open it.")
    def cmd_workspace(self, arg: str) -> None:
        root = self.ws.root
        venv = self.ws.venv_python()
        self.out.md(
            f"**Workspace:** `{root}`\n\n"
            f"* Python used by checks: `{self.ws.python()}`"
            + (" (your .venv)" if venv else " (the game's, until you make a .venv)")
            + "\n"
            f"* Open in VS Code: `code` (or File → Open Folder… → `{root}`)\n"
            f'* In another terminal: `cd "{root}"`, and from there `azurath check` works too.\n'
        )

    # --- inventory & status -------------------------------------------------------------

    @command("inventory", "i", "inv", help="List the items (cheat sheets) you've earned.")
    def cmd_inventory(self, arg: str) -> None:
        if not self.state.inventory:
            self.out.info("Your pack is empty. Complete quests to earn items.")
            return
        items = self.dungeon.items()
        for name in self.state.inventory:
            alias = items[name].handle if name in items else name
            self.out.say(f" • [bold]{name}[/bold]  [dim](examine {alias})[/dim]")

    def _find_item(self, text: str) -> Item | None:
        items = self.dungeon.items()
        for name in self.state.inventory:
            item = items.get(name)
            if item and item.matches(text):
                return item
        return None

    @command(
        "examine",
        "x",
        "inspect",
        usage="examine <item>",
        help="Study an item: each one is a cheat sheet.",
    )
    def cmd_examine(self, arg: str) -> None:
        if not arg:
            self.out.warn("Examine what? See `inventory`.")
            return
        item = self._find_item(arg)
        if item:
            self.out.panel(item.text, f"🎒 {item.name}", style="blue")
            return
        npc = self.room.npc
        if npc and npc.matches(arg):
            self.out.md(f"*{npc.name}* looks back at you patiently. Try `talk`.")
            return
        self.out.warn(f"You don't have '{arg}'. See `inventory`.")

    @command("status", "score", "whoami", help="Your title, XP and progress.")
    def cmd_status(self, arg: str) -> None:
        total = sum(1 for r in self.dungeon.ordered() if r.quest and not r.optional)
        done = sum(
            1 for r in self.dungeon.ordered() if r.quest and not r.optional and self.quest_done(r)
        )
        side = [r for r in self.dungeon.ordered() if r.optional and self.quest_done(r)]
        self.out.md(
            f"**{self.state.name}** the *{self.title}*  \n"
            f"XP: **{self.state.xp}** · Main quests: **{done}/{total}**"
            + (f" · Side quests: **{len(side)}**" if side else "")
            + f" · Items: **{len(self.state.inventory)}**"
        )

    # --- meta ---------------------------------------------------------------------------

    @command("help", "?", "commands", usage="help [command]", help="List commands, or explain one.")
    def cmd_help(self, arg: str) -> None:
        if arg:
            cmd = _LOOKUP.get(arg.lower().lstrip("!"))
            if not cmd:
                self.out.warn(f"No command '{arg}'.")
                return
            aliases = f"  (aliases: {', '.join(cmd.aliases)})" if cmd.aliases else ""
            self.out.md(f"`{cmd.usage}`{aliases}\n\n{cmd.help}")
            return
        groups = {
            "Explore": ["look", "go", "goto", "map", "talk", "ask"],
            "Learn": ["read", "pages", "quest", "hint", "check", "scaffold", "solution"],
            "Code": [
                "edit",
                "vim",
                "code",
                "ls",
                "cat",
                "python",
                "pytest",
                "sh",
                "shell",
                "commit",
                "log",
                "workspace",
            ],
            "You": ["inventory", "examine", "status", "save", "quit", "help"],
        }
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold cyan", no_wrap=True)
        table.add_column()
        for group, names in groups.items():
            table.add_row(f"[bold magenta]{group}[/bold magenta]", "")
            for name in names:
                cmd = COMMANDS[name]
                table.add_row("  " + escape(cmd.usage), escape(cmd.help))
        self.console.print(table)
        self.out.say(
            "[dim]Directions: north/n, south/s, east/e, west/w, up/u, down/d. "
            "`!cmd` runs a shell command.[/dim]"
        )

    @command("save", help="Save your progress (also happens automatically).")
    def cmd_save(self, arg: str) -> None:
        self.save()
        self.out.ok(f"saved to {PlayerState.path_for(self.ws.root)}")

    @command("quit", "exit", "q!", "bye", help="Save and leave the game.")
    def cmd_quit(self, arg: str) -> object:
        self.save()
        name = escape(self.state.name)
        self.out.say(
            f"[bold]Farewell, {name}.[/bold] Your progress is saved. Run `azurath` again to return."
        )
        return QUIT
