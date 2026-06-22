from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.history import build_chart_payload


@pytest.mark.django_db
def test_chart_payload_builds_aligned_series():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="A")
    b = UserFactory(name="B")
    t0 = timezone.now()
    m1 = MatchFactory(round=grp, kickoff=t0, result_home=1, result_away=0, finished_at=t0)
    m2 = MatchFactory(
        round=grp, kickoff=t0 + timedelta(hours=1), result_home=2, result_away=2, finished_at=t0
    )
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=a, match=m2, earned=0)
    PredictionFactory(player=b, match=m1, earned=1)
    PredictionFactory(player=b, match=m2, earned=3)

    payload = build_chart_payload(a.id)
    assert payload["me"] == a.id
    assert payload["finished"] == 2

    by_id = {p["id"]: p for p in payload["players"]}
    # B termina líder (4 pts) y A segundo (3 pts)
    assert payload["players"][0]["id"] == b.id
    assert by_id[a.id]["pts"] == 3
    assert by_id[b.id]["pts"] == 4
    assert by_id[a.id]["rank"] == 2
    assert by_id[b.id]["rank"] == 1
    # series acumuladas alineadas a los 2 partidos
    assert by_id[a.id]["pts_hist"] == [3, 3]
    assert by_id[b.id]["pts_hist"] == [1, 4]
    # A va líder tras el primer partido y cede el liderato en el segundo
    assert by_id[a.id]["rank_hist"] == [1, 2]
    assert by_id[b.id]["rank_hist"] == [2, 1]


@pytest.mark.django_db
def test_chart_payload_empty_when_no_finished_matches():
    UserFactory(name="A")
    payload = build_chart_payload(1)
    assert payload["finished"] == 0
    # los jugadores activos aparecen con series vacías
    for p in payload["players"]:
        assert p["pts_hist"] == []
        assert p["rank_hist"] == []
