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
def test_tiebreak_keeps_shared_position():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups, result_home=0, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m2, home=0, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m2, home=0, away=0, earned=3)
    PredictionFactory(player=c, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=c, match=m2, home=1, away=1, earned=0)

    rows = {r.name: r for r in standings()}
    assert rows["Ana"].position == 1
    assert rows["Borja"].position == 1
    assert rows["Ana"].is_tied is True
    assert rows["Borja"].is_tied is True
    assert rows["Ana"].is_first_in_tie is True
    assert rows["Borja"].is_first_in_tie is False
    assert rows["Carla"].position == 2
    assert rows["Carla"].is_tied is False
    assert rows["Carla"].is_first_in_tie is True


@pytest.mark.django_db
def test_dense_ranking_no_gap_after_tie():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=c, match=m1, home=0, away=1, earned=0)

    rows = {r.name: r for r in standings()}
    assert rows["Ana"].position == 1
    assert rows["Borja"].position == 1
    assert rows["Carla"].position == 2  # densa, sin saltos


@pytest.mark.django_db
def test_alphabetical_only_visual_within_tie():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    z = UserFactory(name="Zoe", email="z@e.com")
    a = UserFactory(name="Ana", email="a@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=z, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)

    rows = standings()
    same_pos = [r for r in rows if r.pts == 3]
    assert same_pos[0].name == "Ana"
    assert same_pos[0].is_first_in_tie is True
    assert same_pos[1].name == "Zoe"
    assert same_pos[1].is_first_in_tie is False
    assert same_pos[0].position == same_pos[1].position == 1


@pytest.mark.django_db
def test_is_tied_false_when_unique():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=0, away=1, earned=0)

    rows = {r.name: r for r in standings()}
    assert rows["Ana"].is_tied is False
    assert rows["Ana"].is_first_in_tie is True
    assert rows["Borja"].is_tied is False
    assert rows["Borja"].is_first_in_tie is True


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


@pytest.mark.django_db
def test_streak_counts_consecutive_recent_hits():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="ana@e.com")
    now = timezone.now()
    m1 = MatchFactory(
        round=groups,
        kickoff=now - timedelta(days=3),
        finished_at=now - timedelta(days=3),
        result_home=1,
        result_away=0,
    )
    m2 = MatchFactory(
        round=groups,
        kickoff=now - timedelta(days=2),
        finished_at=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m3 = MatchFactory(
        round=groups,
        kickoff=now - timedelta(days=1),
        finished_at=now - timedelta(days=1),
        result_home=1,
        result_away=0,
    )
    PredictionFactory(player=ana, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m2, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m3, home=1, away=0, earned=3)

    s = standings()
    me = next(r for r in s if r.name == "Ana")
    assert me.streak == 3


@pytest.mark.django_db
def test_streak_breaks_on_fail():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="ana@e.com")
    now = timezone.now()
    m_old = MatchFactory(
        round=groups,
        kickoff=now - timedelta(days=2),
        finished_at=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m_recent = MatchFactory(
        round=groups,
        kickoff=now - timedelta(days=1),
        finished_at=now - timedelta(days=1),
        result_home=2,
        result_away=2,
    )
    PredictionFactory(player=ana, match=m_old, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m_recent, home=0, away=3, earned=0)

    s = standings()
    me = next(r for r in s if r.name == "Ana")
    assert me.streak == 0


@pytest.mark.django_db
def test_standings_scope_by_round_filters_predictions():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="OCT", order=3)
    ana = UserFactory(name="Ana", email="ana@e.com")
    luis = UserFactory(name="Luis", email="luis@e.com")
    m_grp = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_oct = MatchFactory(round=r16, matchday=None, result_home=2, result_away=1)
    PredictionFactory(player=ana, match=m_grp, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m_oct, home=0, away=0, earned=0)
    PredictionFactory(player=luis, match=m_grp, home=0, away=0, earned=0)
    PredictionFactory(player=luis, match=m_oct, home=2, away=1, earned=7)

    grp_rows = {r.name: r.pts for r in standings(round_id="groups")}
    oct_rows = {r.name: r.pts for r in standings(round_id="r16")}
    assert grp_rows["Ana"] == 3
    assert grp_rows["Luis"] == 0
    assert oct_rows["Ana"] == 0
    assert oct_rows["Luis"] == 7


