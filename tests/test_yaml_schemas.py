"""Every YAML file in the repo is parsed strictly and checked against a JSON Schema."""

import fnmatch
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from azurath import yamlschema, yamlstrict
from azurath.content import Dungeon, Item, Npc, Page, Quest, Reward, Room, Solution

ROOT = Path(__file__).parents[1]

# (glob, JSON Schema in src/azurath/schemas/). Every tracked .yaml/.yml must match one.
RULES: list[tuple[str, str]] = [
    ("src/azurath/dungeons/*/rooms/*.yaml", "room.schema.json"),
    ("src/azurath/dungeons/*/dungeon.yaml", "dungeon.schema.json"),
    (".github/workflows/*.yml", "workflow.schema.json"),
    ("src/azurath/dungeons/*/files/*/*/*.yml", "workflow.schema.json"),  # workflows players write
    ("src/azurath/dungeons/enterprise/files/yaml_scriptorium/*/quests.yaml", "quests.schema.json"),
]


def tracked_yaml() -> list[str]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        return []
    res = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [p for p in res.stdout.splitlines() if p.endswith((".yaml", ".yml"))]


def schema_for(path: str) -> str | None:
    return next((schema for glob, schema in RULES if fnmatch.fnmatch(path, glob)), None)


def test_every_yaml_file_has_a_schema() -> None:
    files = tracked_yaml()
    if not files:
        pytest.skip("needs a git checkout")
    orphans = [p for p in files if schema_for(p) is None]
    assert not orphans, f"add a rule in tests/test_yaml_schemas.py for: {orphans}"


@pytest.mark.parametrize("path", tracked_yaml())
def test_yaml_file_matches_its_schema(path: str) -> None:
    data = yamlstrict.load((ROOT / path).read_text(encoding="utf-8"), source=path)
    yamlschema.validate(data, schema_for(path), source=path)


@pytest.mark.parametrize("name", yamlschema.schema_names())
def test_schemas_are_valid_json_schema(name: str) -> None:
    Draft202012Validator.check_schema(yamlschema.load_schema(name))


def test_vscode_maps_the_schemas() -> None:
    settings = json.loads((ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8"))
    mapped = settings["yaml.schemas"]
    for name in ("room.schema.json", "dungeon.schema.json", "quests.schema.json"):
        assert f"./src/azurath/schemas/{name}" in mapped


# --- the schemas and the pydantic models that hold the data must agree ------------------


def fields(model) -> set[str]:
    return set(model.model_fields)


@pytest.mark.parametrize(
    ("model", "pointer"),
    [
        (Room, ()),
        (Page, ("$defs", "page")),
        (Npc, ("$defs", "npc")),
        (Item, ("$defs", "item")),
        (Quest, ("$defs", "quest")),
        (Solution, ("$defs", "quest", "properties", "solution")),
        (Reward, ("$defs", "quest", "properties", "reward")),
    ],
    ids=lambda v: getattr(v, "__name__", "/".join(v) if isinstance(v, tuple) else str(v)),
)
def test_room_schema_and_models_cover_the_model_fields(model, pointer: tuple) -> None:
    node = yamlschema.load_schema("room.schema.json")
    for key in pointer:
        node = node[key]
    # The schema may list keys a newer model adds (e.g. on a branch); it must cover every field.
    assert fields(model) <= set(node["properties"])


def test_dungeon_schema_and_model_cover_the_model_fields() -> None:
    schema = yamlschema.load_schema("dungeon.schema.json")
    assert fields(Dungeon) - {"rooms"} <= set(schema["properties"])  # rooms live in rooms/


# --- strictness ----------------------------------------------------------------------------

GOOD_ROOM = {
    "id": "a_room",
    "name": "A Room",
    "order": 0,
    "zone": "Zone",
    "description": "Words.",
    "exits": {"n": "b_room"},
    "quest": {"title": "T", "brief": "B", "check": "a_room", "reward": {"xp": 10}},
}


def room_errors(**changes: object) -> list[str]:
    return yamlschema.errors({**GOOD_ROOM, **changes}, "room.schema.json")


def test_a_good_room_passes() -> None:
    assert room_errors() == []


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"exit": {"north": "b_room"}}, "'exit' was unexpected"),  # typo: exit/exits
        ({"order": "1"}, "is not of type 'integer'"),  # no coercion
        ({"id": "Bad Room"}, "does not match"),
        ({"name": "   "}, "does not match"),  # blank text
        ({"exits": {"sideways": "b_room"}}, "is not one of"),  # not a direction
        ({"exits": {"north": "B Room"}}, "does not match"),
        ({"order": -1}, "less than the minimum"),
        ({"quest": {**GOOD_ROOM["quest"], "reward": {"xp": "10"}}}, "is not of type 'integer'"),
        ({"quest": {**GOOD_ROOM["quest"], "scaffold": {"../escape.py": "x.py"}}}, "does not match"),
        ({"quest": {**GOOD_ROOM["quest"], "scaffold": {"/abs.py": "x.py"}}}, "does not match"),
    ],
)
def test_room_mistakes_are_rejected(changes: dict, message: str) -> None:
    problems = room_errors(**changes)
    assert any(message in p for p in problems), problems


