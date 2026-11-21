# practice/lily_pads.py: practise lists and loops.
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).

# STEP 1: Make a LIST of three snacks.
# snacks = "berry, acorn, seed"
# snacks = [berry, acorn, seed]
snacks = ["berry", "acorn", "seed"]

# STEP 2: Show the FIRST snack, SHOUTED. (Positions start at 0, and remember
#         .upper() from the Word Weaver's Nook!)
# print(snacks.upper())
# print(snacks[1].upper())
print(snacks[0].upper())


def count_letters(words):
    """Add up how many letters there are in all the words."""
    total = 0
    # STEP 3: Uncomment the loop line that visits every word...
    # for words in word:
    for word in words:
    # ...and the line that ADDS this word's letters to the total (the Tally Tree's +=).
    #     total = len(word)
        total += len(word)
    return total


print(count_letters(snacks))