@pytest.mark.django_db
def test_standings_scope_by_matchday_filters_predictions():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="ana@e.com")
    m_j1 = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_j2 = MatchFactory(round=grp, matchday=2, result_home=0, result_away=0)
    PredictionFactory(player=ana, match=m_j1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m_j2, home=0, away=0, earned=3)

    j1 = {r.name: r.pts for r in standings(round_id="groups", matchday=1)}
    j2 = {r.name: r.pts for r in standings(round_id="groups", matchday=2)}
    assert j1["Ana"] == 3
    assert j2["Ana"] == 3


@pytest.mark.django_db
def test_standings_scope_skips_streak_and_trend():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="ana@e.com")
    now = timezone.now()
    m1 = MatchFactory(
        round=grp,
        matchday=1,
        kickoff=now - timedelta(days=2),
        finished_at=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m2 = MatchFactory(
        round=grp,
        matchday=1,
        kickoff=now - timedelta(days=1),
        finished_at=now - timedelta(days=1),
        result_home=1,
        result_away=0,
    )
    PredictionFactory(player=ana, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m2, home=1, away=0, earned=3)

    scoped = next(r for r in standings(round_id="groups", matchday=1) if r.name == "Ana")
    assert scoped.streak == 0
    assert scoped.trend == "flat"


@pytest.mark.django_db
def test_exact_hits_uses_match_snapshot_not_current_round_points():
    """Un partido resuelto con points=3 sigue contando como exacto aunque
    ahora la ronda valga 5."""
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    u = UserFactory(is_jugador=True, is_active=True)
    m = MatchFactory(
        round=groups,
        result_home=1,
        result_away=0,
    )
    PredictionFactory(player=u, match=m, home=1, away=0, earned=3)

    # Cambia el valor actual de la ronda
    groups.points = 5
    groups.save()

    rows = standings()
    me = next(r for r in rows if r.player_id == u.id)
    assert me.exact_hits == 1


@pytest.mark.django_db
def test_trend_up_when_position_improved_after_last_match():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    leader = UserFactory(name="Leader", email="l@e.com")
    chaser = UserFactory(name="Chaser", email="c@e.com")
    now = timezone.now()
    m_old = MatchFactory(
        round=groups,
        kickoff=now - timedelta(days=2),
        finished_at=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m_recent = MatchFactory(
        round=groups,
        kickoff=now - timedelta(days=1),
        finished_at=now - timedelta(days=1),
        result_home=1,
        result_away=0,
    )
    PredictionFactory(player=leader, match=m_old, home=1, away=0, earned=3)
    PredictionFactory(player=chaser, match=m_old, home=0, away=1, earned=0)
    PredictionFactory(player=leader, match=m_recent, home=0, away=1, earned=0)
    PredictionFactory(player=chaser, match=m_recent, home=1, away=0, earned=3)

    s = standings()
    chaser_row = next(r for r in s if r.name == "Chaser")
    leader_row = next(r for r in s if r.name == "Leader")
    assert chaser_row.trend == "up"
    assert leader_row.trend == "down"


@pytest.mark.django_db
def test_standings_player_ids_filters_to_subset():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="a@e.com")
    luis = UserFactory(name="Luis", email="l@e.com")
    zoe = UserFactory(name="Zoe", email="z@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=ana, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=luis, match=m1, home=0, away=1, earned=0)
    PredictionFactory(player=zoe, match=m1, home=1, away=0, earned=3)

    rows = standings(player_ids=[ana.id, zoe.id])
    ids = [r.player_id for r in rows]
    assert ana.id in ids
    assert zoe.id in ids
    assert luis.id not in ids


@pytest.mark.django_db
def test_standings_player_ids_recomputes_positions_from_one():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    leader = UserFactory(name="Leader", email="lead@e.com")
    mid = UserFactory(name="Mid", email="mid@e.com")
    bottom = UserFactory(name="Bot", email="bot@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=leader, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=mid, match=m1, home=1, away=2, earned=1)
    PredictionFactory(player=bottom, match=m1, home=0, away=1, earned=0)

    rows = standings(player_ids=[mid.id, bottom.id])
    by_name = {r.name: r for r in rows}
    assert by_name["Mid"].position == 1
    assert by_name["Bot"].position == 2


@pytest.mark.django_db
def test_standings_player_ids_empty_returns_empty():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    UserFactory(name="Ana", email="a@e.com")
    rows = standings(player_ids=[])
    assert rows == []


@pytest.mark.django_db
def test_standings_player_ids_combined_with_scope():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="a@e.com")
    luis = UserFactory(name="Luis", email="l@e.com")
    m_j1 = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_j2 = MatchFactory(round=grp, matchday=2, result_home=0, result_away=0)
    PredictionFactory(player=ana, match=m_j1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m_j2, home=0, away=0, earned=3)
    PredictionFactory(player=luis, match=m_j1, home=1, away=0, earned=3)
    PredictionFactory(player=luis, match=m_j2, home=0, away=0, earned=3)

    rows = standings(round_id="groups", matchday=1, player_ids=[ana.id])
    assert len(rows) == 1
    assert rows[0].name == "Ana"
    assert rows[0].pts == 3


@pytest.mark.django_db
def test_standings_player_ids_includes_zero_pts_players():
    """Jugadores del grupo sin predicciones siguen apareciendo con 0 pts."""
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="A", email="a@e.com")
    b = UserFactory(name="B", email="b@e.com")
    rows = standings(player_ids=[a.id, b.id])
    ids = {r.player_id for r in rows}
    assert ids == {a.id, b.id}
    assert all(r.pts == 0 for r in rows)


@pytest.mark.django_db
def test_standings_round_ids_aggregates_multiple_rounds():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    user = UserFactory(name="Ana")
    m_grp = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_r32 = MatchFactory(round=r32, matchday=None, result_home=2, result_away=0)
    m_r16 = MatchFactory(round=r16, matchday=None, result_home=1, result_away=1)
    PredictionFactory(player=user, match=m_grp, earned=3)
    PredictionFactory(player=user, match=m_r32, earned=5)
    PredictionFactory(player=user, match=m_r16, earned=7)

    rows = {r.name: r.pts for r in standings(round_ids=["r32", "r16"])}
    assert rows["Ana"] == 12  # 5+7, sin contar grupos


@pytest.mark.django_db
def test_standings_round_id_and_round_ids_are_mutually_exclusive():
    with pytest.raises(ValueError):
        standings(round_id="groups", round_ids=["r32", "r16"])


@pytest.mark.django_db
def test_third_place_match_counts_in_general_and_finals_scope():
    final_round = RoundFactory(id="final", label="Final", short="FIN", points=25, order=6)
    player = UserFactory(name="Ana", is_jugador=True)
    # Partido del 3.er puesto: misma ronda `final`, sin matchday, resuelto.
    third = MatchFactory(
        round=final_round,
        group="3.º y 4.º puesto",
        matchday=None,
        bracket_code="M104",
        result_home=2,
        result_away=1,
    )
    PredictionFactory(player=player, match=third, earned=25)

    general = {r.player_id: r.pts for r in standings()}
    assert general[player.id] == 25

    finals = {r.player_id: r.pts for r in standings(round_ids=("r16", "qf", "sf", "final"))}
    assert finals[player.id] == 25
