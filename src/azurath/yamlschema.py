"""Validate YAML data against the JSON Schema files in ``azurath/schemas/``.

The schemas are plain JSON Schema (draft 2020-12), so they're the single source of
truth: the game checks its own content against them when it loads, the tests check
every YAML file in the repo, and editors (VS Code's YAML extension) use the same
files to underline mistakes as you type.

| Schema | For |
|---|---|
| ``room.schema.json`` | ``dungeons/<id>/rooms/*.yaml`` |
| ``dungeon.schema.json`` | ``dungeons/<id>/dungeon.yaml`` |
| ``workflow.schema.json`` | GitHub Actions workflows (this repo's and the players') |
| ``quests.schema.json`` | the YAML Scriptorium's quest seed data |
| ``common.schema.json`` | shared definitions the others ``$ref`` |
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

SCHEMA_DIR = resources.files("azurath") / "schemas"


class SchemaError(ValueError):
    """Data doesn't match its JSON Schema. The message lists every problem."""


def schema_names() -> list[str]:
    return sorted(p.name for p in SCHEMA_DIR.iterdir() if p.name.endswith(".schema.json"))


@cache
def load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@cache
def _registry() -> Registry:
    resources_ = [
        (load_schema(name)["$id"], Resource.from_contents(load_schema(name)))
        for name in schema_names()
    ]
    return Registry().with_resources(resources_)


@cache
def validator(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=_registry())


def prepare_workflow(data: Any) -> Any:
    """PyYAML is YAML 1.1, where the key ``on`` means True. Put it back before validating."""
    if isinstance(data, dict) and True in data:
        return {("on" if key is True else key): value for key, value in data.items()}
    return data


def _describe(error: ValidationError) -> str:
    where = error.json_path.removeprefix("$") or "(top level)"
    where = where.removeprefix(".")
    if error.validator == "oneOf" and error.context:
        # Report the most specific reason a oneOf failed, not "is not valid under any".
        # A wrong-type branch ("is not of type 'array'") is the least useful explanation.
        best = min(
            error.context,
            key=lambda e: (e.validator == "type", -len(e.absolute_path), e.message),
        )
        return f"{where}: {best.message}"
    return f"{where}: {error.message}"


def errors(data: Any, name: str) -> list[str]:
    if name == "workflow.schema.json":
        data = prepare_workflow(data)
    found = sorted(validator(name).iter_errors(data), key=lambda e: list(map(str, e.absolute_path)))
    return [_describe(e) for e in found]


def validate(data: Any, name: str, source: str = "<yaml>") -> None:
    problems = errors(data, name)
    if problems:
        listed = "\n".join(f"  - {p}" for p in problems)
        raise SchemaError(f"{source} doesn't match {name}:\n{listed}")
