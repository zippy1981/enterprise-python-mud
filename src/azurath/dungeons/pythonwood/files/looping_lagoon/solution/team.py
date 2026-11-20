"""Functions that work on a whole team of critters.

A team is a list of critter dictionaries, like:
    [{"name": "Sparky", "health": 30}, {"name": "Mossy", "health": 80}]
"""


def total_health(team):
    """Add up the health of every critter on the team."""
    total = 0
    for critter in team:
        total = total + critter["health"]
    return total


def strongest(team):
    """Return the name of the critter with the most health ("" for an empty team).

    If two critters are tied, the one that comes first in the team wins.
    """
    best = None
    for critter in team:
        if best is None or critter["health"] > best["health"]:
            best = critter
    if best is None:
        return ""
    return best["name"]


def roll_call(team):
    """Return a list of every critter's name, in order."""
    names = []
    for critter in team:
        names.append(critter["name"])
    return names
