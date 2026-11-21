"""Game content: dungeons of rooms, written in YAML and validated by pydantic models.

Each dungeon is a self-contained folder (and Python package) under
``azurath/dungeons/<dungeon_id>/``:

    dungeon.yaml          name, audience, start room, ranks, intro text
    rooms/*.yaml          one file per room (lesson, mentor, quest)
    files/<room_id>/      scaffold/ (starter) and solution/ (reference) files
    checks/               the @check functions that grade each quest

Loading through ``importlib.resources`` means it all still works after the
package is installed as a wheel, the way you'd read an embedded resource from an
assembly in .NET.

Dungeons don't connect to each other yet. When they do, an exit will name a room
in another dungeon as ``"<dungeon_id>:<room_id>"``. Everything that follows an
exit goes through ``RoomRef.parse`` and ``Atlas.resolve`` so that change lands in
one place; today a qualified exit is rejected at load time. See docs/dungeons.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable

from pydantic import BaseModel, Field, field_validator, model_validator

from azurath import yamlschema, yamlstrict

DIRECTIONS = {
    "n": "north",
    "s": "south",
    "e": "east",
    "w": "west",
    "u": "up",
    "d": "down",
    "ne": "northeast",
    "nw": "northwest",
    "se": "southeast",
    "sw": "southwest",
}

DEFAULT_DUNGEON = "enterprise"


@dataclass(frozen=True)
class RoomRef:
    """A pointer to a room: ``room_id`` (same dungeon) or ``dungeon_id:room_id``."""

    dungeon: str | None
    room: str

    @classmethod
    def parse(cls, text: str) -> RoomRef:
        dungeon, sep, room = text.partition(":")
        return cls(dungeon, room) if sep else cls(None, text)

    @property
    def is_local(self) -> bool:
        return self.dungeon is None


class Page(BaseModel):
    title: str
    body: str


class Npc(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    greeting: str
    topics: dict[str, str] = Field(default_factory=dict)

    @property
    def handle(self) -> str:
        """The short name players type, e.g. `talk pip`."""
        return self.aliases[0] if self.aliases else self.name

    def matches(self, text: str) -> bool:
        text = text.lower().strip()
        names = [self.name.lower(), *(a.lower() for a in self.aliases)]
        return any(text == n or text in n.split() for n in names)


class Item(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    text: str

    @property
    def handle(self) -> str:
        return self.aliases[0] if self.aliases else self.name

    def matches(self, text: str) -> bool:
        text = text.lower().strip()
        return text in {self.name.lower(), *(a.lower() for a in self.aliases)} or (
            len(text) >= 3 and text in self.name.lower()
        )


class Reward(BaseModel):
    xp: int = 100
    item: Item | None = None


def _as_mapping(value: object) -> object:
    """Allow ``[a.py, b.py]`` as shorthand for ``{a.py: a.py, b.py: b.py}``."""
    if isinstance(value, list):
        return {str(v): str(v) for v in value}
    return value


class Solution(BaseModel):
    files: dict[str, str] = Field(default_factory=dict)
    commands: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("files", mode="before")
    @classmethod
    def _files_mapping(cls, value: object) -> object:
        return _as_mapping(value)


class Quest(BaseModel):
    title: str
    brief: str
    check: str
    hints: list[str] = Field(default_factory=list)
    scaffold: dict[str, str] = Field(default_factory=dict)
    solution: Solution = Field(default_factory=Solution)
    reward: Reward = Field(default_factory=Reward)
    commit_message: str | None = None
    epilogue: str | None = None

    @field_validator("scaffold", mode="before")
    @classmethod
    def _scaffold_mapping(cls, value: object) -> object:
        return _as_mapping(value)


class Room(BaseModel):
    id: str
    name: str
    order: int
    zone: str
    description: str
    exits: dict[str, str] = Field(default_factory=dict)
    npc: Npc | None = None
    pages: list[Page] = Field(default_factory=list)
    quest: Quest | None = None
    optional: bool = False
    # A guided room teaches by "uncomment the right answer" before its lesson's main room.
    guided: bool = False

    @field_validator("exits", mode="before")
    @classmethod
    def _expand_directions(cls, value: dict[str, str]) -> dict[str, str]:
        return {DIRECTIONS.get(k, k): v for k, v in (value or {}).items()}


class Dungeon(BaseModel):
    """One self-contained curriculum: its rooms, audience and progression."""

    id: str
    name: str
    tagline: str
    audience: str = Field(description="Who this dungeon is written for (shown when choosing).")
    order: int = 0
    start: str
    workspace: str = Field(description="Default folder name for the project the player builds.")
    intro: str = ""
    readme: str | None = Field(default=None, description="README.md for a new workspace.")
    workspace_files: dict[str, str] = Field(
        default_factory=dict,
        description="Files copied into the player's project: target path -> file in template/.",
    )
    vscode_profile: str | None = Field(
        default=None, description="VS Code profile the `code` command opens the project in."
    )
    vscode_extensions: list[str] = Field(
        default_factory=list, description="Extensions to install into that profile."
    )
    ranks: list[tuple[int, str]] = Field(default_factory=lambda: [(0, "Adventurer")])
    rooms: dict[str, Room] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_links(self) -> Dungeon:
        for room in self.rooms.values():
            for direction, target in room.exits.items():
                ref = RoomRef.parse(target)
                if not ref.is_local:
                    raise ValueError(
                        f"{self.id}/{room.id}: exit {direction} -> {target!r} points into another "
                        "dungeon; cross-dungeon exits aren't supported yet (see docs/dungeons.md)"
                    )
                if ref.room not in self.rooms:
                    raise ValueError(
                        f"{self.id}/{room.id}: exit {direction} -> unknown room {target!r}"
                    )
        if self.start not in self.rooms:
            raise ValueError(f"{self.id}: start room {self.start!r} missing")
        if not self.ranks or self.ranks[0][0] != 0:
            raise ValueError(f"{self.id}: ranks must start at 0 XP")
        return self

    # --- rooms -------------------------------------------------------------------

    def ordered(self) -> list[Room]:
        return sorted(self.rooms.values(), key=lambda r: r.order)

    def items(self) -> dict[str, Item]:
        found: dict[str, Item] = {}
        for room in self.ordered():
            if room.quest and room.quest.reward.item:
                found[room.quest.reward.item.name] = room.quest.reward.item
        return found

    def find_room(self, text: str) -> Room | None:
        text = text.lower().strip()
        for room in self.ordered():
            if text in (room.id, room.name.lower()) or text in room.name.lower():
                return room
        return None

    def rank_for(self, xp: int) -> str:
        current = self.ranks[0][1]
        for threshold, title in self.ranks:
            if xp >= threshold:
                current = title
        return current

    # --- files -------------------------------------------------------------------

    def root(self) -> Traversable:
        return resources.files("azurath") / "dungeons" / self.id

    def room_file(self, room_id: str, kind: str, name: str) -> Traversable:
        """Locate ``files/<room>/<kind>/<name>`` (kind is ``scaffold`` or ``solution``)."""
        return self.root() / "files" / room_id / kind / name

    def template_text(self, name: str) -> str:
        return (self.root() / "template" / name).read_text(encoding="utf-8")

    def room_text(self, room_id: str, kind: str, name: str) -> str:
        return self.room_file(room_id, kind, name).read_text(encoding="utf-8")

    @property
    def checks_module(self) -> str:
        """The package whose import registers this dungeon's @check functions."""
        return f"azurath.dungeons.{self.id}.checks"


