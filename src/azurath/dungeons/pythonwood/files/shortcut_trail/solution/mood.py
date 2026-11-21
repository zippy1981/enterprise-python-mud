# mood.py: how is my critter feeling?
# Try changing these two numbers and running the file again!
health = 45
is_sleepy = False

if is_sleepy:
    print("Zzz...")
elif health < 20:
    print("Ouch! I need a snack.")
elif health < 70:
    print("I'm doing OK.")
else:
    print("I feel GREAT!")

print("Mood check done!")
