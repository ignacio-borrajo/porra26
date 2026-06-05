import pytest

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement
from competition.services.resolve import resolve_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)


@pytest.fixture
def r16_round(db):
    return RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)


@pytest.fixture
def final_round(db):
    return RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)


@pytest.fixture
def gestor():
    from accounts.tests.factories import GestorFactory

    return GestorFactory()


@pytest.mark.django_db
def test_resolve_last_match_of_matchday_creates_announcement(groups_round, gestor):
    user = UserFactory()
    other = UserFactory()
    m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=1)
    PredictionFactory(player=user, match=m1, earned=3)
    PredictionFactory(player=user, match=m2, home=2, away=2)
    PredictionFactory(player=other, match=m1, earned=0)
    PredictionFactory(player=other, match=m2, home=0, away=0)

    resolve_match(m2, home=2, away=2, actor=gestor)

    anns = WinnerAnnouncement.objects.filter(scope_kind="matchday", scope_matchday=1)
    assert anns.count() == 1
    assert list(anns.first().winners.values_list("id", flat=True)) == [user.id]


@pytest.mark.django_db
def test_resolve_first_match_of_round_creates_no_announcement(r16_round, gestor):
    user = UserFactory()
    MatchFactory(round=r16_round, matchday=None)  # pendiente
    m_done = MatchFactory(round=r16_round, matchday=None)
    PredictionFactory(player=user, match=m_done, home=1, away=0)

    resolve_match(m_done, home=1, away=0, actor=gestor)

    assert WinnerAnnouncement.objects.filter(scope_kind="round").count() == 0


@pytest.mark.django_db
def test_resolve_final_match_creates_only_global_announcement(final_round, gestor):
    """La Final solo crea el anuncio global (no genera scope='round' porque
    el ganador del Mundial cobra por el podio, no como premio de ronda)."""
    user = UserFactory()
    m = MatchFactory(round=final_round, matchday=None)
    PredictionFactory(player=user, match=m, home=2, away=1)

    resolve_match(m, home=2, away=1, actor=gestor)

    kinds = sorted(WinnerAnnouncement.objects.values_list("scope_kind", flat=True))
    assert kinds == ["global"]
    assert WinnerAnnouncement.objects.filter(scope_kind="round").count() == 0
