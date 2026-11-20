"""Checks for Azure Functions, Durable Functions and the final deployment prep."""

from __future__ import annotations

import ast
import json
import re

from azurath.checks import Report, calls, checks_for, dotted
from azurath.checks.pyproject import load_pyproject, runtime_deps
from azurath.checks.testing import run_pytest
from azurath.workspace import Workspace

check = checks_for("enterprise")

HTTP_PROBE = """
import inspect, asyncio, json
import azure.functions as func
import function_app

app = getattr(function_app, "app", None)
expect(isinstance(app, func.FunctionApp), "function_app.app should be a func.FunctionApp (or df.DFApp)")
functions = app.get_functions()
summary = {f.get_function_name(): [(b.type, getattr(b, "route", None), [str(getattr(m, "value", m)).upper() for m in (getattr(b, "methods", None) or [])]) for b in f.get_bindings()] for f in functions}
print(json.dumps(summary))
target = None
for f in functions:
    for b in f.get_bindings():
        if b.type == "httpTrigger" and getattr(b, "route", None) == "quests":
            methods = [str(getattr(m, "value", m)).upper() for m in (b.methods or [])]
            if not methods or "POST" in methods:
                target = f
expect(target is not None, "no HTTP function with route='quests' accepting POST")
if target is not None:
    fn = target.get_user_function()
    def call(body):
        req = func.HttpRequest(method="POST", url="/api/quests", body=body, headers={"Content-Type": "application/json"})
        resp = fn(req)
        if inspect.isawaitable(resp):
            resp = asyncio.run(resp)
        return resp
    good = call(json.dumps({"title": "Slay the dragon", "reward": 500, "rank": "S"}).encode())
    expect(good.status_code == 201, f"a valid quest should return 201, got {good.status_code}: {good.get_body()[:200]!r}")
    try:
        data = json.loads(good.get_body())
        expect(data.get("slug") == "slay-the-dragon", f"201 body should include slug 'slay-the-dragon', got {data.get('slug')!r}")
        expect(bool(data.get("id")), "201 body should include the quest id")
    except ValueError:
        expect(False, "201 body is not JSON")
    expect("json" in (good.mimetype or ""), f"responses should use mimetype application/json, got {good.mimetype!r}")
    for label, body in {"an invalid quest": b'{"title": "x", "reward": -1}', "malformed JSON": b"{not json", "an empty body": b""}.items():
        resp = call(body)
        expect(resp.status_code == 400, f"{label} should return 400, got {resp.status_code}")
        try:
            errors = json.loads(resp.get_body()).get("errors")
            expect(bool(errors), f"400 for {label} should include a non-empty 'errors' list")
        except (ValueError, AttributeError):
            expect(False, f"400 for {label} should be a JSON object with 'errors'")
"""


def _read_json(ws: Workspace, r: Report, rel: str) -> dict | None:
    text = ws.read(rel)
    if text is None:
        r.require(False, f"`{rel}` exists", "Try `scaffold`.")
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        r.require(False, f"`{rel}` is valid JSON", str(exc))
        return None
    r.require(isinstance(data, dict), f"`{rel}` is valid JSON")
    return data if isinstance(data, dict) else None


def _host_and_settings(ws: Workspace, r: Report) -> None:
    host = _read_json(ws, r, "host.json")
    if host is not None:
        r.require(host.get("version") == "2.0", '`host.json` has `"version": "2.0"`')
        bundle = host.get("extensionBundle") or {}
        r.require(
            bundle.get("id") == "Microsoft.Azure.Functions.ExtensionBundle",
            "`host.json` declares the `Microsoft.Azure.Functions.ExtensionBundle` extension bundle",
        )
    local = _read_json(ws, r, "local.settings.json")
    if local is not None:
        values = local.get("Values") or {}
        r.require(
            values.get("FUNCTIONS_WORKER_RUNTIME") == "python",
            '`local.settings.json` sets `"FUNCTIONS_WORKER_RUNTIME": "python"`',
        )
    r.require(
        ws.git_ignores("local.settings.json"),
        "git ignores `local.settings.json` (it holds secrets)",
        "Add `local.settings.json` to .gitignore.",
    )
    if ws.is_git_repo():
        r.require(
            not ws.git_tracks("local.settings.json"),
            "`local.settings.json` isn't committed",
            "`!git rm --cached local.settings.json`",
        )


