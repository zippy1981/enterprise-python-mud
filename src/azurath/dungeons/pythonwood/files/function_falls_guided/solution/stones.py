# practice/stones.py: practise writing functions.
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).
#
# Everything INSIDE a function is pushed in by exactly 4 spaces. Count them!


# STEP 1: double(number) should RETURN the number times 2 (not print it!).
def double(number):
    # print(number * 2)
    # return number + 2
    return number * 2
    pass


# STEP 2: greet(name) should return "Hi, " then the name, then "!".
def greet(name):
    # return "Hi, {name}!"
    return f"Hi, {name}!"
    # return f"Hi, {Name}!"
    pass


# STEP 3: is_big(number) should return True when the number is MORE than 10.
def is_big(number):
    # return number >= 10
    # return "number > 10"
    return number > 10
    pass


# STEP 4: bonus(level) is (level + 1) times 10, so bonus(2) is 30.
#         Remember the Bracket Bridge: which part must happen first?
def bonus(level):
    # return level + 1 * 10
    return (level + 1) * 10
    pass


# STEP 5: shout(word) should return the word in CAPITALS, so shout("hi") is "HI".
#         The line inside a function is pushed in by EXACTLY 4 spaces.
#         Look carefully: how far is each choice pushed in?
def shout(word):
# return word.upper()
#   return word.upper()
    return word.upper()
#         return word.upper()
    pass


# STEP 6: Call double with 21 and keep the answer in a variable.
# answer = double
# double(21) = answer
answer = double(21)

print(answer)
