"""Tests de la vista /service-worker.js."""

import pytest


@pytest.mark.django_db
def test_sw_is_public(client):
    response = client.get("/service-worker.js")
    assert response.status_code == 200


@pytest.mark.django_db
def test_sw_content_type(client):
    response = client.get("/service-worker.js")
    assert response["Content-Type"].startswith("application/javascript")


@pytest.mark.django_db
def test_sw_headers(client):
    response = client.get("/service-worker.js")
    assert response["Service-Worker-Allowed"] == "/"
    assert response["Cache-Control"] == "no-cache"


@pytest.mark.django_db
def test_sw_has_fetch_handler(client):
    """Chrome exige un fetch handler para considerar la app instalable."""
    response = client.get("/service-worker.js")
    body = response.content.decode("utf-8")
    assert "addEventListener('fetch'" in body or 'addEventListener("fetch"' in body


@pytest.mark.django_db
def test_sw_includes_version(client):
    response = client.get("/service-worker.js")
    body = response.content.decode("utf-8")
    assert "const VERSION" in body
    assert 'const VERSION = ""' not in body
    assert "const VERSION = ''" not in body
