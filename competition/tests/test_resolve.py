import pytest

from accounts.tests.factories import GestorFactory, UserFactory
from competition.services.resolve import resolve_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_resolve_match_persists_result_and_earned():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    p_exact = PredictionFactory(match=m, home=2, away=1, player=UserFactory())
    p_signo = PredictionFactory(match=m, home=3, away=1, player=UserFactory())
    p_fail = PredictionFactory(match=m, home=0, away=1, player=UserFactory())
    actor = GestorFactory()

    resolve_match(m, home=2, away=1, actor=actor)

    m.refresh_from_db()
    assert (m.result_home, m.result_away) == (2, 1)
    assert m.finished_at is not None

    p_exact.refresh_from_db()
    assert p_exact.earned == 3
    p_signo.refresh_from_db()
    assert p_signo.earned == 1
    p_fail.refresh_from_db()
    assert p_fail.earned == 0


@pytest.mark.django_db
def test_resolve_match_creates_audit_log():
    from accounts.models import AuditLog

    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    g = GestorFactory()
    resolve_match(m, home=1, away=0, actor=g)
    log = AuditLog.objects.get(action="match_resolved")
    assert log.actor_id == g.id
    assert log.target_id == str(m.id)
