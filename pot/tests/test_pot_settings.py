import pytest
from pot.models import PotSettings


@pytest.mark.django_db
def test_load_creates_singleton():
    s = PotSettings.load()
    assert s.pk == 1
    assert s.per_player == 10


@pytest.mark.django_db
def test_load_returns_existing():
    s1 = PotSettings.load()
    s1.per_player = 15
    s1.save()
    s2 = PotSettings.load()
    assert s2.per_player == 15
