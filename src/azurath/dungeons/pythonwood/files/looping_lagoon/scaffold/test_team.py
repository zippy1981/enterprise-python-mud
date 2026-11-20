# Tests for critters/team.py. Write them FIRST (red), then make them pass (green)!
from critters.team import roll_call, strongest, total_health

TEAM = [
    {"name": "Sparky", "health": 30},
    {"name": "Mossy", "health": 80},
    {"name": "Pebble", "health": 55},
]


def test_total_health_adds_everyone_up():
    assert total_health(TEAM) == 165


# TODO: what's the total health of an empty team []?

# TODO: tests for strongest (who's strongest in TEAM? what about a tie? an empty team?)

# TODO: a test for roll_call
