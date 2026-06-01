from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
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
