import pytest

from competition.tests.factories import RoundFactory


@pytest.mark.django_db
def test_round_has_partial_points_default_one():
    r = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert r.partial_points == 1


@pytest.mark.django_db
def test_round_partial_points_can_be_customised():
    r = RoundFactory(id="final", points=20, partial_points=3, label="F", short="F", order=6)
    assert r.partial_points == 3
