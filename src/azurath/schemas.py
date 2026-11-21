"""Strict schemas for the repo's other YAML files, and JSON Schema export for editors.

Room and dungeon files are validated by the models in ``azurath.content``. This module
adds the rest: GitHub Actions workflows (the repo's own CI, and the workflows players
write in the CI rooms) and the YAML Scriptorium's quest seed data.

``python -m azurath.schemas [folder]`` writes JSON Schema files (default ``schemas/``)
that VS Code's YAML extension uses to flag mistakes as you type; a test keeps them in
sync with the models.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from azurath.content import Dungeon, Identifier, Room, StrictModel, Text

# --- GitHub Actions workflows ----------------------------------------------------------

Scalar = str | int | float | bool
EVENTS = {
    "push",
    "pull_request",
    "pull_request_target",
    "workflow_dispatch",
    "workflow_call",
    "schedule",
    "release",
    "merge_group",
    "workflow_run",
    "repository_dispatch",
    "issues",
    "issue_comment",
    "create",
    "delete",
    "deployment",
    "page_build",
    "registry_package",
}


class WorkflowModel(StrictModel):
    # GitHub uses kebab-case keys (`runs-on`). Accept ONLY those, so a snake_case typo
    # like `runs_on`, which GitHub would reject, is caught here too.
    model_config = ConfigDict(extra="forbid", strict=True, populate_by_name=False)


class Step(WorkflowModel):
    name: Text | None = None
    id: str | None = None
    uses: Text | None = None
    run: Text | None = None
    with_: dict[str, Scalar] | None = Field(default=None, alias="with")
    env: dict[str, Scalar] | None = None
    if_: str | bool | None = Field(default=None, alias="if")
    shell: str | None = None
    working_directory: str | None = Field(default=None, alias="working-directory")
    continue_on_error: bool | str | None = Field(default=None, alias="continue-on-error")
    timeout_minutes: int | None = Field(default=None, alias="timeout-minutes")

    @model_validator(mode="after")
    def _uses_or_run(self) -> Step:
        if (self.uses is None) == (self.run is None):
            raise ValueError("a step needs exactly one of `uses:` or `run:`")
        return self


class Strategy(WorkflowModel):
    matrix: dict[str, list[Any] | str]
    fail_fast: bool | None = Field(default=None, alias="fail-fast")
    max_parallel: int | None = Field(default=None, alias="max-parallel")


class Job(WorkflowModel):
    name: Text | None = None
    runs_on: str | list[str] = Field(alias="runs-on")
    needs: str | list[str] | None = None
    if_: str | bool | None = Field(default=None, alias="if")
    permissions: str | dict[str, str] | None = None
    env: dict[str, Scalar] | None = None
    defaults: dict[str, Any] | None = None
    strategy: Strategy | None = None
    environment: str | dict[str, str] | None = None
    concurrency: str | dict[str, Any] | None = None
    outputs: dict[str, str] | None = None
    services: dict[str, Any] | None = None
    container: str | dict[str, Any] | None = None
    timeout_minutes: int | None = Field(default=None, alias="timeout-minutes")
    continue_on_error: bool | str | None = Field(default=None, alias="continue-on-error")
    steps: list[Step] = Field(min_length=1)


class Workflow(WorkflowModel):
    name: Text | None = None
    run_name: str | None = Field(default=None, alias="run-name")
    on: str | list[str] | dict[str, Any]
    permissions: str | dict[str, str] | None = None
    env: dict[str, Scalar] | None = None
    defaults: dict[str, Any] | None = None
    concurrency: str | dict[str, Any] | None = None
    jobs: dict[str, Job] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _yaml_on_is_true(cls, data: Any) -> Any:
        """PyYAML is YAML 1.1, where the key `on` means True. Put it back."""
        if isinstance(data, dict) and True in data:
            data = {("on" if k is True else k): v for k, v in data.items()}
        return data

    @model_validator(mode="after")
    def _known_events(self) -> Workflow:
        events = {self.on} if isinstance(self.on, str) else set(self.on)
        unknown = events - EVENTS
        if unknown:
            raise ValueError(f"unknown trigger(s) in `on:`: {sorted(unknown)}")
        return self


# --- the YAML Scriptorium's seed data -----------------------------------------------------


class QuestSeed(StrictModel):
    title: Text
    reward: int = Field(ge=0)
    rank: Literal["S", "A", "B", "C"] = "C"
    guilds: list[Text] = Field(default_factory=list)


class QuestSeedFile(StrictModel):
    defaults: dict[str, Any] | None = None  # an anchor for `<<: *defaults` merges
    quests: list[QuestSeed] = Field(min_length=1)


# --- JSON Schema export -------------------------------------------------------------------


def _dungeon_file_schema() -> dict[str, Any]:
    schema = Dungeon.model_json_schema()
    schema["properties"].pop("rooms", None)  # rooms live in rooms/*.yaml, not dungeon.yaml
    schema["title"] = "Azurath dungeon.yaml"
    return schema


def json_schemas() -> dict[str, dict[str, Any]]:
    room = Room.model_json_schema()
    room["title"] = "Azurath room"
    seeds = QuestSeedFile.model_json_schema()
    seeds["title"] = "YAML Scriptorium quest seed data"
    return {
        "room.schema.json": room,
        "dungeon.schema.json": _dungeon_file_schema(),
        "quests.schema.json": seeds,
    }


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_json_schemas(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for name, schema in json_schemas().items():
        path = folder / name
        path.write_text(render(schema), encoding="utf-8", newline="\n")
        written.append(path)
    return written


__all__ = ["Identifier", "QuestSeedFile", "Workflow", "json_schemas", "write_json_schemas"]

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("schemas")
    for path in write_json_schemas(out):
        print(f"wrote {path}")
