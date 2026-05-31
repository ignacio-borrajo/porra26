import pytest
from accounts.tests.factories import UserFactory
from pot.models import Payment, PotSettings


@pytest.mark.django_db
def test_pot_total_uses_paid_players():
    PotSettings.objects.update_or_create(pk=1, defaults={"per_player": 10})
    a = UserFactory(); b = UserFactory(); c = UserFactory()
    Payment.objects.create(player=a, paid=True)
    Payment.objects.create(player=b, paid=False)
    Payment.objects.create(player=c, paid=True)

    from core.context_processors import app_context
    from django.test import RequestFactory
    rf = RequestFactory()
    ctx = app_context(rf.get("/"))
    assert ctx["pot_total"] == 20
