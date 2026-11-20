"""The quest-processing workflow.

It's a plain generator that takes anything shaped like a
DurableOrchestrationContext, so it can be unit-tested with a fake context and
no Azure in sight. function_app.py delegates to it with `yield from`.
"""

from collections.abc import Generator
from typing import Any


def process_quest(context: Any) -> Generator[Any, Any, dict[str, Any]]:
    quest = context.get_input()
    validated = yield context.call_activity("validate_quest", quest)

    # Fan out: schedule every notification first, then wait for all of them (Task.WhenAll).
    tasks = [
        context.call_activity("notify_guild", {"guild": guild, "quest_id": validated["id"]})
        for guild in validated["guilds"]
    ]
    notified = (yield context.task_all(tasks)) if tasks else []

    reward = yield context.call_activity("award_reward", validated)
    return {"quest_id": validated["id"], "notified": notified, "reward": reward}
