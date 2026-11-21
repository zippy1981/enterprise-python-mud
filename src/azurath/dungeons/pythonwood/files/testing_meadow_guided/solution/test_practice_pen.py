# practice/test_practice_pen.py: practise red, green, tidy!
# Each STEP below has some choices. Only ONE is right.
# Uncomment the right one: delete the "# " (the hash AND the space) at the
# start of its line. Tip: click the line and press Ctrl+/ (Cmd+/ on a Mac).
#
# To uncomment several lines at once, select them all, then press Ctrl+/.


def add_berries(basket, picked):
    """Put the berries you picked into the basket."""
    # STEP 2 (GREEN): Which line makes the tests pass?
    # return basket - picked
    # print(basket + picked)
    return basket + picked
    return 0


# STEP 1 (RED): Uncomment the RIGHT test (both of its lines). 2 plus 3 is...?
# Then type `pytest practice`. It goes RED, because add_berries isn't done
# yet. That's what's supposed to happen! Now go and do STEP 2.
# def test_add_berries():
#     assert add_berries(2, 3) == 6

def test_add_berries():
    assert add_berries(2, 3) == 5


# STEP 3: An edge case: picking 0 berries. Uncomment the right test.
# def test_picking_no_berries():
#     assert add_berries(4, 0) == 0

def test_picking_no_berries():
    assert add_berries(4, 0) == 4
