# actions.py: the things my critter can do.
# Every function RETURNS its answer. No print() in here!


def feed(health, snack):
    return min(health + snack, 100)


def describe(name, health):
    return f"{name} has {health} health."


def is_tired(energy):
    return energy < 20


def is_full(health):
    return health >= 100


def rest(energy, hours):
    return min(energy + hours * 10, 100)
