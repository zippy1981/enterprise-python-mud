# actions.py: the things my critter can do.
# Every function RETURNS its answer. No print() in here!


def feed(health, snack):
    return min(health + snack, 100)


def describe(name, health):
    return f"{name} has {health} health."


def is_tired(energy):
    if energy < 20:
        return True
    else:
        return False
