"""Helpers for checks that read a player's pyproject.toml."""

from __future__ import annotations

import re
import tomllib
from typing import Any

from azurath.checks import Report
from azurath.workspace import Workspace

_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_names(reqs: list[Any]) -> set[str]:
    names = set()
    for req in reqs:
        if isinstance(req, str) and (m := _NAME.match(req)):
            names.add(normalize(m.group(1)))
    return names


def load_pyproject(ws: Workspace, r: Report | None = None) -> dict[str, Any] | None:
    text = ws.read("pyproject.toml")
    if text is None:
        if r:
            r.require(False, "`pyproject.toml` exists", "Create it first (see the quest brief).")
        return None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        if r:
            r.require(False, "`pyproject.toml` is valid TOML", str(exc))
        return None
    if r:
        r.require(True, "`pyproject.toml` is valid TOML")
    return data


def runtime_deps(pyproject: dict[str, Any]) -> set[str]:
    return requirement_names(pyproject.get("project", {}).get("dependencies", []) or [])


def dev_deps(pyproject: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    groups = pyproject.get("dependency-groups", {}) or {}
    for name in ("dev", "test", "lint"):
        found |= requirement_names(groups.get(name, []) or [])
    found |= requirement_names(
        pyproject.get("tool", {}).get("uv", {}).get("dev-dependencies", []) or []
    )
    found |= requirement_names(
        pyproject.get("project", {}).get("optional-dependencies", {}).get("dev", []) or []
    )
    return found
