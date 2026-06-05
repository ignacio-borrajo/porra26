from decimal import Decimal

import pytest

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.models import PotSettings
from pot.services.prizes import sede_winners


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.fixture
def prize_25(db):
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("25.00")
    s.save(update_fields=["sede_winner_prize"])
    return s


def _by_sede(result, key):
    return next(sw for sw in result if sw.sede_key == key)


@pytest.mark.django_db
def test_returns_six_entries_in_sede_choices_order(groups_round, prize_25):
    result = sede_winners()
    assert [sw.sede_key for sw in result] == [
        "ourense",
        "vigo",
        "asturias",
        "madrid",
        "barcelona",
        "latam",
    ]
    assert all(sw.status == "desierto" for sw in result)


@pytest.mark.django_db
def test_basic_two_sedes_with_clear_winners(groups_round, prize_25):
    madrid_a = UserFactory(name="MA", sede="madrid")
    vigo_a = UserFactory(name="VA", sede="vigo")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=madrid_a, match=m, earned=3)
    PredictionFactory(player=vigo_a, match=m, earned=3)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    vigo = _by_sede(result, "vigo")
    # Empate global → ambos están en top 3 → ambas sedes desiertas
    assert madrid.status == "desierto"
    assert vigo.status == "desierto"


@pytest.mark.django_db
def test_excludes_global_top3(groups_round, prize_25):
    # Ana lidera global y es de Madrid; Borja (Madrid) tiene menos pts
    # Resultado esperado: Madrid premia a Borja
    ana = UserFactory(name="Ana", sede="madrid")
    borja = UserFactory(name="Borja", sede="madrid")
    # 4 jugadores extra para llenar el top 3 global con gente que NO es Borja
    UserFactory(name="X1", sede="vigo")
    UserFactory(name="X2", sede="vigo")
    UserFactory(name="X3", sede="vigo")
    m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
    PredictionFactory(player=ana, match=m1, earned=3)
    PredictionFactory(player=ana, match=m2, earned=3)  # 6 pts global #1
    # Construir 2º y 3º global SIN que sean Borja
    p2 = UserFactory(name="P2", sede="barcelona")
    p3 = UserFactory(name="P3", sede="ourense")
    PredictionFactory(player=p2, match=m1, earned=3)
    PredictionFactory(player=p2, match=m2, earned=1)  # 4 pts global #2
    PredictionFactory(player=p3, match=m1, earned=3)  # 3 pts global #3
    PredictionFactory(player=borja, match=m1, earned=1)  # 1 pt
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "resolved"
    assert [u.id for u in madrid.users] == [borja.id]
    assert madrid.prize_per_user == Decimal("25.00")


@pytest.mark.django_db
def test_sede_with_all_players_in_global_top3(groups_round, prize_25):
    # Solo 3 jugadores con pts, todos de Madrid → Madrid desierta
    a = UserFactory(name="A", sede="madrid")
    b = UserFactory(name="B", sede="madrid")
    c = UserFactory(name="C", sede="madrid")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m, earned=3)
    PredictionFactory(player=b, match=m, earned=2)
    PredictionFactory(player=c, match=m, earned=1)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "desierto"


@pytest.mark.django_db
def test_tied_inside_sede(groups_round, prize_25):
    # Cuatro jugadores. Top 3 global son tres de vigo. Dos de madrid empatados.
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    m_b = UserFactory(name="MB", sede="madrid")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=m, earned=5)
    PredictionFactory(player=v2, match=m, earned=4)
    PredictionFactory(player=v3, match=m, earned=3)
    # Empate Madrid 1 pt + sin exactos + sin aciertos extra → quedan empatados
    PredictionFactory(player=m_a, match=m, home=9, away=9, earned=1)
    PredictionFactory(player=m_b, match=m, home=9, away=9, earned=1)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "resolved"
    assert {u.id for u in madrid.users} == {m_a.id, m_b.id}
    assert madrid.prize_per_user == Decimal("12.50")  # 25 / 2


@pytest.mark.django_db
def test_user_without_sede_ignored(groups_round, prize_25):
    nohome = UserFactory(name="Nadie", sede="")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=nohome, match=m, earned=3)
    result = sede_winners()
    assert all(sw.status == "desierto" for sw in result)


@pytest.mark.django_db
def test_sede_with_no_points_returns_desierto(groups_round, prize_25):
    UserFactory(name="X", sede="madrid")
    MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    result = sede_winners()
    assert _by_sede(result, "madrid").status == "desierto"


@pytest.mark.django_db
def test_prize_zero_when_setting_zero(groups_round):
    # Sin tocar PotSettings → sede_winner_prize por defecto = 0
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=m, earned=5)
    PredictionFactory(player=v2, match=m, earned=4)
    PredictionFactory(player=v3, match=m, earned=3)
    PredictionFactory(player=m_a, match=m, earned=1)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "resolved"
    assert [u.id for u in madrid.users] == [m_a.id]
    assert madrid.prize_per_user == Decimal("0")
