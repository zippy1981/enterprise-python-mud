# Tests for actions.py. Run them with the game's `pytest` command.
from actions import describe, feed, is_tired


def test_feed_adds_the_snack():
    assert feed(50, 10) == 60


# TODO: a test that feed never goes over 100


# TODO: a test for describe


def test_low_energy_is_tired():
    assert is_tired(10) == True


# TODO: what about exactly 20 energy?


# TODO (part 2): tests for rest() FIRST, then write rest() in actions.py
