from datetime import timedelta
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import BetsReminderLog
from competition.tests.factories import MatchFactory, TeamFactory


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox = []
    yield
    mail.outbox = []


def _make_match(hours_to_kickoff: float, home="ESP", away="MEX"):
    h = TeamFactory(code=home, name=home)
    a = TeamFactory(code=away, name=away)
    return MatchFactory(home=h, away=a, kickoff=timezone.now() + timedelta(hours=hours_to_kickoff))


@pytest.mark.django_db
def test_command_sends_both_kinds_in_window():
    """Match A solo en T-2h; Match B en T-30min (con T-2h ya enviado previamente)."""
    UserFactory(name="Ana")
    _make_match(hours_to_kickoff=1.5, home="A1", away="A2")
    m_b = _make_match(hours_to_kickoff=0.4, home="B1", away="B2")
    BetsReminderLog.objects.create(
        match=m_b,
        kind=BetsReminderLog.KIND_T_MINUS_2H,
        sent_at=timezone.now() - timedelta(hours=1, minutes=30),
        pending_count=1,
        pending_names=["Ana"],
    )

    call_command("send_match_reminders", stdout=StringIO(), stderr=StringIO())

    assert len(mail.outbox) == 2
    assert BetsReminderLog.objects.filter(kind=BetsReminderLog.KIND_T_MINUS_2H).count() == 2
    assert BetsReminderLog.objects.filter(kind=BetsReminderLog.KIND_T_MINUS_30M).count() == 1


@pytest.mark.django_db
def test_command_continues_on_individual_error(monkeypatch):
    UserFactory(name="Ana")
    m1 = _make_match(hours_to_kickoff=1, home="A1", away="A2")
    _make_match(hours_to_kickoff=1.1, home="B1", away="B2")

    from competition.services import reminder_email as reminder_email_module

    original = reminder_email_module.send_reminder_email

    def flaky(match, kind):
        if match.id == m1.id:
            raise RuntimeError("SMTP roto para este match")
        return original(match, kind)

    monkeypatch.setattr(
        "competition.management.commands.send_match_reminders.send_reminder_email",
        flaky,
    )

    stdout, stderr = StringIO(), StringIO()
    call_command("send_match_reminders", stdout=stdout, stderr=stderr)

    assert len(mail.outbox) == 1
    assert "ERR" in stderr.getvalue()


@pytest.mark.django_db
def test_command_dry_run_does_not_send():
    UserFactory(name="Ana")
    _make_match(hours_to_kickoff=1)

    call_command("send_match_reminders", "--dry-run", stdout=StringIO(), stderr=StringIO())

    assert mail.outbox == []
    assert not BetsReminderLog.objects.exists()


@pytest.mark.django_db
def test_command_match_id_filter():
    UserFactory(name="Ana")
    m1 = _make_match(hours_to_kickoff=1, home="A1", away="A2")
    _make_match(hours_to_kickoff=1, home="B1", away="B2")

    call_command(
        "send_match_reminders",
        "--match-id",
        str(m1.id),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject.endswith(timezone.localtime(m1.kickoff).strftime("%d/%m %H:%M"))


@pytest.mark.django_db
def test_command_kind_filter():
    """Con --kind T_MINUS_30M solo se procesa esa ventana."""
    UserFactory(name="Ana")
    _make_match(hours_to_kickoff=1.5, home="A1", away="A2")  # solo T-2h
    _make_match(hours_to_kickoff=0.4, home="B1", away="B2")  # T-30min (y también T-2h)

    call_command(
        "send_match_reminders",
        "--kind",
        BetsReminderLog.KIND_T_MINUS_30M,
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert len(mail.outbox) == 1
    assert BetsReminderLog.objects.filter(kind=BetsReminderLog.KIND_T_MINUS_2H).count() == 0
    assert BetsReminderLog.objects.filter(kind=BetsReminderLog.KIND_T_MINUS_30M).count() == 1


@pytest.mark.django_db
def test_command_skips_match_outside_window():
    """Match con kickoff lejano (T-2h aún no llegó) no se envía."""
    UserFactory(name="Ana")
    _make_match(hours_to_kickoff=10)

    call_command("send_match_reminders", stdout=StringIO(), stderr=StringIO())
    assert mail.outbox == []


@pytest.mark.django_db
def test_command_idempotent_across_runs():
    """Llamar dos veces seguidas no duplica envíos."""
    UserFactory(name="Ana")
    _make_match(hours_to_kickoff=1)

    call_command("send_match_reminders", stdout=StringIO(), stderr=StringIO())
    call_command("send_match_reminders", stdout=StringIO(), stderr=StringIO())

    assert len(mail.outbox) == 1
