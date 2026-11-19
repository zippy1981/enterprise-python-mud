"""Saved player progress, stored as a pydantic model serialized to JSON."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

SAVE_DIR = ".azurath"
SAVE_FILE = "save.json"

LEVELS: list[tuple[int, str]] = [
    (0, "Curious Visitor"),
    (100, "Apprentice Pythonista"),
    (400, "Junior Pythonista"),
    (900, "Pythonista"),
    (1500, "Senior Pythonista"),
    (2200, "Staff Pythonista"),
    (3000, "Principal Pythonista"),
    (4000, "Archmage of Azurath"),
]


class PlayerState(BaseModel):
    """Everything we need to resume a session."""

    version: int = 1
    name: str = "Adventurer"
    room: str = "gatehouse"
    visited: list[str] = Field(default_factory=lambda: ["gatehouse"])
    completed: dict[str, datetime] = Field(default_factory=dict)
    hints: dict[str, int] = Field(default_factory=dict)
    pages: dict[str, int] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    xp: int = 0

    @property
    def title(self) -> str:
        current = LEVELS[0][1]
        for threshold, name in LEVELS:
            if self.xp >= threshold:
                current = name
        return current

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
