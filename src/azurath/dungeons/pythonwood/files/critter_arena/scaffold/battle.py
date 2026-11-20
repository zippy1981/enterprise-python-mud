"""Battle rules. A critter looks like {"name": "Sparky", "health": 30, "power": 12}."""


def attack(attacker, defender):
    """Return the defender's health after one hit from the attacker (never below 0)."""
    # TODO
    return defender["health"]


def winner(first, second):
    """Run turns (first attacks first) until someone is out. Return the winner's name.

    If neither critter has any power, nobody can win: return "draw".
    """
    # TODO: plan it in words first! Then use a while loop.
    return "draw"
