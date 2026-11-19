"""Checks for classes, pydantic, pydantic-settings and YAML."""

from __future__ import annotations

import ast
import re

import yaml

from azurath.checks import Report, calls, check, decorator_names, defined_functions
from azurath.checks.packaging import run_pytest
from azurath.workspace import Workspace


def _uses_fixture(tree: ast.Module) -> bool:
    return any(
        any(d.endswith("fixture") for d in decorator_names(fn))
        for fn in defined_functions(tree).values()
    )


@check("class_barracks")
def class_barracks(ws: Workspace, r: Report) -> None:
    if r.python_file(ws, "questboard/repository.py") is None:
        return
    behaviour = ws.probe("""
        import dataclasses
        from questboard.repository import InMemoryRepository, Repository, Reward

        expect(getattr(Repository, "_is_protocol", False), "Repository should subclass typing.Protocol")
        expect(dataclasses.is_dataclass(Reward), "Reward should be a @dataclass")

        total = Reward(10, 5) + Reward(gold=1, xp=1)
        expect(total == Reward(11, 6), f"Reward(10, 5) + Reward(1, 1) gave {total!r}")
        expect(Reward(3).xp == 0, "Reward.xp should default to 0")
        try:
            total.gold = 0
            expect(False, "Reward should be frozen (assignment must fail)")
        except dataclasses.FrozenInstanceError:
            pass
        try:
            Reward(1) + 5
            expect(False, "Reward(1) + 5 should raise TypeError (return NotImplemented)")
        except TypeError:
            pass

        repo = InMemoryRepository()
        repo.add("a", 1)
        repo.add("b", 2)
        expect(len(repo) == 2, f"len(repo) should be 2, got {len(repo)}")
        expect("a" in repo and "zzz" not in repo, "`key in repo` should check keys")
        expect(repo.get("a") == 1, "repo.get('a') should return 1")
        expect(repo.get("zzz") is None, "repo.get(missing) should return None")
        expect(repo.all() == [1, 2], f"repo.all() should be [1, 2], got {repo.all()!r}")
        expect(list(repo) == [1, 2], f"iterating should yield [1, 2], got {list(repo)!r}")
        try:
            repo.add("a", 3)
            expect(False, "adding a duplicate key should raise KeyError")
        except KeyError:
            pass
        expect(repo.get("a") == 1, "a rejected duplicate must not overwrite the original")
    """)
    r.probe(behaviour, "`Reward` and `InMemoryRepository` behave as specified")
    tree = r.python_file(ws, "tests/test_repository.py")
    if tree is None:
        return
    r.require(_uses_fixture(tree), "`tests/test_repository.py` defines a `@pytest.fixture`")
    tests = [n for n in defined_functions(tree) if n.startswith("test")]
    r.require(len(tests) >= 3, "at least 3 tests", f"found {len(tests)}")
    run_pytest(ws, r, "tests/test_repository.py", "repository tests pass")


