"""The world's YAML content is valid and internally consistent."""

import pytest

from azurath.checks import REGISTRY, _load_all
from azurath.content import load_world, room_file

WORLD = load_world()
ROOMS = WORLD.ordered()


def test_every_room_has_a_quest_with_a_registered_check() -> None:
    _load_all()
    for room in ROOMS:
        assert room.quest is not None, room.id
        assert room.quest.check in REGISTRY, f"{room.id}: unknown check {room.quest.check}"


def test_room_orders_are_unique_and_start_at_the_gatehouse() -> None:
    orders = [r.order for r in ROOMS]
    assert len(orders) == len(set(orders))
    assert ROOMS[0].id == WORLD.start == "gatehouse"


@pytest.mark.parametrize("room", ROOMS, ids=lambda r: r.id)
def test_room_files_exist(room) -> None:
    quest = room.quest
    for kind, mapping in (("scaffold", quest.scaffold), ("solution", quest.solution.files)):
        for target, source in mapping.items():
            assert room_file(room.id, kind, source).is_file(), (
                f"{room.id} {kind}: {source} for {target}"
            )


@pytest.mark.parametrize("room", ROOMS, ids=lambda r: r.id)
def test_room_teaches_something(room) -> None:
    assert len(room.pages) >= 3, "every room needs a real lesson"
    assert room.npc and room.npc.topics, "every room needs a mentor with topics"
    assert room.quest.hints, "every quest needs hints"
    assert room.quest.reward.item, "every quest rewards a cheat-sheet item"


def test_every_room_is_reachable_from_the_start() -> None:
    seen, frontier = set(), [WORLD.start]
    while frontier:
        room = WORLD.rooms[frontier.pop()]
        if room.id in seen:
            continue
        seen.add(room.id)
        frontier.extend(room.exits.values())
    assert seen == set(WORLD.rooms)


def test_exits_are_two_way() -> None:
    for room in ROOMS:
        for target in room.exits.values():
            assert room.id in WORLD.rooms[target].exits.values(), (
                f"{target} has no way back to {room.id}"
            )


def test_main_path_reaches_the_throne_without_side_quests() -> None:
    """The Go rooms are optional: the finale must be reachable without them."""
    main = {r.id for r in ROOMS if not r.optional}
    seen, frontier = set(), [WORLD.start]
    while frontier:
        room_id = frontier.pop()
        if room_id in seen or room_id not in main:
            continue
        seen.add(room_id)
        frontier.extend(WORLD.rooms[room_id].exits.values())
    assert "throne_room" in seen


def test_item_names_are_unique() -> None:
    names = [r.quest.reward.item.name for r in ROOMS]
    assert len(names) == len(set(names))
