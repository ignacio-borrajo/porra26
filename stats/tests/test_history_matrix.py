from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import GestorFactory, UserFactory
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
    TeamFactory,
)
from stats.services.history_matrix import build_matrix


@pytest.mark.django_db
def test_only_matches_with_closed_betting_are_included():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    finished = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )
    open_match = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=1),
    )
    live_match = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(minutes=10),
    )

    matrix = build_matrix()
    match_ids = [m.id for m in matrix.matches]
    assert finished.id in match_ids
    assert live_match.id in match_ids
    assert open_match.id not in match_ids


@pytest.mark.django_db
def test_match_without_teams_is_excluded_even_if_kickoff_passed():
    grp = RoundFactory(id="r16", points=5, partial_points=1, short="16", order=2)
    now = timezone.now()
    MatchFactory(
        round=grp,
        home=None,
        away=None,
        kickoff=now - timedelta(minutes=5),
        home_slot="W-G1",
        away_slot="W-G2",
    )
    matrix = build_matrix()
    assert matrix.matches == []


@pytest.mark.django_db
def test_live_match_has_no_result_and_is_marked_unresolved():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    MatchFactory(
        round=grp,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="FRA"),
        kickoff=now - timedelta(minutes=20),
    )
    matrix = build_matrix()
    m = matrix.matches[0]
    assert m.resolved is False
    assert m.result_home is None
    assert m.result_away is None


@pytest.mark.django_db
def test_pending_cell_for_prediction_on_unresolved_match():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(minutes=10),
    )
    p = UserFactory(name="P", email="p@edisa.com")
    PredictionFactory(player=p, match=m, home=1, away=2, earned=None)

    matrix = build_matrix()
    cell = matrix.cells[p.id][m.id]
    assert cell.state == "pending"
    assert cell.home == 1 and cell.away == 2


@pytest.mark.django_db
def test_empty_cell_for_unresolved_match_when_no_prediction():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(minutes=10),
    )
    p = UserFactory(name="P", email="p@edisa.com")

    matrix = build_matrix()
    cell = matrix.cells[p.id][m.id]
    assert cell.state == "empty"
    assert cell.home is None and cell.away is None


@pytest.mark.django_db
def test_matches_ordered_by_kickoff():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    later = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(hours=1),
        result_home=0,
        result_away=0,
        finished_at=now,
    )
    earlier = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=1,
        finished_at=now - timedelta(days=1),
    )

    matrix = build_matrix()
    ordered_ids = [m.id for m in matrix.matches]
    assert ordered_ids == [earlier.id, later.id]


@pytest.mark.django_db
def test_players_ordered_by_standings_pts_desc():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=1,
        result_away=0,
        finished_at=now,
    )
    low = UserFactory(name="Low", email="low@edisa.com")
    high = UserFactory(name="High", email="high@edisa.com")
    PredictionFactory(player=low, match=m, home=2, away=2, earned=0)
    PredictionFactory(player=high, match=m, home=1, away=0, earned=3)

    matrix = build_matrix()
    names = [p.name for p in matrix.players]
    assert names.index("High") < names.index("Low")


@pytest.mark.django_db
def test_gestores_are_not_rows():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=1,
        result_away=0,
        finished_at=now,
    )
    player = UserFactory(name="Player", email="player@edisa.com")
    gestor = GestorFactory(name="Gestor", email="gestor@edisa.com", is_jugador=False)

    matrix = build_matrix()
    ids = [p.id for p in matrix.players]
    assert player.id in ids
    assert gestor.id not in ids


@pytest.mark.django_db
def test_cell_state_exact():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )
    p = UserFactory(name="P", email="p@edisa.com")
    PredictionFactory(player=p, match=m, home=2, away=1, earned=3)

    matrix = build_matrix()
    cell = matrix.cells[p.id][m.id]
    assert cell.state == "exact"
    assert cell.home == 2 and cell.away == 1


@pytest.mark.django_db
def test_cell_state_partial():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )
    p = UserFactory(name="P", email="p@edisa.com")
    PredictionFactory(player=p, match=m, home=3, away=1, earned=1)

    matrix = build_matrix()
    cell = matrix.cells[p.id][m.id]
    assert cell.state == "partial"


@pytest.mark.django_db
def test_cell_state_miss():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )
    p = UserFactory(name="P", email="p@edisa.com")
    PredictionFactory(player=p, match=m, home=0, away=0, earned=0)

    matrix = build_matrix()
    cell = matrix.cells[p.id][m.id]
    assert cell.state == "miss"


@pytest.mark.django_db
def test_cell_state_empty_when_no_prediction():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )
    p = UserFactory(name="P", email="p@edisa.com")

    matrix = build_matrix()
    cell = matrix.cells[p.id][m.id]
    assert cell.state == "empty"
    assert cell.home is None and cell.away is None


@pytest.mark.django_db
def test_totals_match_sum_of_earned():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    m1 = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
        finished_at=now,
    )
    m2 = MatchFactory(
        round=grp,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=2,
        finished_at=now,
    )
    p = UserFactory(name="P", email="p@edisa.com")
    PredictionFactory(player=p, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=p, match=m2, home=2, away=2, earned=3)

    matrix = build_matrix()
    assert matrix.totals[p.id] == 6


@pytest.mark.django_db
def test_match_carries_team_codes_and_result():
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    esp = TeamFactory(code="ESP", name="España", flag="🇪🇸")
    fra = TeamFactory(code="FRA", name="Francia", flag="🇫🇷")
    MatchFactory(
        round=grp,
        home=esp,
        away=fra,
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )

    matrix = build_matrix()
    m = matrix.matches[0]
    assert m.home_code == "ESP"
    assert m.away_code == "FRA"
    assert m.home_flag == "🇪🇸"
    assert m.away_flag == "🇫🇷"
    assert m.result_home == 2
    assert m.result_away == 1
    assert m.resolved is True
