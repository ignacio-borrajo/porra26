import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from accounts.tests.factories import GestorFactory, UserFactory
from competition.api.auth import require_teams_api_token


@require_teams_api_token
def fake_view(request, **kwargs):
    return HttpResponse("ok")


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_accepts_correct_bearer_token():
    rf = RequestFactory()
    req = rf.get("/x", HTTP_AUTHORIZATION="Bearer testing-token-1234567890")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 200


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_rejects_wrong_token():
    rf = RequestFactory()
    req = rf.get("/x", HTTP_AUTHORIZATION="Bearer otro")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_rejects_missing_header():
    rf = RequestFactory()
    req = rf.get("/x")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_accepts_gestor_session_without_token():
    rf = RequestFactory()
    req = rf.get("/x")
    req.user = GestorFactory()
    res = fake_view(req)
    assert res.status_code == 200


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_rejects_jugador_session_without_token():
    rf = RequestFactory()
    req = rf.get("/x")
    req.user = UserFactory(is_gestor=False)
    res = fake_view(req)
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="")
def test_empty_setting_rejects_all_bearer():
    rf = RequestFactory()
    req = rf.get("/x", HTTP_AUTHORIZATION="Bearer cualquier-cosa")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 401
