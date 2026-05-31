import pytest

from competition.services.score import score
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Grupos", short="GRP", order=1)


def _match_with_result(groups_round, rh, ra):
    return MatchFactory(round=groups_round, result_home=rh, result_away=ra)


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
def test_score_uses_round_points():
    final = RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)
    m = MatchFactory(round=final, result_home=1, result_away=0)
    pred = type("P", (), {"home": 1, "away": 0})()
    assert score(pred, m) == 25


@pytest.mark.django_db
def test_score_returns_none_for_unresolved(groups_round):
    m = MatchFactory(round=groups_round, result_home=None, result_away=None)
    pred = type("P", (), {"home": 1, "away": 0})()
    assert score(pred, m) is None
