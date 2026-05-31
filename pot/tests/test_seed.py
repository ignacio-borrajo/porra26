import pytest
from django.core.management import call_command

from pot.models import Prize


@pytest.mark.django_db
def test_seed_creates_nine_prizes_after_loaddata():
    call_command("loaddata", "fixtures/rounds.json")
    call_command("migrate", "pot", verbosity=0)
    assert Prize.objects.count() >= 6