def test_errors_say_where_the_problem_is() -> None:
    problems = room_errors(quest={**GOOD_ROOM["quest"], "reward": {"xp": "10"}})
    assert problems == ["quest.reward.xp: '10' is not of type 'integer'"]


def test_validate_names_the_file() -> None:
    with pytest.raises(yamlschema.SchemaError, match="rooms/x.yaml doesn't match room.schema.json"):
        yamlschema.validate({"id": "x"}, "room.schema.json", source="rooms/x.yaml")


def test_duplicate_keys_are_rejected_with_a_line_number() -> None:
    with pytest.raises(
        yamlstrict.StrictYAMLError, match=r"duplicate key 'hints' \(first on line 2\)"
    ):
        yamlstrict.load("quest:\n  hints: [a]\n  hints: [b]\n", "room.yaml")


def test_a_merge_may_override_an_anchored_key() -> None:
    data = yamlstrict.load("base: &b {rank: C, reward: 1}\nq: {<<: *b, rank: S}\n")
    assert data["q"] == {"rank": "S", "reward": 1}


def test_dungeon_unknown_keys_are_rejected() -> None:
    dungeon = {
        "id": "d",
        "name": "D",
        "tagline": "T",
        "audience": "A",
        "start": "a_room",
        "workspace": "proj",
        "colour": "blue",
    }
    assert any(
        "'colour' was unexpected" in p for p in yamlschema.errors(dungeon, "dungeon.schema.json")
    )


@pytest.mark.parametrize(
    ("workflow", "message"),
    [
        (
            {"on": "push", "jobs": {"t": {"runs-on": "x", "steps": [{"uses": "a", "run": "b"}]}}},
            "should not be valid",
        ),
        (
            {"on": "push", "jobs": {"t": {"runs-on": "x", "steps": [{"name": "nothing"}]}}},
            "is a required property",
        ),
        ({"on": "psuh", "jobs": {"t": {"runs-on": "x", "steps": [{"run": "b"}]}}}, "is not one of"),
        (
            {"on": "push", "jobs": {"t": {"runs_on": "x", "steps": [{"run": "b"}]}}},
            "'runs_on' was unexpected",
        ),
        (
            {"on": "push", "jobs": {"t": {"runs-on": "x", "steps": [{"run": "b", "wtih": {}}]}}},
            "'wtih' was unexpected",
        ),
    ],
)
def test_workflow_mistakes_are_rejected(workflow: dict, message: str) -> None:
    problems = yamlschema.errors(workflow, "workflow.schema.json")
    assert any(message in p for p in problems), problems


def test_pyyaml_reading_on_as_true_is_handled() -> None:
    data = yamlstrict.load("on: [push]\njobs:\n  t:\n    runs-on: x\n    steps:\n      - run: hi\n")
    assert True in data  # YAML 1.1 strikes again
    assert yamlschema.errors(data, "workflow.schema.json") == []


def test_the_game_refuses_invalid_content(tmp_path: Path) -> None:
    from azurath import content

    room = tmp_path / "dungeons" / "x" / "rooms"
    room.mkdir(parents=True)
    (tmp_path / "dungeons" / "x" / "dungeon.yaml").write_text(
        "id: x\nname: X\ntagline: T\naudience: A\nstart: r\nworkspace: x\n", encoding="utf-8"
    )
    (room / "r.yaml").write_text(
        "id: r\nname: R\norder: 0\nzone: Z\ndescription: D\nexit: {}\n", encoding="utf-8"
    )
    with pytest.raises(content.ContentError, match="'exit' was unexpected"):
        content._load_dungeon(tmp_path / "dungeons" / "x")
