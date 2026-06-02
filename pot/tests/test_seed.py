import pytest
from django.core.management import call_command

from pot.models import Prize


@pytest.mark.django_db
def test_seed_creates_only_global_prizes():
    call_command("loaddata", "fixtures/rounds.json")
    call_command("migrate", "pot", verbosity=0)
    globals_qs = Prize.objects.filter(scope="global").order_by("position")
    assert globals_qs.count() == 3
    assert [p.position for p in globals_qs] == [1, 2, 3]
    # Tras la data migration 0005 no debe quedar ningún premio scoped.
    assert Prize.objects.exclude(scope="global").count() == 0
