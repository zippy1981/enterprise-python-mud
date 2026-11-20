# rules.py: the game's settings. Names in CAPITALS are settings that never change
# while the game runs, so they're easy to find and tweak in one place.

MAX_HEALTH = 100  # health can never go higher than this
MAX_ENERGY = 100  # nor can energy (a different idea, so a different name)
TIRED_BELOW = 20  # critters with less energy than this are tired
REST_PER_HOUR = 10  # energy gained for each hour of sleep
