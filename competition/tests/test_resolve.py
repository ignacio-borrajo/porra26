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


@pytest.mark.django_db
def test_resolve_match_freezes_points_applied():
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    resolve_match(m, home=1, away=0, actor=GestorFactory())
    m.refresh_from_db()
    assert m.exact_points_applied == 3
    assert m.partial_points_applied == 1


@pytest.mark.django_db
def test_resolve_match_does_not_overwrite_existing_snapshots():
    """Si se edita un resultado después de cambiar la puntuación de la ronda,
    los snapshots ya fijados no se reescriben."""
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    actor = GestorFactory()
    resolve_match(m, home=1, away=0, actor=actor)

    groups.points = 10
    groups.partial_points = 5
    groups.save()
    m.refresh_from_db()

    resolve_match(m, home=2, away=0, actor=actor)
    m.refresh_from_db()
    assert m.exact_points_applied == 3
    assert m.partial_points_applied == 1
