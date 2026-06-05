import pytest

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement
from announcements.services import detect_after_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Grupos", short="GRP", order=1)


@pytest.fixture
def final_round(db):
    return RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)


@pytest.mark.django_db
def test_sede_announcement_created_after_final(groups_round, final_round):
    # Top 3 global: 3 jugadores de vigo. Ganador de madrid: m_a.
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=g_m, earned=5)
    PredictionFactory(player=v2, match=g_m, earned=4)
    PredictionFactory(player=v3, match=g_m, earned=3)
    PredictionFactory(player=m_a, match=g_m, earned=1)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=final_match, earned=20)
    created = detect_after_match(final_match)
    kinds = [a.scope_kind for a in created]
    assert "global" in kinds
    assert "sede" in kinds
    ann = WinnerAnnouncement.objects.get(scope_kind="sede")
    assert ann.points == 0
    assert ann.tied is False
    assert m_a in ann.winners.all()


@pytest.mark.django_db
def test_sede_announcement_idempotent(groups_round, final_round):
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=g_m, earned=5)
    PredictionFactory(player=v2, match=g_m, earned=4)
    PredictionFactory(player=v3, match=g_m, earned=3)
    PredictionFactory(player=m_a, match=g_m, earned=1)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=final_match, earned=20)
    detect_after_match(final_match)
    detect_after_match(final_match)  # segunda llamada
    assert WinnerAnnouncement.objects.filter(scope_kind="sede").count() == 1


@pytest.mark.django_db
def test_sede_announcement_not_created_when_all_desierto(groups_round, final_round):
    # Solo 1 jugador con pts → está en top 3 global → todas las sedes desiertas
    a = UserFactory(name="A", sede="madrid")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=a, match=g_m, earned=3)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=a, match=final_match, earned=20)
    detect_after_match(final_match)
    assert not WinnerAnnouncement.objects.filter(scope_kind="sede").exists()


@pytest.mark.django_db
def test_sede_announcement_winners_m2m_union(groups_round, final_round):
    # Dos sedes resueltas con un ganador distinto cada una
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    b_a = UserFactory(name="BA", sede="barcelona")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=g_m, earned=5)
    PredictionFactory(player=v2, match=g_m, earned=4)
    PredictionFactory(player=v3, match=g_m, earned=3)
    PredictionFactory(player=m_a, match=g_m, earned=2)
    PredictionFactory(player=b_a, match=g_m, earned=1)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=final_match, earned=20)
    detect_after_match(final_match)
    ann = WinnerAnnouncement.objects.get(scope_kind="sede")
    assert {u.id for u in ann.winners.all()} == {m_a.id, b_a.id}
