# practice/training_ring.py: practise while loops and main().
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).


def rounds_to_win(health, power):
    """Count how many hits of `power` it takes to bring `health` down to 0."""
    rounds = 0
    # STEP 1: Which line keeps looping WHILE there's health left?
    # if health > 0:
    # while health > 0
    while health > 0:
    # STEP 2: Uncomment BOTH of these lines too. They're the loop's body.
        health = health - power
        rounds = rounds + 1
    return rounds


def main():
    """Run a little training fight."""
    print(f"It takes {rounds_to_win(10, 3)} hits to win.")


# STEP 3: Which line means "only run main() when this file is run"?
# Uncomment it, AND the indented main() line under it.
# if __name__ = "__main__":
# if name == "main":
if __name__ == "__main__":
    main()
