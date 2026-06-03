import pytest

from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_match_points_applied_default_none():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    assert m.exact_points_applied is None
    assert m.partial_points_applied is None
