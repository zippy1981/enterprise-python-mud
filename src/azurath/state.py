"""Saved player progress, stored as a pydantic model serialized to JSON."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

SAVE_DIR = ".azurath"
SAVE_FILE = "save.json"


class PlayerState(BaseModel):
    """Everything we need to resume a session."""

    version: int = 1
    # Which dungeon this save (and its workspace) belongs to. Saves written before
    # there was more than one dungeon have no field, so they default to the first.
    dungeon: str = "enterprise"
    name: str = "Adventurer"
    room: str = "gatehouse"
    visited: list[str] = Field(default_factory=lambda: ["gatehouse"])
    completed: dict[str, datetime] = Field(default_factory=dict)
    hints: dict[str, int] = Field(default_factory=dict)
    pages: dict[str, int] = Field(default_factory=dict)
    # Every page the player has opened, per room (1-based), to know what's still unread.
    seen_pages: dict[str, list[int]] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    xp: int = 0

    @classmethod
    def new(cls, dungeon_id: str, start_room: str, name: str = "Adventurer") -> PlayerState:
        return cls(dungeon=dungeon_id, name=name, room=start_room, visited=[start_room])

    def mark_read(self, room_id: str, page: int) -> None:
        self.pages[room_id] = page
        seen = self.seen_pages.setdefault(room_id, [])
        if page not in seen:
            seen.append(page)
            seen.sort()

    def unread_pages(self, room_id: str, total: int) -> list[int]:
        seen = set(self.seen_pages.get(room_id, []))
        if not seen and self.pages.get(room_id):  # saves from before seen_pages existed
            seen = set(range(1, self.pages[room_id] + 1))
        return [n for n in range(1, total + 1) if n not in seen]

    def visit(self, room_id: str) -> None:
        self.room = room_id
        if room_id not in self.visited:
            self.visited.append(room_id)

    def complete(self, room_id: str) -> bool:
        """Mark a room's quest done. Returns True the first time only."""
        if room_id in self.completed:
            return False
        self.completed[room_id] = datetime.now(UTC)
        return True

    # --- persistence -------------------------------------------------------

    @staticmethod
    def path_for(workspace: Path) -> Path:
        return workspace / SAVE_DIR / SAVE_FILE

    @classmethod
    def load(cls, workspace: Path) -> PlayerState | None:
        path = cls.path_for(workspace)
        if not path.exists():
            return None
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            backup = path.with_suffix(".corrupt.json")
            path.replace(backup)
            return None

    def save(self, workspace: Path) -> None:
        path = self.path_for(workspace)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)  # atomic on every OS we care about
