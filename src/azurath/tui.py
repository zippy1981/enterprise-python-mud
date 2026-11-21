"""A split-screen terminal UI for Azurath, built with Textual.

``azurath tui`` (or ``uv run --extra tui azurath tui``) shows the same game as
``azurath play``, laid out in panes:

* the story on the left: room descriptions, mentors, lesson pages and command
  output, with the command box underneath;
* a sidebar on the right with the quest and its live checklist, buttons for the
  exits and the common commands, the map with your progress, and your items.

Every command still works by typing it. The buttons just type it for you. To play
in a browser instead, run it through Textual's web server::

    uvx --from textual-dev textual serve "azurath tui"

It drives the game through :class:`azurath.session.Session`, the headless API
the other front ends use too.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, RichLog, Static, Tree

from azurath.content import Dungeon
from azurath.editor import choose_editor
from azurath.session import Result, Session, Snapshot
from azurath.settings import AzurathSettings

STATUS_ICONS = {"complete": "✔", "visited": "◐", "undiscovered": "🔒"}
COMMON = [
    ("look", "Look"),
    ("read", "Read"),
    ("talk", "Talk"),
    ("hint", "Hint"),
    ("check", "Check"),
]


def quest_panel(snap: Snapshot) -> Text:
    """The quest title and the last check's criteria, as a checklist."""
    if not snap.quest:
        return Text("No quest here.", style="dim")
    status = ("✔ complete", "green") if snap.quest_done else ("open", "yellow")
    text = Text.assemble((snap.quest, "bold"), "  ", status)
    if snap.last_check is None:
        text.append("\n\nType `check` (or press Check) to see what's left.", style="dim")
        return text
    for item in snap.last_check:
        if item.ok:
            mark, style = "✔", "green"
        elif item.optional:
            mark, style = "○", "yellow"
        else:
            mark, style = "✘", "red"
        text.append(f"\n{mark} ", style=f"bold {style}")
        text.append(item.description.replace("`", ""))
    return text


def status_line(snap: Snapshot) -> Text:
    done = sum(r.status == "complete" for r in snap.map)
    return Text.assemble(
        (snap.player, "bold"),
        " the ",
        (snap.title, "italic"),
        f" · {snap.xp} XP · {done}/{len(snap.map)} rooms · {len(snap.inventory)} items",
    )


