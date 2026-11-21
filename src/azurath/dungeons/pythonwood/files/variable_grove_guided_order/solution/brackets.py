# practice/brackets.py: the Bracket Bridge. Which maths happens first?
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).
#
# Python follows the same order as maths at school:
#   1. ( brackets )   2. ** powers   3. * / // %   4. + -
# Try a STEP in your head first, then check with: python -c "print(2 + 3 * 4)"

# STEP 1: What does Python get for 2 + 3 * 4?
# answer_one = 20
answer_one = 14

# STEP 2: Bramble wants (2 + 3) times 4, which is 20. Which line gives 20?
# answer_two = 2 + 3 * 4
answer_two = (2 + 3) * 4

# STEP 3: The average of 8 and 4 is 6. Which line works it out?
# average = 8 + 4 / 2
average = (8 + 4) / 2

# STEP 4: What does Python get for 2 ** 3 * 2? (Powers go before times.)
# answer_four = 64
answer_four = 16

# STEP 5: 3 snacks at 2 coins each, plus 1 coin for delivery, costs 7 coins.
# total = 3 * (2 + 1)
total = 3 * 2 + 1

print(answer_one, answer_two, average, answer_four, total)
