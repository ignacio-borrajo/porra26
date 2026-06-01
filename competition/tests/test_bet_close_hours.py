from datetime import timedelta

from competition.models import BET_CLOSE_HOURS


def test_bet_close_hours_is_two():
    assert BET_CLOSE_HOURS == 2


def test_bet_close_hours_can_build_timedelta():
    assert timedelta(hours=BET_CLOSE_HOURS) == timedelta(hours=2)
