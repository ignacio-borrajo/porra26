import pytest
from django.urls import reverse

from accounts.forms import ProfileForm
from accounts.models import AuditLog
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
    user = UserFactory(
        email="ana@edisa.com", name="Ana", dept="gestion", sede="vigo", puesto="desarrollo"
    )
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


@pytest.mark.django_db
def test_password_post_changes_password_and_keeps_session(client):
    user = UserFactory(email="ana@edisa.com")
    user.set_password("Vieja12345!")
    user.save()
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Vieja12345!",
            "new1": "NuevaSegura1",
            "new2": "NuevaSegura1",
        },
    )
    assert r.status_code == 302
    user.refresh_from_db()
    assert user.check_password("NuevaSegura1")
    # sesión sigue viva
    r2 = client.get(reverse("accounts:my_account"))
    assert r2.status_code == 200


@pytest.mark.django_db
def test_password_post_wrong_current_keeps_password(client):
    user = UserFactory()
    user.set_password("Correcta1234")
    user.save()
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Incorrecta1234",
            "new1": "NuevaSegura1",
            "new2": "NuevaSegura1",
        },
    )
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Correcta1234")


@pytest.mark.django_db
def test_password_post_mismatch_shows_error(client):
    user = UserFactory()
    user.set_password("Correcta1234")
    user.save()
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Correcta1234",
            "new1": "NuevaSegura1",
            "new2": "OtraDistinta1",
        },
    )
    assert r.status_code == 200
    assert b"no coinciden" in r.content


@pytest.mark.django_db
def test_password_post_weak_rejected(client):
    user = UserFactory()
    user.set_password("Correcta1234")
    user.save()
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Correcta1234",
            "new1": "todominusculas",
            "new2": "todominusculas",
        },
    )
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Correcta1234")


@pytest.mark.django_db
def test_password_post_keeps_must_change_flag_false(client):
    """El cambio normal desde /mi-cuenta/ ocurre cuando must_change_password ya
    es False (el middleware redirige si fuera True). Verificamos que tras el
    cambio el flag sigue siendo False."""
    user = UserFactory(must_change_password=False)
    user.set_password("Inicial12345")
    user.save()
    client.force_login(user)
    r = client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Inicial12345",
            "new1": "NuevaSegura1",
            "new2": "NuevaSegura1",
        },
    )
    assert r.status_code == 302
    user.refresh_from_db()
    assert user.must_change_password is False


@pytest.mark.django_db
def test_post_without_action_returns_400(client):
    user = UserFactory()
    client.force_login(user)
    r = client.post(reverse("accounts:my_account"), {"name": "Ana"})
    assert r.status_code == 400


@pytest.mark.django_db
def test_post_unknown_action_returns_400(client):
    user = UserFactory()
    client.force_login(user)
    r = client.post(reverse("accounts:my_account"), {"action": "explotame"})
    assert r.status_code == 400


@pytest.mark.django_db
def test_profile_post_writes_audit_log_when_changed(client):
    user = UserFactory(name="Ana", dept="gestion", sede="vigo", puesto="desarrollo")
    client.force_login(user)
    client.post(
        reverse("accounts:my_account"),
        {
            "action": "profile",
            "name": "Ana López",
            "dept": "gestion",
            "sede": "vigo",
            "puesto": "desarrollo",
        },
    )
    log = AuditLog.objects.filter(action="profile.update").first()
    assert log is not None
    assert log.actor_id == user.id
    assert log.target_type == "user"
    assert log.target_id == str(user.id)
    assert log.payload == {"changed": ["name"]}


@pytest.mark.django_db
def test_profile_post_no_audit_when_nothing_changed(client):
    user = UserFactory(name="Ana", dept="gestion", sede="vigo", puesto="desarrollo")
    client.force_login(user)
    client.post(
        reverse("accounts:my_account"),
        {
            "action": "profile",
            "name": "Ana",
            "dept": "gestion",
            "sede": "vigo",
            "puesto": "desarrollo",
        },
    )
    assert AuditLog.objects.filter(action="profile.update").count() == 0


@pytest.mark.django_db
def test_password_change_writes_audit_log(client):
    user = UserFactory()
    user.set_password("Correcta1234")
    user.save()
    client.force_login(user)
    client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Correcta1234",
            "new1": "NuevaSegura1",
            "new2": "NuevaSegura1",
        },
    )
    log = AuditLog.objects.filter(action="password.change").first()
    assert log is not None
    assert log.actor_id == user.id
    assert log.target_type == "user"
    assert log.target_id == str(user.id)
    assert log.payload == {}


@pytest.mark.django_db
def test_topbar_avatar_links_to_my_account(client):
    user = UserFactory()
    client.force_login(user)
    # Usamos la propia /mi-cuenta/ — también renderiza el topbar y no depende
    # de que existan datos del dashboard de competición.
    r = client.get(reverse("accounts:my_account"))
    assert r.status_code == 200
    body = r.content.decode()
    assert 'href="/mi-cuenta/"' in body


@pytest.mark.django_db
def test_my_account_has_logout_button(client):
    # En móvil el jugador pierde el botón de salir del topbar; debe poder
    # cerrar sesión desde "Mi cuenta".
    user = UserFactory()
    client.force_login(user)
    r = client.get(reverse("accounts:my_account"))
    assert r.status_code == 200
    body = r.content.decode()
    logout_url = reverse("accounts:logout")
    # El form de logout aparece dentro de la card de Preferencias.
    assert f'action="{logout_url}"' in body
    assert ">Salir<" in body
