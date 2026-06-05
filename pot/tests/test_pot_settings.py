from decimal import Decimal

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


@pytest.mark.django_db
def test_matchday_winner_prize_defaults_to_zero():
    s = PotSettings.load()
    assert s.matchday_winner_prize == Decimal("0")


@pytest.mark.django_db
def test_matchday_winner_prize_is_persisted():
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("25.50")
    s.save()
    assert PotSettings.load().matchday_winner_prize == Decimal("25.50")


@pytest.mark.django_db
def test_maintenance_cost_defaults_to_zero():
    s = PotSettings.load()
    assert s.maintenance_cost == Decimal("0")


@pytest.mark.django_db
def test_maintenance_cost_is_persisted():
    s = PotSettings.load()
    s.maintenance_cost = Decimal("42.75")
    s.save()
    assert PotSettings.load().maintenance_cost == Decimal("42.75")


def test_potsettings_has_sede_winner_prize_default_zero(db):
    from decimal import Decimal
    from pot.models import PotSettings
    s = PotSettings.load()
    assert s.sede_winner_prize == Decimal("0")


def test_potsettings_sede_winner_prize_persists(db):
    from decimal import Decimal
    from pot.models import PotSettings
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("25.50")
    s.save(update_fields=["sede_winner_prize"])
    assert PotSettings.load().sede_winner_prize == Decimal("25.50")