@check("pydantic_citadel")
def pydantic_citadel(ws: Workspace, r: Report) -> None:
    if r.python_file(ws, "questboard/models.py") is None:
        return
    behaviour = ws.probe("""
        from uuid import UUID
        from pydantic import BaseModel, ValidationError
        from questboard.models import Quest, Rank

        expect(issubclass(Quest, BaseModel), "Quest should be a pydantic BaseModel")
        expect([r.value for r in Rank] == ["S", "A", "B", "C"], "Rank should have members S, A, B, C in that order")
        expect(isinstance(Rank.S, str), "Rank should be a StrEnum (members are strings)")

        q = Quest(title="  Slay the Dragon ", reward=500, rank="s", guilds=["mages"])
        expect(q.title == "Slay the Dragon", f"title should be stripped, got {q.title!r}")
        expect(q.rank is Rank.S, f"rank 's' should become Rank.S, got {q.rank!r}")
        expect(getattr(q, "slug", None) == "slay-the-dragon", f"slug should be 'slay-the-dragon', got {getattr(q, 'slug', None)!r}")
        expect(isinstance(q.id, UUID), "id should be a UUID")
        expect(Quest(title="Rats", reward=5).id != Quest(title="Rats", reward=5).id, "each quest needs its own id (default_factory)")
        expect(Quest(title="Rats", reward="5").reward == 5, "reward '5' should be coerced to 5")
        r = Quest(title="Rats", reward=5)
        expect(r.rank is Rank.C, "rank should default to C")
        expect(r.guilds == [], "guilds should default to []")
        expect(Quest(title="Rats", reward=1, rank=" a ").rank is Rank.A, "rank ' a ' should become Rank.A")

        bad_inputs = {
            "title too short ('ab')": dict(title="ab", reward=1),
            "title too long (81 chars)": dict(title="x" * 81, reward=1),
            "whitespace-padded short title ('  ab  ')": dict(title="  ab  ", reward=1),
            "negative reward": dict(title="Rats", reward=-1),
            "unknown rank 'Z'": dict(title="Rats", reward=1, rank="Z"),
            "S-rank paying only 50": dict(title="Cheap dragon", reward=50, rank="S"),
        }
        for label, data in bad_inputs.items():
            try:
                Quest(**data)
                expect(False, f"{label} should raise ValidationError")
            except ValidationError:
                pass
        Quest(title="Proper dragon", reward=100, rank="S")

        dumped = q.model_dump(mode="json")
        expect(dumped.get("slug") == "slay-the-dragon", "model_dump() should include the computed slug")
        expect(isinstance(dumped.get("id"), str), "model_dump(mode='json') should render id as a string")
        expect(dumped.get("rank") == "S", "model_dump(mode='json') should render rank as 'S'")
        again = Quest.model_validate_json(q.model_dump_json(exclude={"slug"}))
        expect(again == q, "a quest should survive a JSON round trip")
    """)
    r.probe(behaviour, "`Quest` validates and serialises as specified")
    tree = r.python_file(ws, "tests/test_models.py")
    if tree is None:
        return
    source = ws.read("tests/test_models.py") or ""
    r.require(
        any(c.endswith("raises") for c in calls(tree)) and "ValidationError" in source,
        "`tests/test_models.py` uses `pytest.raises(ValidationError)`",
    )
    run_pytest(ws, r, "tests/test_models.py", "model tests pass")


SETTINGS_ENV = {
    "QUESTBOARD_STORAGE_CONNECTION": "UseDevelopmentStorage=true",
    "QUESTBOARD_MAX_ACTIVE_QUESTS": "5",
    "QUESTBOARD_GUILDS": '["mages", "clerics"]',
    "QUESTBOARD_ENVIRONMENT": "prod",
}


@check("settings_observatory")
def settings_observatory(ws: Workspace, r: Report) -> None:
    if r.python_file(ws, "questboard/settings.py") is None:
        return
    reads = ws.probe(
        """
        from pydantic import SecretStr
        from pydantic_settings import BaseSettings
        from questboard.settings import Settings, get_settings

        expect(issubclass(Settings, BaseSettings), "Settings should subclass pydantic_settings.BaseSettings")
        s = Settings(_env_file=None)
        expect(s.max_active_quests == 5, f"QUESTBOARD_MAX_ACTIVE_QUESTS=5 should give 5, got {s.max_active_quests!r}")
        expect(s.environment == "prod", f"QUESTBOARD_ENVIRONMENT=prod should give 'prod', got {s.environment!r}")
        expect(s.guilds == ["mages", "clerics"], f"QUESTBOARD_GUILDS (JSON) should parse to a list, got {s.guilds!r}")
        expect(isinstance(s.storage_connection, SecretStr), "storage_connection should be a SecretStr")
        expect("UseDevelopmentStorage" not in repr(s), "the secret must not appear in repr(settings)")
        expect(s.storage_connection.get_secret_value() == "UseDevelopmentStorage=true", "secret value not read from QUESTBOARD_STORAGE_CONNECTION")
        get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
        expect(get_settings() is get_settings(), "get_settings() should return the same cached instance")
        expect(Settings.model_config.get("env_file") in (".env", (".env",), [".env"]), "Settings should read an optional .env file (env_file='.env')")
    """,
        env=SETTINGS_ENV,
    )
    r.probe(reads, "`Settings` reads typed values from `QUESTBOARD_*` variables")
    defaults = ws.probe("""
        import os
        from pydantic import ValidationError
        from questboard.settings import Settings
        for k in list(os.environ):
            if k.upper().startswith("QUESTBOARD_"):
                del os.environ[k]
        s = Settings(storage_connection="x", _env_file=None)
        expect(s.environment == "dev", f"environment should default to 'dev', got {s.environment!r}")
        expect(s.max_active_quests == 10, f"max_active_quests should default to 10, got {s.max_active_quests!r}")
        expect(s.guilds == ["mages", "rogues", "bards"], f"guilds default is wrong: {s.guilds!r}")
        for label, kwargs in {
            "missing storage_connection": {},
            "environment='staging'": {"storage_connection": "x", "environment": "staging"},
            "max_active_quests=0": {"storage_connection": "x", "max_active_quests": 0},
        }.items():
            try:
                Settings(_env_file=None, **kwargs)
                expect(False, f"{label} should raise ValidationError")
            except ValidationError:
                pass
    """)
    r.probe(defaults, "defaults and validation rules are right")
    r.require(
        ws.git_ignores(".env"),
        "git ignores `.env`",
        "Add `.env` to .gitignore. Secrets never go in git.",
    )
    tree = r.python_file(ws, "tests/test_settings.py")
    if tree is None:
        return
    r.require(
        "monkeypatch" in (ws.read("tests/test_settings.py") or ""),
        "`tests/test_settings.py` uses `monkeypatch`",
    )
    run_pytest(ws, r, "tests/test_settings.py", "settings tests pass")


