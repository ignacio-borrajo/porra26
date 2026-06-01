import pytest

from accounts.tests.factories import UserFactory
from competition.services.closing_report import compute_closing_stats
from competition.tests.factories import MatchFactory, PredictionFactory


@pytest.mark.django_db
def test_stats_count_active_jugadores_only():
    match = MatchFactory()
    UserFactory(is_jugador=True, is_active=True)
    UserFactory(is_jugador=True, is_active=True)
    UserFactory(is_jugador=False, is_active=True)
    UserFactory(is_jugador=True, is_active=False)
    stats = compute_closing_stats(match)
    assert stats.total_players == 2


@pytest.mark.django_db
def test_stats_count_bets_and_absentees():
    match = MatchFactory()
    p1 = UserFactory(is_jugador=True, is_active=True, name="Ana")
    p2 = UserFactory(is_jugador=True, is_active=True, name="Beto")
    p3 = UserFactory(is_jugador=True, is_active=True, name="Carla")
    PredictionFactory(match=match, player=p1, home=2, away=1)
    PredictionFactory(match=match, player=p2, home=2, away=1)
    stats = compute_closing_stats(match)
    assert stats.total_players == 3
    assert stats.bets_count == 2
    assert stats.absent_names == ["Carla"]


@pytest.mark.django_db
def test_stats_most_popular_score():
    match = MatchFactory()
    for i in range(3):
        PredictionFactory(match=match, player=UserFactory(), home=2, away=1)
    PredictionFactory(match=match, player=UserFactory(), home=1, away=0)
    stats = compute_closing_stats(match)
    assert stats.most_popular == [("2-1", 3)]


@pytest.mark.django_db
def test_stats_most_popular_tie():
    match = MatchFactory()
    PredictionFactory(match=match, player=UserFactory(), home=2, away=1)
    PredictionFactory(match=match, player=UserFactory(), home=1, away=0)
    stats = compute_closing_stats(match)
    # empate a 1 voto cada uno → ambos
    assert len(stats.most_popular) == 2


@pytest.mark.django_db
def test_stats_split_1x2():
    match = MatchFactory()
    # 3 victorias locales, 1 empate, 1 visitante
    for _ in range(3):
        PredictionFactory(match=match, player=UserFactory(), home=2, away=0)
    PredictionFactory(match=match, player=UserFactory(), home=1, away=1)
    PredictionFactory(match=match, player=UserFactory(), home=0, away=2)
    stats = compute_closing_stats(match)
    assert stats.split_home == 3
    assert stats.split_draw == 1
    assert stats.split_away == 1


@pytest.mark.django_db
def test_stats_empty_match():
    match = MatchFactory()
    UserFactory(is_jugador=True, is_active=True)
    stats = compute_closing_stats(match)
    assert stats.bets_count == 0
    assert stats.most_popular == []
    assert stats.split_home == 0 and stats.split_draw == 0 and stats.split_away == 0
