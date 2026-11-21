# practice/fork.py: practise making decisions with if.
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).
#
# WATCH THE SPACES at the start of each line. The lines INSIDE an if are
# pushed in by exactly 4 spaces. That's how Python knows they belong to it.

acorns = 12
weather = "rainy"


# STEP 1: print "Lots of acorns!" when there are MORE than 10 acorns.
#         Count the spaces in front of each choice. The right one has 4.
if acorns > 10:
# print("Lots of acorns!")
#   print("Lots of acorns!")
    print("Lots of acorns!")
    pass


# STEP 2: when it's sunny, print "Picnic time!".
#         Then, rain OR shine, print "Off we go!".
#         Should "Off we go!" be INSIDE the if (pushed in) or AFTER it (not pushed in)?
if weather == "sunny":
    print("Picnic time!")
print("Off we go!")
#     print("Off we go!")


# STEP 3: is_dozen should be True when there are EXACTLY 12 acorns.
#         One = puts a value in a jar. Two == ASKS "are these equal?"
is_dozen = False
# is_dozen = acorns = 12
is_dozen = acorns == 12
# is_dozen = "acorns == 12"
if is_dozen:
    print("A dozen acorns!")


# STEP 4: below 20 energy the squirrel is "sleepy", below 60 she's "busy",
#         and anything else is "bouncy". Python checks from the TOP and stops
#         at the first one that's True. Finish the elif.
energy = 45
mood = "unknown"
if energy < 20:
    mood = "sleepy"
elif energy < 60:
    # mood == "busy"
    # mood = busy
    mood = "busy"
    pass
else:
    mood = "bouncy"
print(f"The squirrel is {mood}.")