EVIL_YAML = """\
quests: !!python/object/apply:builtins.exec ["open(r'{marker}', 'w').write('pwned')"]
"""


@check("yaml_scriptorium")
def yaml_scriptorium(ws: Workspace, r: Report) -> None:
    rel = "data/quests.yaml"
    if not r.file(ws, rel):
        return
    text = ws.read(rel) or ""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        r.require(False, f"`{rel}` is valid YAML", str(exc))
        return
    quests = data.get("quests") if isinstance(data, dict) else None
    r.require(
        isinstance(quests, list) and len(quests) >= 3,
        "`quests:` is a list of at least 3 quests",
        f"found {len(quests) if isinstance(quests, list) else type(quests).__name__}",
    )
    r.require(
        re.search(r"&\w", text) and re.search(r"\*\w", text),
        "uses an anchor (`&name`) and an alias (`*name`)",
    )

    tree = r.python_file(ws, "questboard/seed.py")
    if tree is None:
        return
    unsafe = [
        c
        for c in calls(tree)
        if c in {"yaml.load", "yaml.load_all", "yaml.unsafe_load", "load", "unsafe_load"}
    ]
    r.require(
        not unsafe,
        "`seed.py` uses `yaml.safe_load`, never `yaml.load`",
        f"found: {', '.join(unsafe)}",
    )
    loads = ws.probe("""
        from questboard.models import Quest
        from questboard.seed import load_quests
        quests = load_quests("data/quests.yaml")
        expect(isinstance(quests, list), f"load_quests should return a list, got {type(quests).__name__}")
        expect(len(quests) >= 3, f"expected at least 3 quests, got {len(quests)}")
        expect(all(isinstance(q, Quest) for q in quests), "every item should be a Quest model")
        from pathlib import Path
        expect(len(load_quests(Path("data/quests.yaml"))) == len(quests), "load_quests should accept a Path too")
    """)
    r.probe(loads, "`load_quests('data/quests.yaml')` returns validated `Quest` models")
    attack = ws.probe(
        """
        import os, tempfile
        from questboard.seed import load_quests
        with tempfile.TemporaryDirectory() as tmp:
            marker = os.path.join(tmp, "PWNED")
            evil = os.path.join(tmp, "evil.yaml")
            with open(evil, "w") as f:
                f.write(EVIL.replace("{marker}", marker))
            try:
                load_quests(evil)
            except Exception:
                pass  # refusing to load is the right answer
            expect(not os.path.exists(marker), "a malicious YAML file executed code! Use yaml.safe_load")
    """.replace("EVIL", repr(EVIL_YAML))
    )
    r.probe(attack, "a malicious `!!python/object/apply` payload does not execute")
