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

    # TODO: fan out one "notify_guild" activity per guild in validated["guilds"],
    #       then yield context.task_all(...) ONCE to wait for them all
    notified: list[Any] = []

    # TODO: yield the "award_reward" activity
    reward = None

    return {"quest_id": validated["id"], "notified": notified, "reward": reward}
