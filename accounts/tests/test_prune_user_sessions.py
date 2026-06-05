from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def _create_session(key, expire_in_days=30):
    Session.objects.create(
        session_key=key,
        session_data="",
        expire_date=timezone.now() + timedelta(days=expire_in_days),
    )


def test_prune_removes_orphans_without_session():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="orphan", device_label="d", last_seen_at=timezone.now()
    )
    call_command("prune_user_sessions")
    assert not UserSession.objects.filter(session_key="orphan").exists()


def test_prune_removes_stale_user_sessions():
    user = UserFactory()
    _create_session("ok")
    UserSession.objects.create(
        user=user,
        session_key="ok",
        device_label="d",
        last_seen_at=timezone.now() - timedelta(days=40),
    )
    call_command("prune_user_sessions")
    assert not UserSession.objects.filter(session_key="ok").exists()


def test_prune_keeps_valid_user_sessions():
    user = UserFactory()
    _create_session("good")
    UserSession.objects.create(
        user=user,
        session_key="good",
        device_label="d",
        last_seen_at=timezone.now() - timedelta(days=2),
    )
    call_command("prune_user_sessions")
    assert UserSession.objects.filter(session_key="good").exists()
