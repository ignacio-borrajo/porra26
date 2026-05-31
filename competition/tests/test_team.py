import pytest
from competition.models import Team


@pytest.mark.django_db
def test_team_pk_is_code():
    t = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    assert t.pk == "ESP"
    assert str(t) == "España"
