import pytest

from accounts.models import AuditLog, User


@pytest.mark.django_db
def test_audit_log_can_be_created():
    actor = User.objects.create_user(email="g@edisa.com", password="x", name="G", is_gestor=True)
    entry = AuditLog.objects.create(
        actor=actor,
        action="password_reset",
        target_type="user",
        target_id="42",
        payload={"by": "g@edisa.com"},
    )
    assert entry.pk
    assert entry.created_at is not None
    assert entry.payload == {"by": "g@edisa.com"}
