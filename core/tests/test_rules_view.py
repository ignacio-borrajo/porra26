from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from competition.tests.factories import RoundFactory
from pot.models import PotSettings
from pot.tests.factories import PrizeFactory


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


@pytest.mark.django_db
def test_rules_renders_points_card(client):
    RoundFactory(id="groups", label="Fase de grupos", short="GRP", points=3, order=1)
    RoundFactory(id="r32", label="Dieciseisavos", short="R32", points=5, order=2)
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "Cómo funciona la porra" in content
    assert "Sistema de puntos" in content
    # Ejemplos
    assert "Marcador exacto" in content
    assert "Solo el resultado" in content
    assert "Fallo" in content
    # Las mini-tarjetas reutilizan el patrón visual de /competicion/:
    # bandera arriba, nombre debajo, score-bubble : score-bubble.
    assert content.count('class="match-card-teams"') == 3
    assert content.count('class="score-bubble"') == 6  # 3 ejemplos × 2 bubbles
    # Tabla de rondas con puntos
    assert "Fase de grupos" in content
    assert "Dieciseisavos" in content
    assert ">5</strong>" in content  # points cell for r32 — unique to the table row


@pytest.mark.django_db
def test_rules_renders_close_card(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "Las apuestas cierran" in content
    assert "2 horas antes del saque" in content
    # Estados del timeline
    for label in ("Abierto", "Cerrando", "Cerrado", "En juego", "Final"):
        assert label in content
    # Mini ejemplos de partido por estado: cuenta atrás, marcador en vivo y final
    assert "01:23:45" in content  # cuenta atrás del estado closing
    assert "1 — 0" in content  # marcador en vivo
    assert "2 — 1" in content  # marcador final


@pytest.mark.django_db
def test_rules_renders_pot_card(client):
    PrizeFactory(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    PrizeFactory(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    PrizeFactory(scope="global", position=3, amount=Decimal("96"), label="3er premio")
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "El bote y los premios" in content
    assert "240" in content
    assert "144" in content
    assert "96" in content


@pytest.mark.django_db
def test_rules_renders_tiebreak_and_access(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "Cómo se decide quién gana" in content
    assert "Más puntos" in content
    assert "Más marcadores exactos" in content
    assert "Acceso a la app" in content
    assert "Sin recuperación automática" in content
    assert "Última actualización del reglamento" in content


@pytest.mark.django_db
def test_rules_renders_placeholder_medals_when_no_prizes(client):
    # Delete seed prizes so the {% empty %} branch fires.
    from pot.models import Prize

    Prize.objects.filter(scope="global").delete()
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    # Three placeholder badges (1º, 2º, 3º) rendered.
    for pos in ("1º", "2º", "3º"):
        assert f">{pos}<" in content
    # Em dash placeholder strong appears at least 3 times.
    assert content.count(">—</strong>") >= 3
