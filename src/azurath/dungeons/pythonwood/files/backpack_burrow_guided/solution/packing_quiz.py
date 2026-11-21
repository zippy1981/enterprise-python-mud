# practice/packing_quiz.py: a quiz about packages, backpacks and uv.
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).

# STEP 1: What is a package?
# package = "a box you post to a friend"
package = "code someone else wrote that you can borrow"

# STEP 2: What is the backpack folder (the virtual environment) called?
# backpack_folder = "node_modules"
backpack_folder = ".venv"

# STEP 3: Which command borrows the cowsay package?
add_command = "uv add cowsay"
# add_command = "pip install everything"

# STEP 4: Which command puts pytest in the dev pocket?
# dev_command = "uv add pytest --game"
dev_command = "uv add --dev pytest"

# STEP 5: Which files should git save? (Not the backpack itself!)
# save_in_git = [".venv", "uv.lock"]
save_in_git = ["pyproject.toml", "uv.lock"]

# STEP 6: Which command starts a packing list WITHOUT joining a bigger project?
# init_command = "uv init"
init_command = "uv init --bare --no-workspace"
