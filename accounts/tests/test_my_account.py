import pytest
from django.urls import reverse

from accounts.forms import ProfileForm
from accounts.models import AuditLog, User
from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_profile_form_saves_editable_fields():
    user = UserFactory(name="Ana", dept="", sede="", puesto="")
    form = ProfileForm(
        data={"name": "Ana López", "dept": "gestion", "sede": "vigo", "puesto": "desarrollo"},
        instance=user,
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    saved.refresh_from_db()
    assert saved.name == "Ana López"
    assert saved.dept == "gestion"
    assert saved.sede == "vigo"
    assert saved.puesto == "desarrollo"


@pytest.mark.django_db
def test_profile_form_strips_name():
    user = UserFactory()
    form = ProfileForm(
        data={"name": "  Ana  ", "dept": "gestion", "sede": "vigo", "puesto": "desarrollo"},
        instance=user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["name"] == "Ana"


@pytest.mark.django_db
def test_profile_form_rejects_empty_name():
    user = UserFactory()
    form = ProfileForm(
        data={"name": "   ", "dept": "gestion", "sede": "vigo", "puesto": "desarrollo"},
        instance=user,
    )
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_profile_form_rejects_invalid_choice():
    user = UserFactory()
    form = ProfileForm(
        data={"name": "Ana", "dept": "INEXISTENTE", "sede": "vigo", "puesto": "desarrollo"},
        instance=user,
    )
    assert not form.is_valid()
    assert "dept" in form.errors


@pytest.mark.django_db
def test_profile_form_ignores_uneditable_fields():
    user = UserFactory(email="ana@edisa.com", is_gestor=False, is_staff=False)
    form = ProfileForm(
        data={
            "name": "Ana",
            "dept": "gestion",
            "sede": "vigo",
            "puesto": "desarrollo",
            "email": "otro@edisa.com",
            "is_gestor": "on",
            "is_staff": "on",
        },
        instance=user,
    )
    assert form.is_valid(), form.errors
    saved = form.save()
    saved.refresh_from_db()
    assert saved.email == "ana@edisa.com"
    assert saved.is_gestor is False
    assert saved.is_staff is False


def test_my_account_url_resolves():
    assert reverse("accounts:my_account") == "/mi-cuenta/"


@pytest.mark.django_db
def test_my_account_redirects_anonymous(client):
    r = client.get(reverse("accounts:my_account"))
    assert r.status_code == 302
    # accounts.urls está montado en "/" en porra26/urls.py, así que login es "/"
    assert "next=/mi-cuenta/" in r.url


@pytest.mark.django_db
def test_my_account_get_renders_for_authenticated_user(client):
    user = UserFactory(email="ana@edisa.com", name="Ana", dept="gestion", sede="vigo", puesto="desarrollo")
    client.force_login(user)
    r = client.get(reverse("accounts:my_account"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "ana@edisa.com" in body
    assert "Datos personales" in body
    assert "Seguridad" in body
    assert "Preferencias" in body
    assert 'name="action" value="profile"' in body
    assert 'name="action" value="password"' in body


@pytest.mark.django_db
def test_profile_post_updates_editable_fields(client):
    user = UserFactory(name="Ana", dept="", sede="", puesto="")
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {
            "action": "profile",
            "name": "Ana López",
            "dept": "gestion",
            "sede": "vigo",
            "puesto": "desarrollo",
        },
    )
    assert r.status_code == 302
    assert r.url == reverse("accounts:my_account")
    user.refresh_from_db()
    assert user.name == "Ana López"
    assert user.dept == "gestion"
    assert user.sede == "vigo"
    assert user.puesto == "desarrollo"


@pytest.mark.django_db
def test_profile_post_ignores_email_and_role(client):
    user = UserFactory(email="ana@edisa.com", is_gestor=False, is_staff=False)
    client.force_login(user)
    client.post(
        reverse("accounts:my_account"),
        {
            "action": "profile",
            "name": "Ana",
            "dept": "gestion",
            "sede": "vigo",
            "puesto": "desarrollo",
            "email": "otro@edisa.com",
            "is_gestor": "on",
            "is_staff": "on",
        },
    )
    user.refresh_from_db()
    assert user.email == "ana@edisa.com"
    assert user.is_gestor is False
    assert user.is_staff is False


@pytest.mark.django_db
def test_profile_post_invalid_choice_keeps_db_intact(client):
    user = UserFactory(name="Ana", dept="gestion", sede="vigo", puesto="desarrollo")
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {
            "action": "profile",
            "name": "Ana",
            "dept": "INEXISTENTE",
            "sede": "vigo",
            "puesto": "desarrollo",
        },
    )
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.dept == "gestion"