def _require_dependency(ws: Workspace, r: Report, dist: str, module: str) -> bool:
    data = load_pyproject(ws) or {}
    ok = r.require(
        dist in runtime_deps(data), f"`{dist}` is a runtime dependency", f"`!uv add {dist}`"
    )
    venv = ws.venv_python()
    if venv:
        imp = ws.run([str(venv), "-c", f"import {module}"])
        ok = (
            r.require(imp.ok, f"`{module}` imports in `.venv`", imp.tail(3) + "\n`!uv sync`") and ok
        )
    return ok


@check("functions_docks")
def functions_docks(ws: Workspace, r: Report) -> None:
    if not _require_dependency(ws, r, "azure-functions", "azure.functions"):
        return
    if r.python_file(ws, "function_app.py") is None:
        return
    r.probe(
        ws.probe(HTTP_PROBE),
        "POST `/api/quests` returns 201 for good quests and 400 with `errors` for bad ones",
    )
    _host_and_settings(ws, r)
    if r.python_file(ws, "tests/test_function_app.py") is not None:
        r.require(
            "HttpRequest" in (ws.read("tests/test_function_app.py") or ""),
            "`tests/test_function_app.py` builds a `func.HttpRequest`",
        )
        run_pytest(ws, r, "tests/test_function_app.py", "function tests pass")


ORCHESTRATION_PROBE = """
from datetime import datetime, timezone
from questboard.orchestration import process_quest
import inspect

expect(inspect.isgeneratorfunction(process_quest), "process_quest should be a generator function (use yield)")

class Task:
    def __init__(self, kind, name=None, payload=None, children=None):
        self.kind, self.name, self.payload, self.children = kind, name, payload, children or []
    def __repr__(self):
        return f"{self.kind}:{self.name or len(self.children)}"

class FakeContext:
    is_replaying = False
    instance_id = "test-instance"
    def __init__(self, input_):
        self._input = input_
        self.current_utc_datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def get_input(self):
        return self._input
    def call_activity(self, name, input_=None, **kwargs):
        return Task("activity", name, input_ if input_ is not None else kwargs.get("input"))
    def call_activity_with_retry(self, name, retry_options, input_=None, **kwargs):
        return self.call_activity(name, input_, **kwargs)
    def task_all(self, tasks):
        return Task("all", children=list(tasks))
    def new_uuid(self):
        return "00000000-0000-0000-0000-000000000001"

def run(quest):
    ctx = FakeContext(quest)
    gen = process_quest(ctx)
    yielded = []
    def resolve(task):
        if not isinstance(task, Task):
            expect(False, f"orchestrator yielded {task!r}; yield the tasks returned by context.call_activity / task_all")
            return None
        if task.kind == "all":
            return [resolve(t) for t in task.children]
        if task.name == "validate_quest":
            return {**task.payload, "id": "q-123", "slug": "validated"}
        if task.name == "notify_guild":
            return f"told {task.payload!r}"
        if task.name == "award_reward":
            return {"gold": (task.payload or {}).get("reward", 0), "xp": 1}
        return None
    try:
        task = next(gen)
        for _ in range(50):
            yielded.append(task)
            task = gen.send(resolve(task))
        expect(False, "the orchestrator yielded more than 50 times; is it looping?")
        return yielded, None
    except StopIteration as done:
        return yielded, done.value

quest = {"title": "Slay the dragon", "reward": 1500, "rank": "S", "guilds": ["mages", "rogues", "bards"]}
yielded, result = run(quest)
kinds = [repr(t) for t in yielded]
expect(len(yielded) >= 3, f"expected 3 yields (validate, task_all, award), got {kinds}")
if len(yielded) >= 3:
    first, fan, last = yielded[0], yielded[1], yielded[-1]
    expect(first.kind == "activity" and first.name == "validate_quest", f"first yield should be call_activity('validate_quest'), got {first!r}")
    expect(first.payload == quest, "validate_quest should receive the orchestration input unchanged")
    expect(fan.kind == "all", f"second yield should be context.task_all([...]), got {fan!r}. Fan out, then yield ONCE")
    if fan.kind == "all":
        names = [c.name for c in fan.children]
        expect(names == ["notify_guild"] * 3, f"task_all should hold one notify_guild per guild (3), got {names}")
    expect(last.kind == "activity" and last.name == "award_reward", f"last yield should be call_activity('award_reward'), got {last!r}")
    if last.kind == "activity":
        expect(isinstance(last.payload, dict) and last.payload.get("id") == "q-123", "award_reward should receive the *validated* quest")
    expect(len(yielded) == 3, f"expected exactly 3 yields for a quest with guilds, got {kinds}")
expect(isinstance(result, dict), f"the orchestrator should return a dict, got {result!r}")
if isinstance(result, dict):
    for key in ("quest_id", "notified", "reward"):
        expect(key in result, f"the result is missing {key!r}")
    expect(result.get("quest_id") == "q-123", "quest_id should come from the validated quest")
    expect(isinstance(result.get("notified"), list) and len(result.get("notified")) == 3, "notified should list the 3 notify_guild results")
    import json
    try:
        json.dumps(result)
    except TypeError as exc:
        expect(False, f"the result must be JSON-serialisable: {exc}")

_, empty = run({"title": "Rats", "reward": 5, "guilds": []})
expect(isinstance(empty, dict) and empty.get("notified") == [], "a quest with no guilds should finish with notified == []")
"""

