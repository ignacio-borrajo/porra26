import pytest
from django.db.utils import IntegrityError
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def test_user_session_can_be_created_with_required_fields():
    user = UserFactory()
    us = UserSession.objects.create(
        user=user,
        session_key="abc123def456abc123def456abc123de",
        device_label="iPhone — Safari",
        last_seen_at=timezone.now(),
    )
    assert us.pk is not None
    assert us.remembered is False
    assert us.is_pwa is False
    assert us.ip_at_login is None
    assert us.user == user


def test_user_session_key_is_unique():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="dup", device_label="x", last_seen_at=timezone.now()
    )
    with pytest.raises(IntegrityError):
        UserSession.objects.create(
            user=user, session_key="dup", device_label="x", last_seen_at=timezone.now()
        )


def test_user_session_cascade_on_user_delete():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="x", device_label="d", last_seen_at=timezone.now()
    )
    user.delete()
    assert UserSession.objects.count() == 0
