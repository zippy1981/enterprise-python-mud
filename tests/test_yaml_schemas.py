"""Every YAML file in the repo is parsed strictly and validated against a strict schema."""

import fnmatch
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from azurath import yamlstrict
from azurath.content import Dungeon, Room
from azurath.schemas import QuestSeedFile, Workflow, json_schemas, render

ROOT = Path(__file__).parents[1]

# (glob, schema). Every tracked .yaml/.yml file must match one of these.
RULES: list[tuple[str, type[BaseModel] | None]] = [
    ("src/azurath/dungeons/*/rooms/*.yaml", Room),
    ("src/azurath/dungeons/*/dungeon.yaml", None),  # validated as a whole dungeon below
    (".github/workflows/*.yml", Workflow),
    ("src/azurath/dungeons/*/files/*/*/*.yml", Workflow),  # workflows players write
    ("src/azurath/dungeons/enterprise/files/yaml_scriptorium/*/quests.yaml", QuestSeedFile),
]


def tracked_yaml() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout")
    res = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [p for p in res.stdout.splitlines() if p.endswith((".yaml", ".yml"))]


def rule_for(path: str) -> tuple[str, type[BaseModel] | None] | None:
    return next(((g, m) for g, m in RULES if fnmatch.fnmatch(path, g)), None)


def test_every_yaml_file_has_a_schema() -> None:
    orphans = [p for p in tracked_yaml() if rule_for(p) is None]
    assert not orphans, f"add a schema rule in tests/test_yaml_schemas.py for: {orphans}"


@pytest.mark.parametrize("path", tracked_yaml() if (ROOT / ".git").exists() else [])
def test_yaml_file_is_valid(path: str) -> None:
    data = yamlstrict.load((ROOT / path).read_text(encoding="utf-8"), source=path)
    rule = rule_for(path)
    assert rule is not None
    if rule[1] is not None:
        rule[1].model_validate(data)


def test_json_schemas_for_editors_are_up_to_date() -> None:
    for name, schema in json_schemas().items():
        committed = (ROOT / "schemas" / name).read_text(encoding="utf-8")
        assert committed == render(schema), (
            f"schemas/{name} is stale: run `uv run python -m azurath.schemas`"
        )


def test_vscode_maps_the_schemas() -> None:
    settings = json.loads((ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    mapped = settings["yaml.schemas"]
    for name in json_schemas():
        assert f"./schemas/{name}" in mapped


# --- strictness ---------------------------------------------------------------------------

GOOD_ROOM = {
    "id": "a_room",
    "name": "A Room",
    "order": 0,
    "zone": "Zone",
    "description": "Words.",
    "exits": {"n": "b_room"},
    "quest": {"title": "T", "brief": "B", "check": "a_room", "reward": {"xp": 10}},
}


def room_with(**changes: object) -> dict:
    return {**GOOD_ROOM, **changes}


def test_a_good_room_passes() -> None:
    assert Room.model_validate(GOOD_ROOM).exits == {"north": "b_room"}


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"exit": {"north": "b_room"}}, "Extra inputs are not permitted"),  # typo: exit/exits
        ({"order": "1"}, "Input should be a valid integer"),  # no coercion
        ({"id": "Bad Room"}, "String should match pattern"),
        ({"name": "   "}, "String should match pattern"),  # blank text
        ({"exits": {"sideways": "b_room"}}, "Input should be"),  # not a direction
        ({"exits": {"north": "B Room"}}, "String should match pattern"),
        ({"order": -1}, "greater than or equal to 0"),
        ({"quest": {**GOOD_ROOM["quest"], "reward": {"xp": "10"}}}, "valid integer"),
        ({"quest": {**GOOD_ROOM["quest"], "scaffold": {"../escape.py": "x.py"}}}, "climb out"),
        ({"quest": {**GOOD_ROOM["quest"], "scaffold": {"/abs.py": "x.py"}}}, "relative path"),
    ],
)
def test_room_mistakes_are_rejected(changes: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Room.model_validate(room_with(**changes))


def test_duplicate_keys_are_rejected_with_a_line_number() -> None:
    with pytest.raises(
        yamlstrict.StrictYAMLError, match=r"duplicate key 'hints' \(first on line 2\)"
    ):
        yamlstrict.load("quest:\n  hints: [a]\n  hints: [b]\n", "room.yaml")


def test_a_merge_may_override_an_anchored_key() -> None:
    data = yamlstrict.load("base: &b {rank: C, reward: 1}\nq: {<<: *b, rank: S}\n")
    assert data["q"] == {"rank": "S", "reward": 1}


def test_dungeon_unknown_keys_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        Dungeon.model_validate(
            {
                "id": "d",
                "name": "D",
                "tagline": "T",
                "audience": "A",
                "start": "a_room",
                "workspace": "proj",
                "rooms": {"a_room": Room.model_validate(room_with(exits={}))},
                "colour": "blue",
            }
        )


@pytest.mark.parametrize(
    ("workflow", "message"),
    [
        (
            {"on": "push", "jobs": {"t": {"runs-on": "x", "steps": [{"uses": "a", "run": "b"}]}}},
            "exactly one of",
        ),
        (
            {"on": "push", "jobs": {"t": {"runs-on": "x", "steps": [{"name": "nothing"}]}}},
            "exactly one of",
        ),
        (
            {"on": "psuh", "jobs": {"t": {"runs-on": "x", "steps": [{"run": "b"}]}}},
            "unknown trigger",
        ),
        (
            {"on": "push", "jobs": {"t": {"runs_on": "x", "steps": [{"run": "b"}]}}},
            "Field required",
        ),
        (
            {"on": "push", "jobs": {"t": {"runs-on": "x", "steps": [{"run": "b", "wtih": {}}]}}},
            "Extra inputs",
        ),
    ],
)
def test_workflow_mistakes_are_rejected(workflow: dict, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Workflow.model_validate(workflow)


def test_pyyaml_reading_on_as_true_is_handled() -> None:
    data = yamlstrict.load("on: [push]\njobs:\n  t:\n    runs-on: x\n    steps:\n      - run: hi\n")
    assert True in data  # YAML 1.1 strikes again
    assert Workflow.model_validate(data).on == ["push"]
