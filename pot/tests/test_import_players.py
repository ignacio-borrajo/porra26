from io import BytesIO

import pytest
from django.urls import reverse
from openpyxl import Workbook

from accounts.models import AuditLog, User
from accounts.tests.factories import GestorFactory, UserFactory
from pot.models import Payment
from pot.services.import_players import import_players_from_xlsx


def _wb(rows) -> BytesIO:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@pytest.mark.django_db
def test_import_creates_users():
    buf = _wb([
        ["Email", "Nombre", "Contraseña"],
        ["alpha@edisa.com", "Alpha", "alpha-pass"],
        ["beta@edisa.com", "Beta", "beta-pass"],
    ])
    result = import_players_from_xlsx(buf)
    assert result.created == 2
    assert result.skipped_total == 0
    u = User.objects.get(email="alpha@edisa.com")
    assert u.name == "Alpha"
    assert u.is_jugador and not u.is_gestor
    assert u.must_change_password is True
    assert Payment.objects.filter(player=u).exists()
    # La contraseña se asigna tal cual aunque sea débil.
    assert u.check_password("alpha-pass")


@pytest.mark.django_db
def test_import_skips_existing_email():
    UserFactory(email="dup@edisa.com")
    buf = _wb([
        ["email", "nombre", "contraseña"],
        ["dup@edisa.com", "Duplicado", "x"],
        ["new@edisa.com", "Nuevo", "y"],
    ])
    result = import_players_from_xlsx(buf)
    assert result.created == 1
    assert result.skipped_existing == 1


@pytest.mark.django_db
def test_import_skips_invalid_email():
    buf = _wb([
        ["email", "nombre", "contraseña"],
        ["no-es-un-email", "Foo", "x"],
        ["ok@edisa.com", "Ok", "y"],
    ])
    result = import_players_from_xlsx(buf)
    assert result.created == 1
    assert result.skipped_invalid_email == 1


@pytest.mark.django_db
def test_import_skips_empty_rows_and_missing_fields():
    buf = _wb([
        ["email", "nombre", "contraseña"],
        [None, None, None],
        ["", "", ""],
        ["a@edisa.com", "", "x"],
        ["b@edisa.com", "B", ""],
        ["c@edisa.com", "C", "z"],
    ])
    result = import_players_from_xlsx(buf)
    assert result.created == 1
    assert result.skipped_empty == 4


@pytest.mark.django_db
def test_import_does_not_update_existing_user():
    existing = UserFactory(email="x@edisa.com", name="Original")
    existing.set_password("old-pass")
    existing.save()
    buf = _wb([
        ["email", "nombre", "contraseña"],
        ["x@edisa.com", "Cambiado", "new-pass"],
    ])
    result = import_players_from_xlsx(buf)
    assert result.skipped_existing == 1
    existing.refresh_from_db()
    assert existing.name == "Original"
    assert existing.check_password("old-pass")


@pytest.mark.django_db
def test_import_column_order_is_irrelevant():
    buf = _wb([
        ["Contraseña", "Nombre", "Email"],
        ["pw", "Nombre1", "a@edisa.com"],
    ])
    result = import_players_from_xlsx(buf)
    assert result.created == 1
    assert User.objects.get(email="a@edisa.com").name == "Nombre1"


@pytest.mark.django_db
def test_import_missing_required_column_returns_error():
    buf = _wb([
        ["email", "nombre"],
        ["a@edisa.com", "Alpha"],
    ])
    result = import_players_from_xlsx(buf)
    assert result.error is not None
    assert result.created == 0


@pytest.mark.django_db
def test_import_unreadable_file_returns_error():
    result = import_players_from_xlsx(BytesIO(b"esto no es un xlsx"))
    assert result.error is not None


@pytest.mark.django_db
def test_import_creates_audit_log_per_user(monkeypatch):
    actor = GestorFactory()
    buf = _wb([
        ["email", "nombre", "contraseña"],
        ["audit@edisa.com", "Audit", "p"],
    ])
    import_players_from_xlsx(buf, actor=actor)
    user = User.objects.get(email="audit@edisa.com")
    assert AuditLog.objects.filter(
        actor=actor, action="player_created", target_id=str(user.id)
    ).exists()


@pytest.mark.django_db
def test_view_requires_gestor(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("pot:players_import"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_view_get_renders_upload_modal(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:players_import"), HTTP_X_MODAL="1")
    assert r.status_code == 200
    assert b"Importar jugadores" in r.content


@pytest.mark.django_db
def test_view_post_no_file_shows_error(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.post(reverse("pot:players_import"), HTTP_X_MODAL="1")
    assert r.status_code == 200
    assert r.headers.get("X-Modal-Errors") == "1"


@pytest.mark.django_db
def test_view_post_xlsx_redirects_to_result_via_x_modal_next(client):
    client.force_login(GestorFactory(must_change_password=False))
    buf = _wb([
        ["email", "nombre", "contraseña"],
        ["flow@edisa.com", "Flow", "pw"],
    ])
    buf.name = "import.xlsx"
    r = client.post(
        reverse("pot:players_import"),
        {"file": buf},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.headers.get("X-Modal-Next") == reverse("pot:players_import_result")
    assert User.objects.filter(email="flow@edisa.com").exists()


@pytest.mark.django_db
def test_view_result_renders_counters_and_consumes_session(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    UserFactory(email="dup@edisa.com")
    buf = _wb([
        ["email", "nombre", "contraseña"],
        ["dup@edisa.com", "Dup", "x"],
        ["new@edisa.com", "New", "y"],
        ["bad-email", "Bad", "z"],
    ])
    buf.name = "import.xlsx"
    client.post(reverse("pot:players_import"), {"file": buf}, HTTP_X_MODAL="1")
    r = client.get(reverse("pot:players_import_result"), HTTP_X_MODAL="1")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Creados" in body and "Saltados" in body
    # El resultado es de un solo uso: la segunda llamada redirige.
    r2 = client.get(reverse("pot:players_import_result"))
    assert r2.status_code == 302


@pytest.mark.django_db
def test_view_rejects_wrong_extension(client):
    client.force_login(GestorFactory(must_change_password=False))
    buf = BytesIO(b"not xlsx")
    buf.name = "import.csv"
    r = client.post(
        reverse("pot:players_import"),
        {"file": buf},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.headers.get("X-Modal-Errors") == "1"
