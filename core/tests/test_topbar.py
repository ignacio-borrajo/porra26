import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_topbar_has_rules_link(client):
    client.force_login(UserFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("core:rules") in content
    assert "Reglas" in content


@pytest.mark.django_db
def test_rules_active_class_on_rules_page(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    href = reverse("core:rules")
    # El enlace activo lleva clase is-active en el mismo elemento.
    assert f'href="{href}" class="nav-item is-active"' in content
