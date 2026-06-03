from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from competition.models import BetsClosingReport
from competition.tests.factories import MatchFactory


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox = []
    yield
    mail.outbox = []


@pytest.mark.django_db
def test_command_sends_for_each_pending_match():
    now = timezone.now()
    MatchFactory(kickoff=now - timedelta(minutes=30))
    MatchFactory(kickoff=now - timedelta(minutes=20))
    MatchFactory(kickoff=now - timedelta(minutes=10))
    call_command("send_pending_closures")
    assert len(mail.outbox) == 3


@pytest.mark.django_db
def test_command_skips_already_sent_matches():
    now = timezone.now()
    m_sent = MatchFactory(kickoff=now - timedelta(minutes=30))
    BetsClosingReport.objects.create(match=m_sent, sent_at=now)
    MatchFactory(kickoff=now - timedelta(minutes=20))
    call_command("send_pending_closures")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_command_skips_open_matches():
    now = timezone.now()
    MatchFactory(kickoff=now + timedelta(hours=6))
    MatchFactory(kickoff=now - timedelta(minutes=10))
    call_command("send_pending_closures")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_command_continues_on_individual_error():
    now = timezone.now()
    MatchFactory(kickoff=now - timedelta(minutes=30))
    m2 = MatchFactory(kickoff=now - timedelta(minutes=20))
    MatchFactory(kickoff=now - timedelta(minutes=10))

    from competition.services.closing_email import send_closure_email as real_send

    def flaky(match):
        if match.id == m2.id:
            raise RuntimeError("boom")
        return real_send(match)

    with patch(
        "competition.management.commands.send_pending_closures.send_closure_email",
        side_effect=flaky,
    ):
        call_command("send_pending_closures")

    # m1 y m3 enviaron, m2 falló → outbox tiene 2.
    assert len(mail.outbox) == 2
    # m2 no debería tener report.sent_at fijado.
    report = BetsClosingReport.objects.filter(match=m2).first()
    assert report is None or report.sent_at is None


@pytest.mark.django_db
def test_command_dry_run_does_not_send():
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    out = StringIO()
    call_command("send_pending_closures", "--dry-run", stdout=out)
    assert len(mail.outbox) == 0
    assert "dry-run" in out.getvalue().lower()


@pytest.mark.django_db
def test_command_match_id_filter():
    now = timezone.now()
    m1 = MatchFactory(kickoff=now - timedelta(minutes=30))
    MatchFactory(kickoff=now - timedelta(minutes=20))
    call_command("send_pending_closures", "--match-id", str(m1.id))
    assert len(mail.outbox) == 1
    # El asunto incluye los nombres de los equipos del match concreto.
    assert m1.home.name in mail.outbox[0].subject
    assert m1.away.name in mail.outbox[0].subject


@pytest.mark.django_db
def test_command_match_id_filter_404_logs_and_continues():
    err = StringIO()
    call_command("send_pending_closures", "--match-id", "999999", stderr=err)
    assert len(mail.outbox) == 0
    assert "999999" in err.getvalue()
