# practice/acorns.py: practise making variables.
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).

# STEP 1: Make a variable called pet_name that holds the text Pip.
# pet name = "Pip"
# "Pip" = pet_name
pet_name = "Pip"

# STEP 2: Make a variable called age that holds the NUMBER 3 (not the text "3").
# age = "3"
age = 3

# STEP 3: Make a variable called is_hungry that holds True.
# is_hungry = true
# is_hungry = "True"
is_hungry = True

# STEP 4: Print "Pip is 3 years old." with an f-string.
#         Inside the { } goes the variable's NAME, not its value!
# print(f"{Pip} is {3} years old.")
# print("{pet_name} is {age} years old.")
print(f"{pet_name} is {age} years old.")

# STEP 5: Pip has a birthday! Which line makes age one bigger?
# age + 1
age = age + 1

# This line is already done for you. Look: the same f-string now says 4,
# because {age} means "whatever is in the age jar right now".
print(f"{pet_name} is now {age} years old.")
