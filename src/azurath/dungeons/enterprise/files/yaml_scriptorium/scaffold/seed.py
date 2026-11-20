"""Load seed quests from YAML."""

from pathlib import Path

import yaml
from pydantic import TypeAdapter

from questboard.models import Quest

_QUESTS = TypeAdapter(list[Quest])


def load_quests(path: str | Path) -> list[Quest]:
    # TODO: read the file, yaml.safe_load it, validate data["quests"]
    raise NotImplementedError
