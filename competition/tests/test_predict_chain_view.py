from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.tests.factories import (
    MatchFactory,
    RoundFactory,
)


@pytest.fixture
def grp(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_get_includes_pending_count_and_has_next(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    m1 = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=2))
    r = client.get(reverse("competicion:predict", args=[m1.id]))
    assert r.status_code == 200
    assert r.context["pending_count"] == 2
    assert r.context["has_next"] is True


@pytest.mark.django_db
def test_get_has_next_false_when_only_current_pending(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.get(reverse("competicion:predict", args=[m.id]))
    assert r.status_code == 200
    assert r.context["pending_count"] == 1
    assert r.context["has_next"] is False


@pytest.mark.django_db
def test_post_without_chain_redirects_as_before(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    assert r["Location"] == reverse("competicion:dashboard")
    assert m.predictions.filter(player=u, home=2, away=1).exists()


@pytest.mark.django_db
def test_post_with_chain_and_next_returns_modal_next_header(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    current = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    nxt = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=2))
    r = client.post(
        reverse("competicion:predict", args=[current.id]),
        {"home": 2, "away": 1, "chain": "1"},
    )
    assert r.status_code == 204
    assert r["X-Modal-Next"] == reverse("competicion:predict", args=[nxt.id])
    assert current.predictions.filter(player=u, home=2, away=1).exists()


@pytest.mark.django_db
def test_post_with_chain_and_no_next_redirects_to_dashboard(client, grp):
    from django.contrib.messages import get_messages

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    only = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(
        reverse("competicion:predict", args=[only.id]),
        {"home": 1, "away": 0, "chain": "1"},
    )
    assert r.status_code == 200
    assert r["X-Modal-Redirect"] == reverse("competicion:dashboard")
    assert only.predictions.filter(player=u, home=1, away=0).exists()
    msgs = [m.message for m in get_messages(r.wsgi_request)]
    assert any("todos los partidos" in s for s in msgs)
