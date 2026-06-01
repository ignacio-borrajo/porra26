import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from competition.tests.factories import RoundFactory
from pot.models import PotSettings


@pytest.mark.django_db
def test_rules_redirects_anonymous(client):
    r = client.get(reverse("core:rules"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_rules_renders_for_authenticated(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_rules_context_has_required_keys(client):
    RoundFactory(id="groups", label="Fase de grupos", short="GRP", points=3, order=1)
    PotSettings.load()  # asegura instancia
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    ctx = r.context
    assert "rounds" in ctx and list(ctx["rounds"])  # no vacío
    assert "pot_per_player" in ctx
    assert "pot_prizes" in ctx
    assert ctx["bet_close_hours"] == 2
    assert "rules_updated_at" in ctx
