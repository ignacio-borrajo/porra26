import pytest

from pot.forms import PlayerForm


@pytest.fixture(autouse=True)
def _allow_domain(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])


@pytest.mark.django_db
def test_player_form_accepts_all_org_fields():
    form = PlayerForm(data={
        "name": "Ana López",
        "email": "ana@edisa.com",
        "dept": "nominas",
        "sede": "vigo",
        "puesto": "desarrollo",
        "is_jugador": "on",
        "is_gestor": "",
    })
    assert form.is_valid(), form.errors
    user = form.save(commit=False)
    user.set_password("x")
    user.save()
    assert user.dept == "nominas"
    assert user.sede == "vigo"
    assert user.puesto == "desarrollo"
    assert user.is_jugador is True
    assert user.is_gestor is False


@pytest.mark.django_db
def test_player_form_allows_blank_org_fields():
    form = PlayerForm(data={
        "name": "Sin Datos",
        "email": "sin@edisa.com",
        "dept": "",
        "sede": "",
        "puesto": "",
        "is_jugador": "on",
        "is_gestor": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_player_form_rejects_unknown_choice():
    form = PlayerForm(data={
        "name": "X",
        "email": "x@edisa.com",
        "dept": "marketing",  # no está en choices
        "sede": "",
        "puesto": "",
        "is_jugador": "on",
        "is_gestor": "",
    })
    assert not form.is_valid()
    assert "dept" in form.errors
