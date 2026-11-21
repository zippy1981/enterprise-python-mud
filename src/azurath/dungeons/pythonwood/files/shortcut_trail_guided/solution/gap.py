# practice/gap.py: practise the shortcut for True and False answers.
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).
#
# A comparison like  energy < 20  is ALREADY True or False. So instead of
# the long way:
#
#     if energy < 20:
#         return True
#     else:
#         return False
#
# you can take the shortcut and hand back the comparison itself:
#
#     return energy < 20

is_raining = True


# STEP 1: is_big(number) should be True when the number is MORE than 10.
#         Pick the shortcut.
def is_big(number):
    # return True
    # return "number > 10"
    return number > 10
    pass


# STEP 2: is_empty(acorns) should be True when there are NO acorns at all.
#         Remember: one = stores, two == asks.
def is_empty(acorns):
    # return acorns = 0
    # if acorns == 0: return True
    return acorns == 0
    pass


# STEP 3: needs_umbrella should be True when it's raining.
#         is_raining is ALREADY True or False. You don't need to ask "== True"!
needs_umbrella = False
# needs_umbrella = is_raining == True
# needs_umbrella = "is_raining"
needs_umbrella = is_raining


# STEP 4: is_dry should be the OPPOSITE of is_raining.
#         The word  not  flips True to False, and False to True.
is_dry = True
# is_dry = is_raining == False
is_dry = not is_raining
# is_dry = is_raining


print(is_big(11), is_big(10), is_empty(0), is_empty(3))
if needs_umbrella:
    print("Take an umbrella!")
if is_dry:
    print("No puddles today!")
