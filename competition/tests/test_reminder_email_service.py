from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import BetsReminderLog
from competition.services.reminder_email import send_reminder_email
from competition.tests.factories import MatchFactory, PredictionFactory, TeamFactory


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox = []
    yield
    mail.outbox = []


def _make_match_open(home_name="España", away_name="México", hours_to_kickoff=1):
    home = TeamFactory(code="ESP", name=home_name)
    away = TeamFactory(code="MEX", name=away_name)
    return MatchFactory(
        home=home,
        away=away,
        kickoff=timezone.now() + timedelta(hours=hours_to_kickoff),
    )


# -------------------------------------------------------------------
# Happy path
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_send_creates_email_when_pending():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    UserFactory(name="Beto")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_send_creates_log_when_pending():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    log = send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert log is not None
    assert log.match == match
    assert log.kind == BetsReminderLog.KIND_T_MINUS_2H
    assert log.sent_at is not None
    assert log.pending_count == 1
    assert log.pending_names == ["Ana"]


# -------------------------------------------------------------------
# No-op cases
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_send_no_email_when_no_pending():
    """Sin jugadores en el universo → no se envía nada."""
    match = _make_match_open()
    result = send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert result is None
    assert mail.outbox == []


@pytest.mark.django_db
def test_send_no_log_when_no_pending():
    match = _make_match_open()
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert not BetsReminderLog.objects.exists()


@pytest.mark.django_db
def test_send_no_email_when_all_have_bet():
    """Si todos los esperados ya apostaron, no se envía."""
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    u = UserFactory(name="Ana")
    PredictionFactory(player=u, match=match)
    result = send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert result is None
    assert mail.outbox == []


# -------------------------------------------------------------------
# Subject
# -------------------------------------------------------------------


@override_settings(TEAMS_REMINDER_SUBJECT_PREFIX="[Porra26 RECORDATORIO]")
@pytest.mark.django_db
def test_send_subject_includes_prefix_and_team_names():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    subj = mail.outbox[0].subject
    assert subj.startswith("[Porra26 RECORDATORIO] ")
    assert "España vs México" in subj


@override_settings(TEAMS_REMINDER_SUBJECT_PREFIX="[Porra26 RECORDATORIO]")
@pytest.mark.django_db
def test_send_subject_includes_kickoff_local_format():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    subj = mail.outbox[0].subject
    assert " · " in subj
    kickoff_local = timezone.localtime(match.kickoff)
    assert kickoff_local.strftime("%d/%m %H:%M") in subj


# -------------------------------------------------------------------
# Body — HTML + plain
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_send_body_plain_lists_pending_names():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana López")
    UserFactory(name="Juan Pérez")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    body = mail.outbox[0].body
    assert "Ana López" in body
    assert "Juan Pérez" in body


@pytest.mark.django_db
def test_send_body_html_lists_pending_names():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana López")
    UserFactory(name="Juan Pérez")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    msg = mail.outbox[0]
    alternatives = getattr(msg, "alternatives", [])
    assert len(alternatives) == 1
    html, mime = alternatives[0]
    assert mime == "text/html"
    assert "Ana López" in html
    assert "Juan Pérez" in html
    assert "<b>" in html


@pytest.mark.django_db
def test_send_body_html_includes_link_to_competicion():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    html = mail.outbox[0].alternatives[0][0]
    assert "laporradeljefe.es/competicion" in html


@pytest.mark.django_db
def test_send_body_mentions_kickoff_time():
    """El body debe nombrar la hora del saque (cierre = kickoff)."""
    from accounts.tests.factories import UserFactory

    match = _make_match_open(hours_to_kickoff=1)
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    kickoff_local = timezone.localtime(match.kickoff)
    kickoff_hhmm = kickoff_local.strftime("%H:%M")
    assert kickoff_hhmm in mail.outbox[0].body


@pytest.mark.django_db
def test_send_body_for_2h_kind_mentions_2_hours_remaining():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert "2 horas" in mail.outbox[0].body


@pytest.mark.django_db
def test_send_body_for_30m_kind_mentions_30_min_remaining():
    from accounts.tests.factories import UserFactory

    match = _make_match_open(hours_to_kickoff=0.4)
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_30M)
    assert "30 min" in mail.outbox[0].body


@pytest.mark.django_db
def test_send_body_for_manual_kind_mentions_remaining_calculated():
    """Manual computa el tiempo restante dinámicamente, no usa los textos AUTO."""
    import re

    from accounts.tests.factories import UserFactory

    match = _make_match_open(hours_to_kickoff=1)
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_MANUAL)
    body = mail.outbox[0].body
    # No usa el texto fijo del T-2h aunque la duración real sea cercana
    assert "2 horas" not in body
    assert re.search(r"\d+\s*(h|min)", body) is not None


# -------------------------------------------------------------------
# Idempotency
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_send_auto_kind_is_idempotent():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    log1 = send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    log2 = send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert log1 is not None
    assert log2 is None
    assert len(mail.outbox) == 1
    assert BetsReminderLog.objects.filter(match=match).count() == 1


@pytest.mark.django_db
def test_send_manual_kind_updates_existing_row():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    log1 = send_reminder_email(match, BetsReminderLog.KIND_MANUAL)
    UserFactory(name="Beto")
    log2 = send_reminder_email(match, BetsReminderLog.KIND_MANUAL)
    assert log1 is not None and log2 is not None
    assert log1.pk == log2.pk
    assert log2.pending_count == 2
    assert BetsReminderLog.objects.filter(match=match).count() == 1
    assert len(mail.outbox) == 2


# -------------------------------------------------------------------
# Closure boundary
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_send_raises_value_error_after_kickoff():
    """kickoff ≤ now → ValueError."""
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="MEX", name="México")
    match = MatchFactory(home=home, away=away, kickoff=timezone.now() - timedelta(minutes=5))
    with pytest.raises(ValueError):
        send_reminder_email(match, BetsReminderLog.KIND_MANUAL)


# -------------------------------------------------------------------
# AuditLog
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_send_creates_audit_log():
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    UserFactory(name="Ana")
    send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    entry = AuditLog.objects.get(action="bets_reminder_sent")
    assert entry.target_type == "match"
    assert entry.target_id == str(match.id)
    assert entry.payload["kind"] == BetsReminderLog.KIND_T_MINUS_2H
    assert entry.payload["pending_count"] == 1


# -------------------------------------------------------------------
# Truncation
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_send_truncates_names_above_30_in_body():
    """Más de 30 rezagados → body trunca a 30 + 'y N más'."""
    from accounts.tests.factories import UserFactory

    match = _make_match_open()
    for i in range(35):
        UserFactory(name=f"Player {i:02d}")
    log = send_reminder_email(match, BetsReminderLog.KIND_T_MINUS_2H)
    assert log.pending_count == 35
    body = mail.outbox[0].body
    assert "5 más" in body or "5 mas" in body
