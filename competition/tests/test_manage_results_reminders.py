from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import GestorFactory, UserFactory
from competition.models import BetsReminderLog
from competition.tests.factories import MatchFactory, PredictionFactory, TeamFactory


@pytest.fixture
def gestor(client):
    """Gestor puro (no juega) para no contaminar el cómputo de rezagados."""
    g = GestorFactory(is_jugador=False)
    client.force_login(g)
    return g


def _upcoming_match():
    h = TeamFactory(code="ESP", name="España")
    a = TeamFactory(code="MEX", name="México")
    return MatchFactory(home=h, away=a, kickoff=timezone.now() + timedelta(hours=10))


@pytest.mark.django_db
def test_upcoming_shows_reminder_button(client, gestor):
    UserFactory(name="Ana")
    m = _upcoming_match()
    res = client.get(reverse("competicion:manage_results"))
    assert res.status_code == 200
    expected_url = reverse("competicion:api:recordatorio_enviar", args=[m.id])
    assert expected_url in res.content.decode()
    assert "Recordatorio" in res.content.decode()


@pytest.mark.django_db
def test_upcoming_shows_pending_pill_with_count(client, gestor):
    UserFactory(name="Ana")
    UserFactory(name="Beto")
    _upcoming_match()
    res = client.get(reverse("competicion:manage_results"))
    html = res.content.decode()
    assert "2 sin apostar" in html


@pytest.mark.django_db
def test_upcoming_pill_shows_green_when_all_bet(client, gestor):
    u = UserFactory(name="Ana")
    m = _upcoming_match()
    PredictionFactory(player=u, match=m)
    res = client.get(reverse("competicion:manage_results"))
    html = res.content.decode()
    assert "Todos han apostado" in html


@pytest.mark.django_db
def test_upcoming_disables_button_when_no_pending(client, gestor):
    u = UserFactory(name="Ana")
    m = _upcoming_match()
    PredictionFactory(player=u, match=m)
    res = client.get(reverse("competicion:manage_results"))
    html = res.content.decode()
    # El form sigue visible pero el botón está disabled
    assert "disabled" in html


@pytest.mark.django_db
def test_upcoming_shows_last_reminder_tooltip(client, gestor):
    UserFactory(name="Ana")
    m = _upcoming_match()
    BetsReminderLog.objects.create(
        match=m,
        kind=BetsReminderLog.KIND_T_MINUS_4H,
        sent_at=timezone.now() - timedelta(hours=1),
        pending_count=3,
        pending_names=["X", "Y", "Z"],
    )
    res = client.get(reverse("competicion:manage_results"))
    html = res.content.decode()
    # Hay un title attr con "rezagados" o info del log
    assert "rezagados" in html or "3 " in html


@pytest.mark.django_db
def test_finished_match_does_not_show_reminder_button(client, gestor):
    """Un match finalizado no tiene botón de recordatorio (cierre pasado)."""
    h = TeamFactory(code="ESP", name="España")
    a = TeamFactory(code="MEX", name="México")
    m = MatchFactory(
        home=h,
        away=a,
        kickoff=timezone.now() - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=timezone.now() - timedelta(hours=22),
    )
    res = client.get(reverse("competicion:manage_results"))
    html = res.content.decode()
    expected_url = reverse("competicion:api:recordatorio_enviar", args=[m.id])
    # El botón solo aparece en upcoming, no en done
    assert expected_url not in html
