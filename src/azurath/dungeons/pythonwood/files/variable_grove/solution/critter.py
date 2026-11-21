# critter.py: everything we know about my critter, stored in variables.

critter_name = "Sparky"
species = "lightning squirrel"
health = 30
speed = 7
is_sleepy = False

print(f"{critter_name} the {species} has {health} health!")

# Bonk! The same f-string now shows the new health, because {health}
# means "whatever is in the health jar right now".
health -= 5
print(f"{critter_name} the {species} has {health} health!")
