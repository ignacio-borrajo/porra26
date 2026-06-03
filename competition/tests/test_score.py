import pytest

from competition.services.score import score
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Grupos", short="GRP", order=1)


def _match_with_result(groups_round, rh, ra):
    return MatchFactory(
        round=groups_round,
        result_home=rh,
        result_away=ra,
        exact_points_applied=groups_round.points,
        partial_points_applied=groups_round.partial_points,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ph,pa,rh,ra,expected",
    [
        (2, 1, 2, 1, 3),
        (3, 1, 2, 1, 1),
        (0, 0, 1, 1, 1),
        (1, 2, 0, 3, 1),
        (2, 0, 0, 1, 0),
        (1, 1, 2, 0, 0),
    ],
)
def test_score_groups(groups_round, ph, pa, rh, ra, expected):
    m = _match_with_result(groups_round, rh, ra)
    pred = type("P", (), {"home": ph, "away": pa})()
    assert score(pred, m) == expected


@pytest.mark.django_db
def test_score_uses_exact_points_applied():
    final = RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)
    m = MatchFactory(
        round=final,
        result_home=1,
        result_away=0,
        exact_points_applied=25,
        partial_points_applied=1,
    )
    pred = type("P", (), {"home": 1, "away": 0})()
    assert score(pred, m) == 25


@pytest.mark.django_db
def test_score_uses_match_partial_points_applied():
    final = RoundFactory(id="final", points=20, partial_points=3, label="F", short="F", order=6)
    m = MatchFactory(
        round=final,
        result_home=2,
        result_away=1,
        exact_points_applied=20,
        partial_points_applied=3,
    )
    exact = type("P", (), {"home": 2, "away": 1})()
    partial = type("P", (), {"home": 3, "away": 1})()
    fail = type("P", (), {"home": 0, "away": 1})()
    assert score(exact, m) == 20
    assert score(partial, m) == 3
    assert score(fail, m) == 0


@pytest.mark.django_db
def test_score_partial_points_zero():
    r = RoundFactory(id="groups", points=3, partial_points=0, label="G", short="G", order=1)
    m = MatchFactory(
        round=r,
        result_home=1,
        result_away=0,
        exact_points_applied=3,
        partial_points_applied=0,
    )
    partial = type("P", (), {"home": 2, "away": 0})()
    assert score(partial, m) == 0


@pytest.mark.django_db
def test_score_returns_none_for_unresolved(groups_round):
    m = MatchFactory(round=groups_round, result_home=None, result_away=None)
    pred = type("P", (), {"home": 1, "away": 0})()
    assert score(pred, m) is None
