from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import GestorFactory
from competition.models import Match
from competition.tests.factories import (
    MatchFactory,
    RoundFactory,
    TeamFactory,
)


@pytest.fixture
def grp():
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


def _closed_match(grp, *, hours_to_kickoff=1):
    """Crea un partido en estado `closed` (kickoff dentro de la ventana de 2h)."""
    return MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=timezone.now() + timedelta(hours=hours_to_kickoff),
    )


@pytest.mark.django_db
def test_official_get_includes_pending_count_and_has_next(client, grp):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    m1 = _closed_match(grp, hours_to_kickoff=1)
    _closed_match(grp, hours_to_kickoff=1)  # m2

    r = client.get(reverse("competicion:official", args=[m1.id]))

    assert r.status_code == 200
    assert r.context["pending_count"] == 2
    assert r.context["has_next"] is True
    # Es fragmento de modal, no extiende base.html.
    assert b"<html" not in r.content.lower()


@pytest.mark.django_db
def test_official_post_chain_returns_x_modal_next(client, grp):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    m1 = _closed_match(grp, hours_to_kickoff=1)
    m2 = _closed_match(grp, hours_to_kickoff=1)

    r = client.post(
        reverse("competicion:official", args=[m1.id]),
        {"home": 2, "away": 1, "chain": "1"},
    )

    assert r.status_code == 204
    assert r["X-Modal-Next"] == reverse("competicion:official", args=[m2.id])
    m1.refresh_from_db()
    assert (m1.result_home, m1.result_away) == (2, 1)


@pytest.mark.django_db
def test_official_post_chain_no_more_redirects(client, grp):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    m = _closed_match(grp, hours_to_kickoff=1)

    r = client.post(
        reverse("competicion:official", args=[m.id]),
        {"home": 1, "away": 0, "chain": "1"},
    )

    assert r.status_code == 200
    assert r["X-Modal-Redirect"] == reverse("competicion:manage_results")
    m.refresh_from_db()
    assert (m.result_home, m.result_away) == (1, 0)


@pytest.mark.django_db
def test_official_post_without_chain_redirects(client, grp):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    m = _closed_match(grp, hours_to_kickoff=1)

    r = client.post(
        reverse("competicion:official", args=[m.id]),
        {"home": 2, "away": 1},
    )

    assert r.status_code == 302
    assert r["Location"] == reverse("competicion:manage_results")
    m.refresh_from_db()
    assert (m.result_home, m.result_away) == (2, 1)


@pytest.mark.django_db
def test_manage_results_finalize_link_uses_modal_url(client, grp):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    m = _closed_match(grp, hours_to_kickoff=1)

    r = client.get(reverse("competicion:manage_results"))

    assert r.status_code == 200
    expected = f'data-modal-url="{reverse("competicion:official", args=[m.id])}"'
    assert expected.encode() in r.content
