from datetime import timedelta

from django.contrib.sessions.models import Session
from django.utils import timezone

from accounts.models import AuditLog, UserSession
from accounts.services.sessions import revoke_sessions
from accounts.tests.factories import UserFactory


def _create_session(session_key: str):
    Session.objects.create(
        session_key=session_key,
        session_data="",
        expire_date=timezone.now() + timedelta(days=30),
    )


def test_revoke_sessions_deletes_session_and_user_session():
    user = UserFactory()
    _create_session("aaaaaaaa")
    UserSession.objects.create(
        user=user, session_key="aaaaaaaa", device_label="d", last_seen_at=timezone.now()
    )

    deleted = revoke_sessions(
        user=user, session_keys=["aaaaaaaa"], actor=user, reason="test"
    )

    assert deleted == 1
    assert not Session.objects.filter(session_key="aaaaaaaa").exists()
    assert not UserSession.objects.filter(session_key="aaaaaaaa").exists()


def test_revoke_sessions_creates_audit_log():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="x", device_label="d", last_seen_at=timezone.now()
    )

    revoke_sessions(user=user, session_keys=["x"], actor=user, reason="password_change")

    log = AuditLog.objects.get(action="sessions.revoked", target_id=str(user.id))
    assert log.payload == {"count": 1, "reason": "password_change"}
    assert log.actor == user


def test_revoke_sessions_with_empty_list_is_noop():
    user = UserFactory()
    assert revoke_sessions(user=user, session_keys=[], actor=user) == 0
    assert AuditLog.objects.filter(action="sessions.revoked").count() == 0


def test_revoke_sessions_only_touches_own_user():
    a = UserFactory()
    b = UserFactory()
    UserSession.objects.create(
        user=a, session_key="ka", device_label="d", last_seen_at=timezone.now()
    )
    UserSession.objects.create(
        user=b, session_key="kb", device_label="d", last_seen_at=timezone.now()
    )

    revoke_sessions(user=a, session_keys=["ka", "kb"], actor=a)

    assert UserSession.objects.filter(user=b).count() == 1


def test_revoke_sessions_idempotent():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="x", device_label="d", last_seen_at=timezone.now()
    )
    revoke_sessions(user=user, session_keys=["x"], actor=user)
    assert revoke_sessions(user=user, session_keys=["x"], actor=user) == 0
