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


@pytest.mark.django_db
def test_sw_precaches_offline_page(client):
    """El install debe meter /offline/ en cache para poder servirla cuando el
    origen esté caído (redeploy de Railway). Sin esto el fallback no existe."""
    response = client.get("/service-worker.js")
    body = response.content.decode("utf-8")
    assert "/offline/" in body
    assert "cache.add" in body or "cache.addAll" in body


@pytest.mark.django_db
def test_sw_falls_back_on_navigation_5xx(client):
    """El handler de fetch debe distinguir navegaciones (mode === 'navigate')
    y servir la página cacheada cuando la red falla o el server da 5xx."""
    response = client.get("/service-worker.js")
    body = response.content.decode("utf-8")
    assert "'navigate'" in body or '"navigate"' in body
    assert ">= 500" in body
