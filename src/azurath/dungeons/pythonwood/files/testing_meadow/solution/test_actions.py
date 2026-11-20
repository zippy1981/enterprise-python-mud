# Tests for actions.py. Run them with the game's `pytest` command.
from actions import describe, feed, is_tired, rest


def test_feed_adds_the_snack():
    assert feed(50, 10) == 60


def test_feed_never_goes_over_100():
    assert feed(95, 10) == 100


def test_describe_says_name_and_health():
    assert describe("Sparky", 7) == "Sparky has 7 health."


def test_low_energy_is_tired():
    assert is_tired(10) == True


def test_exactly_20_energy_is_not_tired():
    assert is_tired(20) == False


def test_rest_adds_10_energy_per_hour():
    assert rest(50, 2) == 70


def test_rest_never_goes_over_100():
    assert rest(95, 1) == 100
