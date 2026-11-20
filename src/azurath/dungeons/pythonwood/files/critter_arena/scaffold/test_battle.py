# Tests for critters/battle.py. Tests first: red, then green!
from critters.battle import attack, winner

SPARKY = {"name": "Sparky", "health": 30, "power": 12}
MOSSY = {"name": "Mossy", "health": 40, "power": 7}


def test_attack_takes_away_power():
    assert attack(SPARKY, MOSSY) == 28


# TODO: an attack can't take health below 0

# TODO: who wins Sparky vs Mossy?

# TODO: two identical critters: does going first matter?

# TODO: two critters with 0 power is a "draw"
