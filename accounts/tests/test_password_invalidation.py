from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def test_admin_password_change_wipes_user_sessions():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="k1", device_label="d", last_seen_at=timezone.now()
    )
    UserSession.objects.create(
        user=user, session_key="k2", device_label="d", last_seen_at=timezone.now()
    )
    user.set_password("NewPass123")
    user.save(update_fields=["password"])
    assert UserSession.objects.filter(user=user).count() == 0
