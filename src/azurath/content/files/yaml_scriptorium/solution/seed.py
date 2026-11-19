"""Load seed quests from YAML."""

from pathlib import Path

import yaml
from pydantic import TypeAdapter

from questboard.models import Quest

_QUESTS = TypeAdapter(list[Quest])


def load_quests(path: str | Path) -> list[Quest]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping with a 'quests' key")
    return _QUESTS.validate_python(data.get("quests", []))
