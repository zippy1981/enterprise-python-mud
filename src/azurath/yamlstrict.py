"""Strict YAML loading: like ``yaml.safe_load``, but a key may only appear once.

PyYAML quietly keeps the *last* value when a mapping repeats a key, so a room file
with two ``hints:`` blocks would silently lose the first. Here that's an error that
names the file and line.
"""

from __future__ import annotations

from typing import Any

import yaml


class StrictYAMLError(ValueError):
    """The YAML isn't valid, or repeats a key."""


class StrictLoader(yaml.SafeLoader):
    """A SafeLoader that refuses duplicate mapping keys."""


def _no_duplicates(loader: StrictLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    # Only keys written in *this* mapping count. A key that overrides one merged in with
    # `<<: *anchor` is normal YAML (the local value wins), so check before merging.
    seen: dict[Any, int] = {}
    for key_node, _ in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            continue
        key = loader.construct_object(key_node, deep=deep)
        line = key_node.start_mark.line + 1
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"duplicate key {key!r} (first on line {seen[key]})",
                key_node.start_mark,
            )
        seen[key] = line
    return loader.construct_mapping(node, deep=deep)


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def load(text: str, source: str = "<yaml>") -> Any:
    try:
        return yaml.load(text, Loader=StrictLoader)  # noqa: S506 - StrictLoader is a SafeLoader
    except yaml.YAMLError as exc:
        raise StrictYAMLError(f"{source}: {exc}") from exc
