"""Battle rules. A critter looks like {"name": "Sparky", "health": 30, "power": 12}."""


def hit(health, power):
    """Take power away from health, but never go below 0."""
    return max(health - power, 0)


def attack(attacker, defender):
    """Return the defender's health after one hit from the attacker (never below 0)."""
    return hit(defender["health"], attacker["power"])


def winner(first, second):
    """Run turns (first attacks first) until someone is out. Return the winner's name.

    If neither critter has any power, nobody can win: return "draw".
    """
    if first["power"] == 0 and second["power"] == 0:
        return "draw"
    first_health = first["health"]
    second_health = second["health"]
    while first_health > 0 and second_health > 0:
        second_health = hit(second_health, first["power"])
        if second_health == 0:
            return first["name"]
        first_health = hit(first_health, second["power"])
    return second["name"]
