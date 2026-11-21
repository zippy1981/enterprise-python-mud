"""Every dungeon's YAML content is valid and internally consistent."""

import pytest
from pydantic import ValidationError

from azurath.checks import REGISTRY, load_checks
from azurath.content import Atlas, Dungeon, RoomRef, load_atlas

ATLAS = load_atlas()
DUNGEONS = ATLAS.ordered()
ROOMS = [(d, r) for d in DUNGEONS for r in d.ordered()]
# pytest calls `ids` once per parameter value, not per tuple, so give the ids explicitly.
# Otherwise each Dungeon's full repr lands in PYTEST_CURRENT_TEST, past Windows' 32K limit.
ROOM_IDS = [f"{d.id}/{r.id}" for d, r in ROOMS]


def reachable(dungeon: Dungeon, allowed: set[str] | None = None) -> set[str]:
    seen, frontier = set(), [dungeon.start]
    while frontier:
        rid = frontier.pop()
        if rid in seen or (allowed is not None and rid not in allowed):
            continue
        seen.add(rid)
        frontier.extend(dungeon.rooms[rid].exits.values())
    return seen


def test_there_are_several_dungeons_with_unique_workspaces() -> None:
    assert len(DUNGEONS) >= 2
    folders = [d.workspace for d in DUNGEONS]
    assert len(folders) == len(set(folders)), "two dungeons would share a default workspace"


@pytest.mark.parametrize("dungeon", DUNGEONS, ids=lambda d: d.id)
def test_every_quest_has_a_registered_check(dungeon: Dungeon) -> None:
    load_checks(dungeon)
    for room in dungeon.ordered():
        assert room.quest is not None, room.id
        assert (dungeon.id, room.quest.check) in REGISTRY, f"{room.id}: no check {room.quest.check}"


@pytest.mark.parametrize("dungeon", DUNGEONS, ids=lambda d: d.id)
def test_room_orders_are_unique_and_start_first(dungeon: Dungeon) -> None:
    orders = [r.order for r in dungeon.ordered()]
    assert len(orders) == len(set(orders))
    assert dungeon.ordered()[0].id == dungeon.start


@pytest.mark.parametrize("dungeon", DUNGEONS, ids=lambda d: d.id)
def test_every_room_is_reachable_and_exits_are_two_way(dungeon: Dungeon) -> None:
    assert reachable(dungeon) == set(dungeon.rooms)
    for room in dungeon.ordered():
        for target in room.exits.values():
            back = dungeon.rooms[target].exits.values()
            assert room.id in back, f"{target} has no way back to {room.id}"


@pytest.mark.parametrize("dungeon", DUNGEONS, ids=lambda d: d.id)
def test_main_path_reaches_the_end_without_side_quests(dungeon: Dungeon) -> None:
    main = {r.id for r in dungeon.ordered() if not r.optional}
    final = max((r for r in dungeon.ordered() if not r.optional), key=lambda r: r.order)
    assert final.id in reachable(dungeon, main)
    assert final.quest.epilogue, f"{dungeon.id}: the final room should have an epilogue"


@pytest.mark.parametrize("dungeon", DUNGEONS, ids=lambda d: d.id)
def test_item_names_are_unique(dungeon: Dungeon) -> None:
    names = [r.quest.reward.item.name for r in dungeon.ordered() if r.quest.reward.item]
    assert len(names) == len(set(names))


@pytest.mark.parametrize(("dungeon", "room"), ROOMS, ids=ROOM_IDS)
def test_room_files_exist(dungeon: Dungeon, room) -> None:
    quest = room.quest
    for kind, mapping in (("scaffold", quest.scaffold), ("solution", quest.solution.files)):
        for target, source in mapping.items():
            assert dungeon.room_file(room.id, kind, source).is_file(), (
                f"{room.id} {kind}: {source} for {target}"
            )


@pytest.mark.parametrize(("dungeon", "room"), ROOMS, ids=ROOM_IDS)
def test_room_teaches_something(dungeon: Dungeon, room) -> None:
    assert room.npc and room.npc.topics, "every room needs a mentor with topics"
    assert room.quest.hints, "every quest needs hints"
    if room.guided:  # short warm-ups: the lesson's main room teaches in depth
        assert len(room.pages) >= 2, "a guided room needs at least a how-to and a step page"
        return
    assert len(room.pages) >= 3, "every room needs a real lesson"
    assert room.quest.reward.item, "every quest rewards a cheat-sheet item"


def test_ranks_climb() -> None:
    for dungeon in DUNGEONS:
        thresholds = [xp for xp, _ in dungeon.ranks]
        assert thresholds == sorted(thresholds) and thresholds[0] == 0, dungeon.id
        assert dungeon.rank_for(0) == dungeon.ranks[0][1]
        assert dungeon.rank_for(10**9) == dungeon.ranks[-1][1]


# --- groundwork for connecting dungeons later --------------------------------------


def test_room_refs_parse_local_and_qualified_names() -> None:
    assert RoomRef.parse("gatehouse") == RoomRef(None, "gatehouse")
    assert RoomRef.parse("pythonwood:trailhead") == RoomRef("pythonwood", "trailhead")
    assert RoomRef.parse("gatehouse").is_local


def test_cross_dungeon_exits_are_rejected_for_now() -> None:
    enterprise = ATLAS.get("enterprise")
    data = enterprise.model_dump()
    data["rooms"]["gatehouse"]["exits"]["portal"] = "pythonwood:trailhead"
    with pytest.raises(ValidationError, match="cross-dungeon exits aren't supported yet"):
        Dungeon.model_validate(data)


def test_atlas_resolves_local_exits() -> None:
    enterprise = ATLAS.get("enterprise")
    dungeon, room = ATLAS.resolve(enterprise, "hall_of_basics")
    assert dungeon is enterprise and room.id == "hall_of_basics"
    with pytest.raises(KeyError, match="unknown dungeon"):
        Atlas(dungeons={}).get("nope")


def test_every_pythonwood_lesson_has_guided_rooms_first() -> None:
    """Each lesson: one or more guided rooms (uncomment the answer), then its main room."""
    pythonwood = ATLAS.get("pythonwood")
    rooms = pythonwood.ordered()
    assert rooms[0].guided and pythonwood.start == rooms[0].id
    pending: list = []  # guided rooms waiting for their lesson's main room
    for room in rooms:
        if room.guided:
            pending.append(room)
            assert all(t.startswith("practice/") for t in room.quest.scaffold), (
                "guided files live in practice/ so they never complete the main room"
            )
            continue
        assert pending, f"{room.id} has no guided room before it"
        assert all(g.id.startswith(f"{room.id}_guided") for g in pending), [g.id for g in pending]
        chain = [*pending, room]
        for here, there in zip(chain, chain[1:], strict=False):
            assert there.id in here.exits.values() and here.id in there.exits.values()
        pending = []
    assert not pending, "guided rooms at the end with no lesson room after them"


def test_variable_grove_has_a_path_for_each_topic() -> None:
    names = [
        r.name
        for r in ATLAS.get("pythonwood").ordered()
        if r.id.startswith("variable_grove_guided")
    ]
    assert names == [
        "The Acorn Path",
        "The Abacus Hollow",
        "The Word Weaver's Nook",
        "The Bracket Bridge",
        "The Tally Tree",
    ]
