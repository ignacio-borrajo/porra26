import pytest

from accounts.tests.factories import GestorFactory, UserFactory
from competition.services.resolve import clear_match_result, resolve_match
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


@pytest.mark.django_db
def test_clear_match_result_resets_match_and_predictions():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    p_exact = PredictionFactory(match=m, home=2, away=1, player=UserFactory())
    p_fail = PredictionFactory(match=m, home=0, away=1, player=UserFactory())
    actor = GestorFactory()
    resolve_match(m, home=2, away=1, actor=actor)
    m.refresh_from_db()
    assert m.has_result

    clear_match_result(m, actor=actor)

    m.refresh_from_db()
    assert m.result_home is None
    assert m.result_away is None
    assert m.finished_at is None
    assert m.exact_points_applied is None
    assert m.partial_points_applied is None
    p_exact.refresh_from_db()
    p_fail.refresh_from_db()
    assert p_exact.earned is None
    assert p_fail.earned is None


@pytest.mark.django_db
def test_clear_match_result_creates_audit_log():
    from accounts.models import AuditLog

    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    g = GestorFactory()
    resolve_match(m, home=2, away=1, actor=g)

    clear_match_result(m, actor=g)

    log = AuditLog.objects.get(action="match_result_cleared")
    assert log.actor_id == g.id
    assert log.target_id == str(m.id)
    assert log.payload == {"home": 2, "away": 1}


@pytest.mark.django_db
def test_clear_match_result_preserves_closing_report_and_reminders():
    """El registro de envío del email de cierre (PDF) y los recordatorios
    quedan intactos al borrar un resultado: el email ya se envió."""
    from django.utils import timezone

    from competition.models import BetsClosingReport, BetsReminderLog

    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    actor = GestorFactory()
    resolve_match(m, home=1, away=0, actor=actor)

    sent_at = timezone.now()
    BetsClosingReport.objects.create(
        match=m,
        generated_at=sent_at,
        sent_at=sent_at,
        attempts=1,
        last_sha256="abc123",
    )
    BetsReminderLog.objects.create(
        match=m,
        kind=BetsReminderLog.KIND_T_MINUS_2H,
        sent_at=sent_at,
        pending_count=2,
        pending_names=["Alice", "Bob"],
    )

    clear_match_result(m, actor=actor)

    report = BetsClosingReport.objects.get(match=m)
    assert report.sent_at == sent_at
    assert report.attempts == 1
    assert report.last_sha256 == "abc123"
    assert BetsReminderLog.objects.filter(match=m).count() == 1


@pytest.mark.django_db
def test_clear_match_result_removes_winner_announcement():
    """Si al resolver el último partido de la jornada se creó un anuncio de
    ganador, borrar ese resultado debe eliminar el anuncio (la jornada vuelve
    a estar incompleta)."""
    from announcements.models import WinnerAnnouncement

    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    user = UserFactory(name="Ganadora")
    m1 = MatchFactory(round=groups, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups, matchday=1)
    PredictionFactory(player=user, match=m1, earned=3)
    PredictionFactory(player=user, match=m2, home=2, away=2)
    actor = GestorFactory()
    resolve_match(m2, home=2, away=2, actor=actor)
    assert WinnerAnnouncement.objects.filter(scope_kind="matchday", scope_matchday=1).exists()

    clear_match_result(m2, actor=actor)

    assert not WinnerAnnouncement.objects.filter(scope_kind="matchday", scope_matchday=1).exists()


@pytest.mark.django_db
def test_clear_match_result_keeps_unrelated_announcement():
    """Borrar el resultado de un partido de la jornada 2 no debe afectar al
    anuncio de la jornada 1 (cuyos partidos siguen resueltos)."""
    from announcements.models import WinnerAnnouncement

    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    user = UserFactory(name="Ganadora")
    m_md1 = MatchFactory(round=groups, matchday=1)
    PredictionFactory(player=user, match=m_md1, home=1, away=0)
    actor = GestorFactory()
    resolve_match(m_md1, home=1, away=0, actor=actor)
    assert WinnerAnnouncement.objects.filter(scope_kind="matchday", scope_matchday=1).exists()

    m_md2 = MatchFactory(round=groups, matchday=2)
    PredictionFactory(player=user, match=m_md2, home=2, away=0)
    resolve_match(m_md2, home=2, away=0, actor=actor)

    clear_match_result(m_md2, actor=actor)

    assert WinnerAnnouncement.objects.filter(scope_kind="matchday", scope_matchday=1).exists()


@pytest.mark.django_db
def test_clear_r32_match_removes_r32_announcement():
    """Borrar el resultado de un partido de R32 elimina el anuncio de la
    jornada de dieciseisavos (el scope vuelve a estar incompleto)."""
    from announcements.models import WinnerAnnouncement

    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    user = UserFactory(name="Ganadora")
    m1 = MatchFactory(round=r32, matchday=None, result_home=1, result_away=0)
    m2 = MatchFactory(round=r32, matchday=None)
    PredictionFactory(player=user, match=m1, earned=5)
    PredictionFactory(player=user, match=m2, home=2, away=0)
    actor = GestorFactory()
    resolve_match(m2, home=2, away=0, actor=actor)
    assert WinnerAnnouncement.objects.filter(scope_kind="r32").exists()

    clear_match_result(m2, actor=actor)

    assert not WinnerAnnouncement.objects.filter(scope_kind="r32").exists()


@pytest.mark.django_db
def test_clear_finals_match_removes_finals_announcement():
    """Borrar el resultado de un partido de la jornada Fases Finales (p. ej.
    octavos) elimina el anuncio de esa jornada."""
    from announcements.models import WinnerAnnouncement

    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    final = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory(name="Ganadora")
    m_r16 = MatchFactory(round=r16, matchday=None, result_home=1, result_away=0)
    m_final = MatchFactory(round=final, matchday=None)
    PredictionFactory(player=user, match=m_r16, earned=7)
    PredictionFactory(player=user, match=m_final, home=2, away=1)
    actor = GestorFactory()
    resolve_match(m_final, home=2, away=1, actor=actor)
    assert WinnerAnnouncement.objects.filter(scope_kind="finals").exists()

    clear_match_result(m_r16, actor=actor)

    assert not WinnerAnnouncement.objects.filter(scope_kind="finals").exists()


@pytest.mark.django_db
def test_clear_final_removes_finals_and_global_announcements():
    """Borrar el resultado de la Final elimina tanto el anuncio de la jornada
    Fases Finales como el de campeón del Mundial (global)."""
    from announcements.models import WinnerAnnouncement

    final = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory(name="Ganadora")
    m_final = MatchFactory(round=final, matchday=None)
    PredictionFactory(player=user, match=m_final, home=2, away=1)
    actor = GestorFactory()
    resolve_match(m_final, home=2, away=1, actor=actor)
    assert WinnerAnnouncement.objects.filter(scope_kind="finals").exists()
    assert WinnerAnnouncement.objects.filter(scope_kind="global").exists()

    clear_match_result(m_final, actor=actor)

    assert not WinnerAnnouncement.objects.filter(scope_kind="finals").exists()
    assert not WinnerAnnouncement.objects.filter(scope_kind="global").exists()
