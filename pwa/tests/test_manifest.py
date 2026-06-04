"""Tests de la vista /manifest.webmanifest."""

import json

import pytest


@pytest.mark.django_db
def test_manifest_is_public(client):
    """El manifest se sirve sin autenticación (el navegador lo pide antes del login)."""
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200


@pytest.mark.django_db
def test_manifest_content_type(client):
    response = client.get("/manifest.webmanifest")
    assert response["Content-Type"].startswith("application/manifest+json")


@pytest.mark.django_db
def test_manifest_is_valid_json(client):
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    assert isinstance(data, dict)


@pytest.mark.django_db
def test_manifest_has_required_fields(client):
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    assert data["name"] == "La Porra del Jefe · Mundial 2026"
    assert data["short_name"] == "La Porra del Jefe"
    assert data["start_url"] == "/"
    assert data["scope"] == "/"
    assert data["display"] == "standalone"
    assert data["theme_color"] == "#1a1530"
    assert data["background_color"] == "#1a1530"
    assert data["lang"] == "es-ES"


@pytest.mark.django_db
def test_manifest_has_required_icons(client):
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    icons = data["icons"]
    purposes = {(i["sizes"], i["purpose"]) for i in icons}
    assert ("192x192", "any") in purposes
    assert ("512x512", "any") in purposes
    assert any("maskable" in p for _, p in purposes)
