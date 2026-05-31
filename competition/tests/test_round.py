import pytest

from competition.models import Round


@pytest.mark.django_db
def test_round_ordering_by_order_field():
    Round.objects.create(id="qf", label="Cuartos", short="QF", points=10, order=4)
    Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    ids = list(Round.objects.values_list("id", flat=True))
    assert ids == ["groups", "qf"]
