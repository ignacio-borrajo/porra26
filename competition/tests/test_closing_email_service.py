from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import BetsClosingReport
from competition.services.closing_email import send_closure_email
from competition.tests.factories import MatchFactory, PredictionFactory, TeamFactory


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox = []
    yield
    mail.outbox = []


@pytest.mark.django_db
def test_send_creates_email_with_pdf_attachment():
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(home=home, away=away, kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert len(msg.attachments) == 1
    name, content, mime = msg.attachments[0]
    assert name == f"cierre-{match.teams_slug}.pdf"
    assert mime == "application/pdf"
    assert content.startswith(b"%PDF-")


@pytest.mark.django_db
def test_send_subject_uses_team_names_and_kickoff():
    """El asunto debe ser human-friendly para Outlook y Teams.

    Formato: "[Porra26] España vs Argentina · 15/06 18:00"
    """
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(home=home, away=away, kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    msg = mail.outbox[0]
    assert msg.subject.startswith("[Porra26] ")
    assert "España vs Argentina" in msg.subject
    assert " · " in msg.subject
    # El slug ya no debe aparecer en el asunto (era difícil de leer).
    assert match.teams_slug not in msg.subject


@pytest.mark.django_db
def test_send_body_includes_summary():
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(home=home, away=away, kickoff=timezone.now() - timedelta(minutes=30))
    from accounts.tests.factories import UserFactory

    p = UserFactory(is_jugador=True, is_active=True)
    UserFactory(is_jugador=True, is_active=True)
    PredictionFactory(match=match, player=p, home=2, away=1)
    send_closure_email(match)
    body = mail.outbox[0].body
    assert "España" in body
    assert "Argentina" in body
    assert "1 de 2" in body


@pytest.mark.django_db
def test_send_marks_report_and_creates_audit():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    report = BetsClosingReport.objects.get(match=match)
    assert report.sent_at is not None
    assert report.attempts == 1
    assert len(report.last_sha256) == 64
    audits = AuditLog.objects.filter(action="bets_pdf_emailed")
    assert audits.count() == 1
    assert audits.first().target_id == str(match.id)


@pytest.mark.django_db
def test_send_is_idempotent():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    send_closure_email(match)
    assert len(mail.outbox) == 1
    assert AuditLog.objects.filter(action="bets_pdf_emailed").count() == 1
    assert BetsClosingReport.objects.get(match=match).attempts == 1


@pytest.mark.django_db
def test_send_raises_if_match_not_closed():
    match = MatchFactory(kickoff=timezone.now() + timedelta(hours=4))
    with pytest.raises(ValueError, match="cerrado"):
        send_closure_email(match)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_increments_attempts_even_on_smtp_failure():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    with patch(
        "competition.services.closing_email.EmailMessage.send",
        side_effect=OSError("SMTP boom"),
    ):
        with pytest.raises(OSError):
            send_closure_email(match)
    report = BetsClosingReport.objects.get(match=match)
    assert report.sent_at is None
    assert report.attempts == 1
    assert AuditLog.objects.filter(action="bets_pdf_emailed").count() == 0


@pytest.mark.django_db
@override_settings(TEAMS_DESTINATION_EMAIL="custom@example.com")
def test_send_uses_setting_for_destination():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    msg = mail.outbox[0]
    assert msg.to == ["custom@example.com"]