BINDINGS_PROBE = """
import json, inspect
import azure.functions as func
import function_app
app = function_app.app
expect(type(app).__name__ == "DFApp", f"function_app.app should be a df.DFApp (Durable-enabled), got {type(app).__name__}")
functions = app.get_functions()
bindings = {f.get_function_name(): [b.type for b in f.get_bindings()] for f in functions}
print(json.dumps(bindings))
orchestrators = [n for n, b in bindings.items() if "orchestrationTrigger" in b]
activities = {n for n, b in bindings.items() if "activityTrigger" in b}
clients = [n for n, b in bindings.items() if "durableClient" in b]
expect(len(orchestrators) == 1, f"expected one orchestrator, found {orchestrators}")
missing = {"validate_quest", "notify_guild", "award_reward"} - activities
expect(not missing, f"missing activities: {sorted(missing)}")
expect(clients, "no function uses @app.durable_client_input to start orchestrations")
expect(any("httpTrigger" in b for b in bindings.values()), "keep your create_quest HTTP function")

users = {f.get_function_name(): f.get_user_function() for f in functions}
if "validate_quest" in users:
    out = users["validate_quest"]({"title": " Slay the dragon ", "reward": 500, "rank": "s", "guilds": ["mages"]})
    expect(isinstance(out, dict), f"validate_quest should return a dict, got {type(out).__name__}")
    if isinstance(out, dict):
        expect(out.get("title") == "Slay the dragon" and out.get("rank") == "S", "validate_quest should normalise via the Quest model")
        expect(isinstance(out.get("id"), str), "validate_quest should return JSON-safe data (model_dump(mode='json'))")
    try:
        users["validate_quest"]({"title": "x", "reward": -1})
        expect(False, "validate_quest should raise for an invalid quest")
    except Exception:
        pass
for name, payload in {"notify_guild": {"guild": "mages", "quest_id": "q-1"},
                      "award_reward": {"title": "Rats", "reward": 50, "rank": "C", "guilds": [], "id": "q-1"}}.items():
    if name in users:
        out = users[name](payload)
        try:
            json.dumps(out)
        except TypeError:
            expect(False, f"{name} must return something JSON-serialisable, got {type(out).__name__}")
print(json.dumps(orchestrators))
"""

NONDETERMINISTIC = {
    "datetime.now",
    "datetime.utcnow",
    "datetime.datetime.now",
    "datetime.datetime.utcnow",
    "date.today",
    "time.time",
    "time.sleep",
    "uuid.uuid4",
    "uuid4",
    "random.random",
    "random.randint",
    "random.choice",
    "random.shuffle",
    "requests.get",
    "requests.post",
    "open",
}


