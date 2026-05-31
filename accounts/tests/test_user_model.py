import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_user_uses_email_as_username_field():
    assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_create_user_persists():
    u = User.objects.create_user(email="a@edisa.com", password="pw", name="Ana")
    assert u.pk is not None
    assert u.email == "a@edisa.com"
    assert u.check_password("pw")


@pytest.mark.django_db
def test_create_user_defaults_role_to_jugador():
    u = User.objects.create_user(email="a@edisa.com", password="pw", name="Ana")
    assert u.role == "jugador"
    assert u.must_change_password is True
    assert u.is_active is True


@pytest.mark.django_db
def test_create_superuser_is_gestor():
    u = User.objects.create_superuser(email="g@edisa.com", password="pw", name="G")
    assert u.is_staff and u.is_superuser
    assert u.role == "gestor"
