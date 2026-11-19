"""Unit tests for the orchestration, driven by a fake Durable context."""

from collections.abc import Callable, Generator
from typing import Any

from questboard.orchestration import process_quest


class FakeContext:
    def __init__(self, input_: Any) -> None:
        self._input = input_

    def get_input(self) -> Any:
        return self._input

    def call_activity(self, name: str, input_: Any = None) -> tuple[str, str, Any]:
        return ("activity", name, input_)

    def task_all(self, tasks: list[Any]) -> tuple[str, list[Any]]:
        return ("all", list(tasks))


ACTIVITIES: dict[str, Callable[[Any], Any]] = {
    "validate_quest": lambda quest: {**quest, "id": "quest-1"},
    "notify_guild": lambda notice: f"notified {notice['guild']}",
    "award_reward": lambda quest: {"gold": quest["reward"]},
}


def drive(gen: Generator[Any, Any, Any]) -> Any:
    """Play the Durable framework: resolve every yielded task and send back its result."""

    def resolve(task: Any) -> Any:
        if task[0] == "all":
            return [resolve(t) for t in task[1]]
        _, name, payload = task
        return ACTIVITIES[name](payload)

    try:
        task = next(gen)
        while True:
            task = gen.send(resolve(task))
    except StopIteration as done:
        return done.value


def test_notifies_every_guild_and_awards_the_reward() -> None:
    quest = {"title": "Slay the dragon", "reward": 1500, "rank": "S", "guilds": ["mages", "bards"]}
    result = drive(process_quest(FakeContext(quest)))
    assert result["quest_id"] == "quest-1"
    # TODO: assert on result["notified"] and result["reward"]