@check("durable_sanctum")
def durable_sanctum(ws: Workspace, r: Report) -> None:
    if not _require_dependency(ws, r, "azure-functions-durable", "azure.durable_functions"):
        return
    tree = r.python_file(ws, "questboard/orchestration.py")
    if tree is None:
        return
    bad = sorted({c for c in calls(tree) if c in NONDETERMINISTIC or c.startswith("random.")})
    r.require(
        not bad,
        "the orchestration is deterministic (no clocks, uuid4, random or I/O)",
        "found: " + ", ".join(bad) + ". `ask orchestrator about determinism`",
    )
    r.probe(
        ws.probe(ORCHESTRATION_PROBE),
        "`process_quest` validates, fans out to every guild, then awards the reward",
    )

    app_tree = r.python_file(ws, "function_app.py")
    if app_tree is None:
        return
    bindings = ws.probe(BINDINGS_PROBE)
    r.probe(
        bindings, "`function_app.py` registers an orchestrator, the three activities and a client"
    )
    orchestrators: list[str] = []
    if bindings.ok and bindings.output:
        try:
            orchestrators = json.loads(bindings.output.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            orchestrators = []
    started = [
        node.args[0].value
        for node in ast.walk(app_tree)
        if isinstance(node, ast.Call)
        and dotted(node.func).endswith("start_new")
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    if orchestrators:
        r.require(
            any(name in orchestrators for name in started),
            "the client starts the orchestrator by its function name",
            f"start_new() was called with {started or 'no string literal'}; the orchestrator is {orchestrators[0]!r}",
        )
    delegates = any(isinstance(n, ast.YieldFrom) for n in ast.walk(app_tree))
    r.suggest(
        delegates, "the orchestrator delegates to `questboard.orchestration` with `yield from`"
    )
    if r.python_file(ws, "tests/test_orchestration.py") is not None:
        run_pytest(ws, r, "tests/test_orchestration.py", "orchestration tests pass")


@check("throne_room")
def throne_room(ws: Workspace, r: Report) -> None:
    reqs = ws.read("requirements.txt")
    if r.require(
        reqs is not None,
        "`requirements.txt` exists",
        "`!uv export --format requirements-txt --no-dev --no-emit-project --no-hashes -o requirements.txt`",
    ):
        assert reqs is not None
        lines = [
            ln.strip() for ln in reqs.splitlines() if ln.strip() and not ln.strip().startswith("#")
        ]
        pins = {
            re.split(r"[=<>~!\[; ]", ln, maxsplit=1)[0].lower(): ln
            for ln in lines
            if not ln.startswith("-")
        }
        r.require(
            "autogenerated by uv" in reqs or "uv export" in reqs,
            "`requirements.txt` was generated by `uv export`",
            "Regenerate it with uv rather than by hand.",
        )
        for dist in (
            "azure-functions",
            "azure-functions-durable",
            "pydantic",
            "pydantic-settings",
            "pyyaml",
        ):
            line = pins.get(dist)
            r.require(
                line is not None and "==" in line,
                f"`{dist}` is pinned with `==`",
                f"found: {line!r}",
            )
        r.require("pytest" not in pins and "ruff" not in pins, "no dev dependencies (`--no-dev`)")
        r.require(
            not any(ln.startswith("-e") for ln in lines), "no `-e .` line (`--no-emit-project`)"
        )
    funcignore = ws.read(".funcignore")
    if r.require(funcignore is not None, "`.funcignore` exists", "Try `scaffold`."):
        patterns = {ln.strip().rstrip("/") for ln in (funcignore or "").splitlines() if ln.strip()}
        for needed in (".venv", "tests", "local.settings.json"):
            r.require(needed in patterns, f"`.funcignore` excludes `{needed}`")
    imp = ws.probe("import function_app")
    r.probe(imp, "`function_app.py` imports cleanly (as the Functions host will import it)")
    run_pytest(ws, r, "tests", "the whole test suite passes")
    if ws.venv_python():
        lint = ws.run([ws.python(), "-m", "ruff", "check", "."])
        r.require(lint.ok, "`ruff check .` is clean", lint.tail(15))
    if ws.is_git_repo():
        remote = ws.git("remote", "-v")
        r.suggest(remote.ok and "origin" in remote.stdout, "pushed to GitHub")
