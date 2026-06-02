from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory
from pot.models import PotSettings, Prize


@pytest.mark.django_db
def test_prizes_requires_gestor(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_prizes_get_renders_for_gestor(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_prizes_get_context_has_top3_and_settings(client):
    client.force_login(GestorFactory(must_change_password=False))
    Prize.objects.filter(scope="global").delete()
    Prize.objects.create(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    Prize.objects.create(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    Prize.objects.create(scope="global", position=3, amount=Decimal("96"), label="3er premio")
    settings = PotSettings.load()
    settings.matchday_winner_prize = Decimal("15.00")
    settings.save()

    r = client.get(reverse("pot:prizes"))
    ctx = r.context
    assert [p.position for p in ctx["prizes"]] == [1, 2, 3]
    assert ctx["settings"].matchday_winner_prize == Decimal("15.00")


@pytest.mark.django_db
def test_prizes_get_renders_inputs_for_each_prize(client):
    client.force_login(GestorFactory(must_change_password=False))
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    p2 = Prize.objects.create(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    p3 = Prize.objects.create(scope="global", position=3, amount=Decimal("96"), label="3er premio")

    r = client.get(reverse("pot:prizes"))
    content = r.content.decode("utf-8")
    assert f'name="amount_{p1.id}"' in content
    assert f'name="amount_{p2.id}"' in content
    assert f'name="amount_{p3.id}"' in content
    assert 'name="matchday_winner_prize"' in content
