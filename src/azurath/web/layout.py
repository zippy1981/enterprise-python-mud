"""Place a dungeon's rooms on a grid for drawing a map, following the exits' directions."""

from __future__ import annotations

from collections import deque

from azurath.content import Dungeon

STEP = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
    "northeast": (1, -1),
    "northwest": (-1, -1),
    "southeast": (1, 1),
    "southwest": (-1, 1),
    "up": (1, -1),
    "down": (-1, 1),
}


def layout(dungeon: Dungeon) -> dict[str, tuple[int, int]]:
    """Grid positions for every room, starting from the start room at (0, 0).

    Rooms are placed breadth-first in curriculum order: each one goes one step from
    the room it was reached from, in the exit's direction. If that spot is taken,
    it moves further along the same direction (then sideways) until it finds a free
    one. The grid is shifted so the smallest x and y are 0. Unreachable rooms go
    in a row underneath.
    """
    positions: dict[str, tuple[int, int]] = {dungeon.start: (0, 0)}
    taken = {(0, 0)}
    queue = deque([dungeon.start])
    while queue:
        here = queue.popleft()
        x, y = positions[here]
        exits = sorted(dungeon.rooms[here].exits.items(), key=lambda kv: dungeon.rooms[kv[1]].order)
        for direction, target in exits:
            if target in positions:
                continue
            dx, dy = STEP.get(direction, (1, 0))
            spot = _free(taken, x, y, dx, dy)
            positions[target] = spot
            taken.add(spot)
            queue.append(target)
    row = max((y for _, y in positions.values()), default=0) + 2
    for i, room in enumerate(r for r in dungeon.ordered() if r.id not in positions):
        positions[room.id] = (i, row)
    min_x = min(x for x, _ in positions.values())
    min_y = min(y for _, y in positions.values())
    return {room: (x - min_x, y - min_y) for room, (x, y) in positions.items()}


def _free(taken: set[tuple[int, int]], x: int, y: int, dx: int, dy: int) -> tuple[int, int]:
    for distance in range(1, 50):
        spot = (x + dx * distance, y + dy * distance)
        if spot not in taken:
            return spot
        for side in (1, -1):  # try sideways from the first blocked spot
            nudged = (spot[0] + side * dy, spot[1] + side * dx)
            if (dx, dy) != (0, 0) and nudged not in taken:
                return nudged
    raise RuntimeError("no free spot on the map")  # pragma: no cover
