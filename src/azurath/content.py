"""World content: rooms are YAML files validated by pydantic models.

The lesson text lives in ``content/rooms/*.yaml``. Starter (scaffold) and
reference (solution) files live in ``content/files/<room_id>/``. Loading them
through ``importlib.resources`` means it still works after the package is
installed as a wheel, the same way you'd read an embedded resource from an
assembly in .NET.
"""

from __future__ import annotations

from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

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

    @field_validator("exits", mode="before")
    @classmethod
    def _expand_directions(cls, value: dict[str, str]) -> dict[str, str]:
        return {DIRECTIONS.get(k, k): v for k, v in (value or {}).items()}


class World(BaseModel):
    rooms: dict[str, Room]
    start: str = "gatehouse"

    @model_validator(mode="after")
    def _check_links(self) -> World:
        for room in self.rooms.values():
            for direction, target in room.exits.items():
                if target not in self.rooms:
                    raise ValueError(f"{room.id}: exit {direction} -> unknown room {target!r}")
        if self.start not in self.rooms:
            raise ValueError(f"start room {self.start!r} missing")
        return self

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


def content_root() -> Traversable:
    return resources.files("azurath") / "content"


def _rooms_dir() -> Traversable:
    return content_root() / "rooms"


@cache
def load_world() -> World:
    rooms: dict[str, Room] = {}
    for entry in sorted(_rooms_dir().iterdir(), key=lambda t: t.name):
        if not entry.name.endswith((".yaml", ".yml")):
            continue
        data = yaml.safe_load(entry.read_text(encoding="utf-8"))
        room = Room.model_validate(data)
        if room.id in rooms:
            raise ValueError(f"duplicate room id {room.id}")
        rooms[room.id] = room
    return World(rooms=rooms)


def room_file(room_id: str, kind: str, name: str) -> Traversable:
    """Locate ``content/files/<room>/<kind>/<name>`` (kind is scaffold or solution)."""
    return content_root() / "files" / room_id / kind / name
