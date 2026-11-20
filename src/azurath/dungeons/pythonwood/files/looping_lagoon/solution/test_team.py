# Tests for critters/team.py. Written FIRST (red), then made to pass (green)!
from critters.team import roll_call, strongest, total_health

TEAM = [
    {"name": "Sparky", "health": 30},
    {"name": "Mossy", "health": 80},
    {"name": "Pebble", "health": 55},
]


def test_total_health_adds_everyone_up():
    assert total_health(TEAM) == 165


def test_empty_team_has_no_health():
    assert total_health([]) == 0


def test_strongest_finds_the_most_health():
    assert strongest(TEAM) == "Mossy"


def test_strongest_tie_goes_to_the_first():
    tied = [{"name": "Ash", "health": 50}, {"name": "Birch", "health": 50}]
    assert strongest(tied) == "Ash"


def test_strongest_of_nobody_is_empty():
    assert strongest([]) == ""


def test_roll_call_lists_names_in_order():
    assert roll_call(TEAM) == ["Sparky", "Mossy", "Pebble"]
