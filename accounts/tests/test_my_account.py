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