class Atlas(BaseModel):
    """Every dungeon the game knows about."""

    dungeons: dict[str, Dungeon]

    def ordered(self) -> list[Dungeon]:
        return sorted(self.dungeons.values(), key=lambda d: (d.order, d.id))

    def get(self, dungeon_id: str) -> Dungeon:
        try:
            return self.dungeons[dungeon_id]
        except KeyError:
            known = ", ".join(self.dungeons)
            raise KeyError(f"unknown dungeon {dungeon_id!r} (known: {known})") from None

    def resolve(self, current: Dungeon, target: str) -> tuple[Dungeon, Room]:
        """Follow an exit. Today only local refs exist; portals will resolve here later."""
        ref = RoomRef.parse(target)
        dungeon = current if ref.is_local else self.get(ref.dungeon or "")
        return dungeon, dungeon.rooms[ref.room]


def _dungeons_dir() -> Traversable:
    return resources.files("azurath") / "dungeons"


class ContentError(ValueError):
    """A dungeon's YAML is invalid. The message names the file and every problem."""


def _load_yaml(entry: Traversable, where: str, schema: str) -> dict:
    """Parse strictly (no duplicate keys), then check against a JSON Schema in schemas/."""
    try:
        data = yamlstrict.load(entry.read_text(encoding="utf-8"), source=where)
        yamlschema.validate(data, schema, source=where)
    except (yamlstrict.StrictYAMLError, yamlschema.SchemaError) as exc:
        raise ContentError(str(exc)) from exc
    return data


def _load_dungeon(folder: Traversable) -> Dungeon:
    where = f"dungeons/{folder.name}/dungeon.yaml"
    meta = _load_yaml(folder / "dungeon.yaml", where, "dungeon.schema.json")
    rooms: dict[str, Room] = {}
    for entry in sorted((folder / "rooms").iterdir(), key=lambda t: t.name):
        if not entry.name.endswith((".yaml", ".yml")):
            continue
        room_where = f"dungeons/{folder.name}/rooms/{entry.name}"
        room = Room.model_validate(_load_yaml(entry, room_where, "room.schema.json"))
        if room.id in rooms:
            raise ContentError(f"{room_where}: duplicate room id {room.id}")
        rooms[room.id] = room
    dungeon = Dungeon.model_validate({**meta, "rooms": rooms})
    if dungeon.id != folder.name:
        raise ContentError(f"dungeon folder {folder.name!r} declares id {dungeon.id!r}")
    return dungeon


@cache
def load_atlas() -> Atlas:
    dungeons: dict[str, Dungeon] = {}
    for folder in sorted(_dungeons_dir().iterdir(), key=lambda t: t.name):
        if folder.is_dir() and (folder / "dungeon.yaml").is_file():
            dungeon = _load_dungeon(folder)
            dungeons[dungeon.id] = dungeon
    return Atlas(dungeons=dungeons)


def load_dungeon(dungeon_id: str = DEFAULT_DUNGEON) -> Dungeon:
    return load_atlas().get(dungeon_id)
