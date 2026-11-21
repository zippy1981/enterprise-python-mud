"""The Textual split-screen UI (`azurath tui`)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from azurath import gitcheck  # noqa: E402
from azurath.content import load_dungeon  # noqa: E402
from azurath.settings import AzurathSettings  # noqa: E402
from azurath.tui import AzurathApp  # noqa: E402


def make_app(tmp_path: Path) -> AzurathApp:
    assert gitcheck.set_global_identity("Ada Lovelace", "ada@example.com").ok
    settings = AzurathSettings(workspace=tmp_path / "proj", dungeon="pythonwood")
    return AzurathApp(settings, load_dungeon("pythonwood"))


async def settle(pilot, app: AzurathApp) -> None:
    for _ in range(100):
        await pilot.pause(0.05)
        if not app.busy and not app.workers:
            return


def log_text(app: AzurathApp) -> str:
    log = app.query_one("#log")
    return "\n".join(strip.text for strip in log.lines)


def test_the_tui_starts_and_runs_commands(tmp_path: Path) -> None:
    app = make_app(tmp_path)

    async def play() -> None:
        async with app.run_test(size=(140, 48)) as pilot:
            await settle(pilot, app)
            assert app.session.started
            first_room = load_dungeon("pythonwood").ordered()[0].name
            assert first_room in log_text(app)

            await pilot.click("#command")
            await pilot.press(*"status", "enter")
            await settle(pilot, app)
            assert "› status" in log_text(app)

            await pilot.click("#do-check")  # the Check button
            await settle(pilot, app)
            quest = str(app.query_one("#quest").render())
            assert "✘" in quest  # nothing done yet, so the checklist shows what's left

            exits = list(app.query("#exits Button"))
            assert exits and all(button.disabled for button in exits)  # locked until done

    asyncio.run(play())
