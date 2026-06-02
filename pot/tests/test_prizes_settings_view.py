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


from accounts.models import AuditLog


@pytest.mark.django_db
def test_prizes_post_updates_top3_amounts(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")
    p2 = Prize.objects.create(scope="global", position=2, amount=0, label="2º premio")
    p3 = Prize.objects.create(scope="global", position=3, amount=0, label="3er premio")

    r = client.post(
        reverse("pot:prizes"),
        {
            f"amount_{p1.id}": "240",
            f"amount_{p2.id}": "144",
            f"amount_{p3.id}": "96",
            "matchday_winner_prize": "0",
        },
    )
    assert r.status_code == 302
    p1.refresh_from_db(); p2.refresh_from_db(); p3.refresh_from_db()
    assert p1.amount == Decimal("240")
    assert p2.amount == Decimal("144")
    assert p3.amount == Decimal("96")


@pytest.mark.django_db
def test_prizes_post_updates_matchday_winner_prize(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "0", "matchday_winner_prize": "25.50"},
    )
    assert PotSettings.load().matchday_winner_prize == Decimal("25.50")


@pytest.mark.django_db
def test_prizes_post_writes_audit_log(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "100", "matchday_winner_prize": "10"},
    )
    log = AuditLog.objects.filter(actor=g, action="prize_changed").first()
    assert log is not None
    assert log.target_type == "prize"


@pytest.mark.django_db
def test_prizes_post_ignores_invalid_amount(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=Decimal("50"), label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "not-a-number", "matchday_winner_prize": "10"},
    )
    p1.refresh_from_db()
    assert p1.amount == Decimal("50")  # sin cambio
    assert PotSettings.load().matchday_winner_prize == Decimal("10")  # otros sí


@pytest.mark.django_db
def test_prizes_post_rejects_negative_amount(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=Decimal("50"), label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "-10", "matchday_winner_prize": "-5"},
    )
    p1.refresh_from_db()
    assert p1.amount == Decimal("50")  # ignorado
    assert PotSettings.load().matchday_winner_prize == Decimal("0")  # default tras load (sin cambio si rechazamos)
