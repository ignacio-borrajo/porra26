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
def test_user_dept_accepts_known_choice():
    u = User.objects.create_user(email="d@edisa.com", password="pw", name="D", dept="nominas")
    assert u.dept == "nominas"


@pytest.mark.django_db
def test_user_sede_defaults_blank():
    u = User.objects.create_user(email="s@edisa.com", password="pw", name="S")
    assert u.sede == ""


@pytest.mark.django_db
def test_user_puesto_defaults_blank():
    u = User.objects.create_user(email="p@edisa.com", password="pw", name="P")
    assert u.puesto == ""


@pytest.mark.django_db
def test_user_is_jugador_default_true():
    u = User.objects.create_user(email="j@edisa.com", password="pw", name="J")
    assert u.is_jugador is True


@pytest.mark.django_db
def test_user_is_gestor_default_false():
    u = User.objects.create_user(email="g2@edisa.com", password="pw", name="G2")
    assert u.is_gestor is False


@pytest.mark.django_db
def test_superuser_is_admin_not_jugador():
    u = User.objects.create_superuser(email="root@edisa.com", password="pw", name="Root")
    assert u.is_staff and u.is_superuser
    assert u.is_jugador is False
    assert u.is_gestor is False
