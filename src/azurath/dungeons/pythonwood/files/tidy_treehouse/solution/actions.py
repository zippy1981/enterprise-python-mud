"""The things my critter can do. Every function returns its answer."""

from critters.rules import MAX_ENERGY, MAX_HEALTH, REST_PER_HOUR, TIRED_BELOW


def feed(health, snack):
    """Give the critter a snack. Health never goes above MAX_HEALTH."""
    return min(health + snack, MAX_HEALTH)


def describe(name, health):
    """Return a sentence like "Sparky has 7 health."."""
    return f"{name} has {health} health."


def is_tired(energy):
    """Return True if the critter has less than TIRED_BELOW energy."""
    return energy < TIRED_BELOW


def is_full(health):
    """Return True if the critter's health is already at MAX_HEALTH."""
    return health >= MAX_HEALTH


def rest(energy, hours):
    """Sleep for some hours, gaining REST_PER_HOUR energy each hour, up to MAX_ENERGY."""
    return min(energy + hours * REST_PER_HOUR, MAX_ENERGY)
