from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import Prediction
from competition.services.standings import standings
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_standings_orders_by_points():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="ana@e.com")
    luis = UserFactory(name="Luis", email="luis@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups, result_home=2, result_away=2)

    PredictionFactory(player=ana, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m2, home=0, away=0, earned=1)
    PredictionFactory(player=luis, match=m1, home=1, away=2, earned=0)
    PredictionFactory(player=luis, match=m2, home=2, away=2, earned=3)

    s = standings()
    pts_by_name = [(r.name, r.pts) for r in s]
    # Filtramos solo los que tienen >0 o que aparecen explícitamente
    assert ("Ana", 4) in pts_by_name
    assert ("Luis", 3) in pts_by_name
    # Orden: Ana primero, Luis después
    ana_pos = [r.position for r in s if r.name == "Ana"][0]
    luis_pos = [r.position for r in s if r.name == "Luis"][0]
    assert ana_pos < luis_pos


@pytest.mark.django_db
def test_standings_tiebreak_by_exact_then_hits_then_name():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    z = UserFactory(name="Zoe", email="z@e.com")
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups, result_home=0, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m2, home=2, away=2, earned=1)
    PredictionFactory(player=b, match=m1, home=2, away=0, earned=1)
    PredictionFactory(player=b, match=m2, home=0, away=0, earned=3)
    PredictionFactory(player=z, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=z, match=m2, home=0, away=0, earned=3)

    s = standings()
    # Zoe (2 exactos) -> primero. Ana y Borja empatados a 4 pts y 1 exacto, alfabético.
    top3_names = [r.name for r in s if r.pts > 0][:3]
    assert top3_names == ["Zoe", "Ana", "Borja"]


@pytest.mark.django_db
def test_standings_excludes_inactive_users():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    UserFactory(name="Ina", email="i@e.com", is_active=False)
    UserFactory(name="Act", email="a@e.com", is_active=True)
    s = standings()
    names = [r.name for r in s]
    assert "Act" in names
    assert "Ina" not in names


@pytest.mark.django_db
def test_non_jugador_user_excluded_from_standings():
    gestor_puro = UserFactory(is_jugador=False, is_gestor=True)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(days=2))
    m.result_home, m.result_away = 1, 0
    m.finished_at = timezone.now()
    m.save()
    Prediction.objects.create(player=gestor_puro, match=m, home=1, away=0, earned=3)

    rows = standings()
    assert all(r.player_id != gestor_puro.id for r in rows)


@pytest.mark.django_db
def test_jugador_with_zero_points_still_listed():
    u = UserFactory(is_jugador=True)
    rows = standings()
    assert any(r.player_id == u.id and r.pts == 0 for r in rows)
