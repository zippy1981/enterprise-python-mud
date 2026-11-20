# Tests for critters/battle.py. Tests first: red, then green!
from critters.battle import attack, winner

SPARKY = {"name": "Sparky", "health": 30, "power": 12}
MOSSY = {"name": "Mossy", "health": 40, "power": 7}


def test_attack_takes_away_power():
    assert attack(SPARKY, MOSSY) == 28


def test_attack_never_goes_below_zero():
    weakling = {"name": "Twig", "health": 5, "power": 1}
    assert attack(SPARKY, weakling) == 0


def test_sparky_beats_mossy():
    assert winner(SPARKY, MOSSY) == "Sparky"


def test_going_first_wins_between_twins():
    ash = {"name": "Ash", "health": 10, "power": 5}
    birch = {"name": "Birch", "health": 10, "power": 5}
    assert winner(ash, birch) == "Ash"
    assert winner(birch, ash) == "Birch"


def test_no_power_means_a_draw():
    sleepy = {"name": "Snooze", "health": 10, "power": 0}
    dozy = {"name": "Doze", "health": 10, "power": 0}
    assert winner(sleepy, dozy) == "draw"


def test_battles_dont_change_the_critters():
    winner(SPARKY, MOSSY)
    assert SPARKY["health"] == 30
    assert MOSSY["health"] == 40
