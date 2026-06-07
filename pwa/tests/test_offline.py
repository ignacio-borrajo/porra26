"""Tests de la vista /offline/, que el service worker sirve cuando el origen
está caído (típicamente durante un redeploy de Railway)."""

import pytest


@pytest.mark.django_db
def test_offline_is_public(client):
    """No requiere login: el SW la precachea sin sesión y la sirve igual."""
    response = client.get("/offline/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_offline_content_type_is_html(client):
    response = client.get("/offline/")
    assert response["Content-Type"].startswith("text/html")


@pytest.mark.django_db
def test_offline_cache_control_allows_sw_storage(client):
    """`no-store` impediría al SW guardar la respuesta en Cache Storage."""
    response = client.get("/offline/")
    cache_control = response["Cache-Control"]
    assert "no-store" not in cache_control


@pytest.mark.django_db
def test_offline_has_no_external_assets(client):
    """Si el origen está caído, no se puede pedir nada al servidor: la página
    debe ser autosuficiente (CSS y JS inline, sin <link href> ni <script src>)."""
    response = client.get("/offline/")
    body = response.content.decode("utf-8")
    assert "<link " not in body or 'rel="stylesheet"' not in body
    assert "<script src=" not in body


@pytest.mark.django_db
def test_offline_retries_on_load(client):
    """Sanity check de que el JS de auto-retry sigue presente."""
    response = client.get("/offline/")
    body = response.content.decode("utf-8")
    assert "location.reload()" in body
