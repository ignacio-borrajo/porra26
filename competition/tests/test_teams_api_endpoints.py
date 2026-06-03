import hashlib
from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from competition.models import BetsClosingReport
from competition.tests.factories import MatchFactory, TeamFactory

TOKEN = "testing-token-1234567890"
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_returns_only_closed_unsent(client):
    now = timezone.now()
    # Abierto: cierra en 4h → no aparece
    MatchFactory(kickoff=now + timedelta(hours=6))
    # Cerrado y sin envío → aparece
    m_closed = MatchFactory(kickoff=now + timedelta(hours=1))
    # Cerrado y enviado → no aparece
    m_sent = MatchFactory(kickoff=now + timedelta(hours=1))
    BetsClosingReport.objects.create(match=m_sent, sent_at=now)
    # Cerrado, con report pero sin sent_at → aparece
    m_pending = MatchFactory(kickoff=now + timedelta(hours=1))
    BetsClosingReport.objects.create(match=m_pending)

    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    assert res.status_code == 200
    ids = sorted(m["id"] for m in res.json()["matches"])
    assert ids == sorted([m_closed.id, m_pending.id])


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_includes_live_and_done_if_unsent(client):
    now = timezone.now()
    # Live (sin resultado, kickoff pasado)
    m_live = MatchFactory(kickoff=now - timedelta(minutes=5))
    # Done (con resultado)
    m_done = MatchFactory(
        kickoff=now - timedelta(days=1),
        result_home=1,
        result_away=0,
        finished_at=now - timedelta(hours=1),
    )
    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    ids = sorted(m["id"] for m in res.json()["matches"])
    assert m_live.id in ids
    assert m_done.id in ids


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_ordered_by_kickoff_asc(client):
    now = timezone.now()
    m1 = MatchFactory(kickoff=now - timedelta(hours=3))
    m2 = MatchFactory(kickoff=now - timedelta(hours=2))
    m3 = MatchFactory(kickoff=now - timedelta(hours=1))
    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    ids = [m["id"] for m in res.json()["matches"]]
    assert ids == [m1.id, m2.id, m3.id]


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_payload_shape(client):
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    kickoff = timezone.now() - timedelta(minutes=10)
    m = MatchFactory(home=home, away=away, group="D", kickoff=kickoff)
    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    payload = res.json()["matches"][0]
    assert payload["id"] == m.id
    assert payload["slug"] == m.teams_slug
    assert payload["round"] == m.round.label
    assert payload["group"] == "D"
    assert payload["home"] == {"code": "ESP", "name": "España"}
    assert payload["away"] == {"code": "ARG", "name": "Argentina"}
    assert "kickoff" in payload
    assert "closed_at" in payload


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_does_not_create_reports(client):
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    assert BetsClosingReport.objects.count() == 0


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_requires_token(client):
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierres_pendientes"))
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_returns_pdf(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]), **AUTH)
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert "attachment" in res["Content-Disposition"]
    assert m.teams_slug in res["Content-Disposition"]
    assert bytes(res.content).startswith(b"%PDF-")


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_creates_report_and_updates(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]), **AUTH)
    assert res.status_code == 200
    report = BetsClosingReport.objects.get(match=m)
    assert report.attempts == 1
    assert report.generated_at is not None
    expected_sha = hashlib.sha256(bytes(res.content)).hexdigest()
    assert report.last_sha256 == expected_sha


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_increments_attempts(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    url = reverse("competicion:api:cierre_pdf", args=[m.id])
    client.get(url, **AUTH)
    client.get(url, **AUTH)
    client.get(url, **AUTH)
    assert BetsClosingReport.objects.get(match=m).attempts == 3


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_404_if_not_closed(client):
    m = MatchFactory(kickoff=timezone.now() + timedelta(hours=6))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]), **AUTH)
    assert res.status_code == 404


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_allows_future_match_with_result(client):
    """Cuando el gestor entra un resultado a un partido cuyo cierre todavía
    no ha pasado (testing pre-Mundial, o admin override), el PDF se genera
    igualmente porque la decisión del gestor implica que las apuestas son
    definitivas."""
    m = MatchFactory(
        kickoff=timezone.now() + timedelta(hours=6),
        result_home=2,
        result_away=1,
    )
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]), **AUTH)
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_404_unknown_match(client):
    res = client.get(reverse("competicion:api:cierre_pdf", args=[999_999]), **AUTH)
    assert res.status_code == 404


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_requires_token(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]))
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_accepts_gestor_session(client):
    from accounts.tests.factories import GestorFactory

    gestor = GestorFactory()
    client.force_login(gestor)
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]))
    assert res.status_code == 200


# --- POST cierre_enviar ----------------------------------------------------


@pytest.fixture
def _clear_outbox():
    from django.core import mail

    mail.outbox = []
    yield
    mail.outbox = []


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_sends_email(client, _clear_outbox):
    from django.core import mail

    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.post(reverse("competicion:api:cierre_enviar", args=[m.id]), **AUTH)
    assert res.status_code == 200
    assert len(mail.outbox) == 1
    assert m.teams_slug in mail.outbox[0].subject
    report = BetsClosingReport.objects.get(match=m)
    assert report.sent_at is not None


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_resends_when_already_sent(client, _clear_outbox):
    """Reenviar: la segunda llamada al endpoint dispara un envío nuevo,
    no es idempotente como sí lo es el service `send_closure_email`."""
    from django.core import mail

    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    url = reverse("competicion:api:cierre_enviar", args=[m.id])
    client.post(url, **AUTH)
    client.post(url, **AUTH)
    assert len(mail.outbox) == 2


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_allows_future_match_with_result(client, _clear_outbox):
    from django.core import mail

    m = MatchFactory(
        kickoff=timezone.now() + timedelta(hours=6),
        result_home=2,
        result_away=1,
    )
    res = client.post(reverse("competicion:api:cierre_enviar", args=[m.id]), **AUTH)
    assert res.status_code == 200
    assert len(mail.outbox) == 1


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_404_if_not_closed_and_no_result(client, _clear_outbox):
    from django.core import mail

    m = MatchFactory(kickoff=timezone.now() + timedelta(hours=6))
    res = client.post(reverse("competicion:api:cierre_enviar", args=[m.id]), **AUTH)
    assert res.status_code == 404
    assert len(mail.outbox) == 0


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_404_unknown_match(client):
    res = client.post(reverse("competicion:api:cierre_enviar", args=[999_999]), **AUTH)
    assert res.status_code == 404


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_requires_auth(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.post(reverse("competicion:api:cierre_enviar", args=[m.id]))
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_rejects_get(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_enviar", args=[m.id]), **AUTH)
    assert res.status_code == 405


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_accepts_gestor_session(client, _clear_outbox):
    from django.core import mail

    from accounts.tests.factories import GestorFactory

    gestor = GestorFactory()
    client.force_login(gestor)
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.post(reverse("competicion:api:cierre_enviar", args=[m.id]))
    assert res.status_code == 200
    assert len(mail.outbox) == 1


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_endpoint_redirects_on_html_accept(client, _clear_outbox):
    """Cuando el POST viene de un <form> del navegador (Accept text/html),
    redirige a /competicion/resultados/ con un mensaje flash en lugar de
    devolver JSON."""
    from accounts.tests.factories import GestorFactory

    gestor = GestorFactory()
    client.force_login(gestor)
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.post(
        reverse("competicion:api:cierre_enviar", args=[m.id]),
        HTTP_ACCEPT="text/html,application/xhtml+xml,application/xml;q=0.9",
    )
    assert res.status_code == 302
    assert res.url == reverse("competicion:manage_results")