class AzurathApp(App[None]):
    """The game, in panes."""

    TITLE = "Azurath"
    CSS = """
    #story { width: 2fr; }
    #log { height: 1fr; border: round $primary; padding: 0 1; }
    #command { dock: bottom; }
    #sidebar { width: 1fr; min-width: 36; }
    #sidebar > * { margin-bottom: 1; }
    .card { border: round $secondary; padding: 0 1; height: auto; }
    #exits Button, #actions Button { min-width: 8; margin-right: 1; }
    #exits, #actions { height: auto; layout: grid; grid-size: 3; grid-gutter: 0 1; }
    #map { height: 16; border: round $secondary; }
    """
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f5", "command('check')", "Check"),
        Binding("f2", "command('hint')", "Hint"),
        Binding("f3", "command('read')", "Read"),
    ]

    def __init__(self, settings: AzurathSettings, dungeon: Dungeon) -> None:
        super().__init__()
        self.settings = settings
        self.session = Session(settings, dungeon=dungeon, width=96, open_file=self.open_file)
        self.busy = False

    # --- layout ------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="story"):
                yield RichLog(id="log", wrap=False, markup=False, highlight=False, min_width=20)
                yield Input(placeholder="Type a command (help, look, read, check…)", id="command")
            with VerticalScroll(id="sidebar"):
                yield Static(id="status", classes="card")
                yield Static(id="quest", classes="card")
                yield Static("Exits", classes="label")
                yield Horizontal(id="exits")
                yield Horizontal(id="actions")
                yield Tree("Map", id="map")
                yield Static(id="inventory", classes="card")
        yield Footer()

    def on_mount(self) -> None:
        actions = self.query_one("#actions", Horizontal)
        for verb, label in COMMON:
            actions.mount(Button(label, id=f"do-{verb}", variant="primary"))
        self.query_one("#command", Input).focus()
        self.call_after_refresh(self._begin)

    def _begin(self) -> None:
        self.fit_output()
        self.run_command("start")

    # --- running commands --------------------------------------------------------------

    @work(thread=True, exclusive=True)
    def run_command(self, line: str) -> None:
        """Run a command off the UI thread (checks can take a while)."""
        self.busy = True
        try:
            result = self.session.start() if line == "start" else self.session.run(line)
            snap = self.session.snapshot()
        finally:
            self.busy = False
        self.call_from_thread(self.show, line, result, snap)

    def show(self, line: str, result: Result, snap: Snapshot) -> None:
        log = self.query_one("#log", RichLog)
        if line != "start":
            log.write(Text(f"› {line}", style="bold magenta"))
        log.write(Text.from_ansi(result.ansi.rstrip("\n")))
        self.refresh_sidebar(snap)
        if result.quit:
            self.exit()

    def fit_output(self) -> None:
        """Draw the game's panels exactly as wide as the story pane."""
        width = self.query_one("#log", RichLog).scrollable_content_region.width
        if width > 20:
            self.session.console.width = width - 1  # leave room for the scrollbar

    def on_resize(self) -> None:
        self.fit_output()  # the next command's output fits the new size

    def action_command(self, line: str) -> None:
        if not self.busy:
            self.fit_output()
            self.run_command(line)

    @on(Input.Submitted, "#command")
    def submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        event.input.value = ""
        if line:
            self.action_command(line)

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        name = event.button.name or ""
        if button_id.startswith("do-"):
            self.action_command(button_id.removeprefix("do-"))
        elif name.startswith("go-"):
            self.action_command(name.removeprefix("go-"))

    @on(Tree.NodeSelected, "#map")
    def map_selected(self, event: Tree.NodeSelected) -> None:
        room_id = event.node.data
        if room_id:
            self.action_command(f"goto {room_id}")

    # --- sidebar -------------------------------------------------------------------------

    def refresh_sidebar(self, snap: Snapshot) -> None:
        self.sub_title = f"{snap.dungeon_name} · {snap.room_name}"
        self.query_one("#status", Static).update(status_line(snap))
        self.query_one("#quest", Static).update(quest_panel(snap))

        exits = self.query_one("#exits", Horizontal)
        exits.remove_children()
        for exit_ in snap.exits:
            label = f"{exit_.direction}{' 🔒' if exit_.locked else ''}"
            # A name, not an id: the old buttons are still being removed while these mount.
            button = Button(label, name=f"go-{exit_.direction}", disabled=exit_.locked)
            button.tooltip = exit_.name
            exits.mount(button)

        tree = self.query_one("#map", Tree)
        tree.clear()
        tree.root.expand()
        zones: dict[str, object] = {}
        for room in snap.map:
            zone = room.zone.split(" (")[0]
            if zone not in zones:
                zones[zone] = tree.root.add(zone, expand=True)
            icon = "▶" if room.here else STATUS_ICONS[room.status]
            label = Text.assemble(f"{icon} ", (room.name, "bold magenta" if room.here else ""))
            zones[zone].add_leaf(label, data=room.id if room.status != "undiscovered" else None)

        items = ", ".join(snap.inventory) or "nothing yet"
        self.query_one("#inventory", Static).update(
            Text.assemble(("Items: ", "bold"), items, "  ", ("(examine <item>)", "dim"))
        )

    # --- opening files -------------------------------------------------------------------

    def open_file(self, path: Path, rel: str) -> bool:
        """Open a file for `edit`: suspend the UI for terminal editors like vim."""
        choice = choose_editor(path, self.settings.editor)
        if choice is None:
            return False
        if choice.blocking:
            # Called from the worker thread: the suspend has to happen on the UI thread.
            self.call_from_thread(self._edit_blocking, choice.argv)
        else:
            subprocess.Popen(choice.argv, cwd=self.session.game.ws.root)
        return True

    def _edit_blocking(self, argv: list[str]) -> None:
        with self.suspend():
            subprocess.call(argv, cwd=self.session.game.ws.root)


def run_tui(settings: AzurathSettings, dungeon: Dungeon) -> None:
    AzurathApp(settings, dungeon).run()
