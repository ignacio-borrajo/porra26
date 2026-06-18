from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
    TeamFactory,
)


@pytest.mark.django_db
def test_rankings_requires_login(client):
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_rankings_default_tab_is_general(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content


@pytest.mark.django_db
def test_rankings_general_tab_renders_podium(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=general")
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content


@pytest.mark.django_db
def test_rankings_tab_label_is_clasificacion(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    body = r.content.decode()
    assert "Clasificación" in body


@pytest.mark.django_db
def test_rankings_general_renders_matchday_selector(client):
    client.force_login(UserFactory(must_change_password=False))
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    now = timezone.now()
    for md in (1, 2):
        MatchFactory(
            round=grp,
            matchday=md,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=now + timedelta(days=md),
        )
    r = client.get(reverse("stats:rankings"))
    body = r.content.decode()
    assert "rankings-md-selector" in body
    assert "Jornada 1" in body
    assert "Jornada 2" in body


@pytest.mark.django_db
def test_rankings_scope_param_changes_standings(client):
    ana = UserFactory(name="Ana", email="ana@e.com", must_change_password=False)
    client.force_login(ana)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    now = timezone.now()
    m_j1 = MatchFactory(
        round=grp,
        matchday=1,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m_j2 = MatchFactory(
        round=grp,
        matchday=2,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=0,
        result_away=0,
    )
    PredictionFactory(player=ana, match=m_j1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m_j2, home=0, away=0, earned=3)

    r = client.get(reverse("stats:rankings") + "?tab=general&scope=groups:1")
    assert r.status_code == 200
    # El scope=groups:1 implica que la jornada 1 está activa
    assert b"scope=groups:1" in r.content


@pytest.mark.django_db
def test_rankings_general_groups_ko_rounds_into_fases_finales(client):
    me = UserFactory(name="Me", email="me@e.com", must_change_password=False)
    client.force_login(me)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    final = RoundFactory(id="final", points=20, label="Final", short="F", order=6)
    now = timezone.now()
    MatchFactory(
        round=grp,
        matchday=1,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=1),
    )
    MatchFactory(
        round=r32,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=2),
    )
    MatchFactory(
        round=final,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=3),
    )
    r = client.get(reverse("stats:rankings"))
    body = r.content.decode()
    assert "Jornada 1" in body
    assert "Dieciseisavos" in body
    assert "Fases Finales" in body
    # Octavos/cuartos/semis/final NO se muestran como opciones independientes.
    assert "Octavos" not in body
    assert "scope=r32:_" in body
    assert "scope=finals:_" in body


@pytest.mark.django_db
def test_rankings_scope_finals_sums_points_across_finals_rounds(client):
    ana = UserFactory(name="Ana", email="ana@e.com", must_change_password=False)
    client.force_login(ana)
    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    final = RoundFactory(id="final", points=20, label="Final", short="F", order=6)
    now = timezone.now()
    m_r16 = MatchFactory(
        round=r16,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m_final = MatchFactory(
        round=final,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=2,
    )
    PredictionFactory(player=ana, match=m_r16, home=1, away=0, earned=5)
    PredictionFactory(player=ana, match=m_final, home=2, away=2, earned=20)

    r = client.get(reverse("stats:rankings") + "?tab=general&scope=finals:_")
    assert r.status_code == 200
    body = r.content.decode()
    assert "scope=finals:_" in body
    assert "Fases Finales" in body
    assert "25" in body


@pytest.mark.django_db
def test_rankings_accepts_puesto_tab(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=puesto")
    assert r.status_code == 200
    assert b"Puesto" in r.content


@pytest.mark.django_db
def test_rankings_unknown_tab_falls_back_to_general(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=hack")
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content


@pytest.mark.django_db
def test_rankings_group_invalid_dim_returns_404(client):
    client.force_login(UserFactory())
    r = client.get("/stats/rankings/foo/bar/")
    assert r.status_code == 404


@pytest.mark.django_db
def test_rankings_group_invalid_key_returns_404(client):
    client.force_login(UserFactory())
    r = client.get("/stats/rankings/sede/atlantis/")
    assert r.status_code == 404


@pytest.mark.django_db
def test_rankings_group_requires_login(client):
    r = client.get("/stats/rankings/sede/madrid/")
    assert r.status_code == 302


@pytest.mark.django_db
def test_rankings_group_empty_group_returns_200(client):
    client.force_login(UserFactory(sede=""))
    r = client.get("/stats/rankings/sede/barcelona/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Barcelona" in body
    assert "Aún no hay jugadores" in body


@pytest.mark.django_db
def test_rankings_group_renders_podium_for_group_members(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    madrid_top = UserFactory(name="MaTop", email="mt@e.com", sede="madrid")
    madrid_mid = UserFactory(name="MaMid", email="mm@e.com", sede="madrid")
    other = UserFactory(name="Other", email="o@e.com", sede="vigo")
    PredictionFactory(player=madrid_top, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=madrid_mid, match=m, home=1, away=2, earned=1)
    PredictionFactory(player=other, match=m, home=1, away=0, earned=3)

    client.force_login(madrid_top)
    r = client.get("/stats/rankings/sede/madrid/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "podium-slot--1" in body
    assert "MaTop" in body
    assert "Other" not in body


@pytest.mark.django_db
def test_rankings_group_breadcrumb_links_back_to_tab(client):
    client.force_login(UserFactory(puesto="desarrollo"))
    r = client.get("/stats/rankings/puesto/desarrollo/")
    assert r.status_code == 200
    body = r.content.decode()
    assert 'href="/stats/rankings/?tab=puesto"' in body
    assert "Desarrollo" in body


@pytest.mark.django_db
def test_rankings_group_chip_present_when_user_in_group(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    me = UserFactory(name="Me", email="me@e.com", sede="madrid")
    PredictionFactory(player=me, match=m, home=1, away=0, earned=3)
    client.force_login(me)
    r = client.get("/stats/rankings/sede/madrid/")
    assert "Tú · " in r.content.decode()


@pytest.mark.django_db
def test_rankings_group_chip_absent_when_user_not_in_group(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    madrid_user = UserFactory(name="Mad", email="m@e.com", sede="madrid")
    me_vigo = UserFactory(name="Me", email="me@e.com", sede="vigo")
    PredictionFactory(player=madrid_user, match=m, home=1, away=0, earned=3)
    client.force_login(me_vigo)
    r = client.get("/stats/rankings/sede/madrid/")
    assert "Tú · " not in r.content.decode()


@pytest.mark.django_db
def test_rankings_sede_tab_rows_are_links(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=sede")
    body = r.content.decode()
    assert 'href="/stats/rankings/sede/madrid/"' in body
    assert 'href="/stats/rankings/sede/vigo/"' in body


@pytest.mark.django_db
def test_rankings_puesto_tab_rows_are_links(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=puesto")
    body = r.content.decode()
    assert 'href="/stats/rankings/puesto/desarrollo/"' in body


@pytest.mark.django_db
def test_rankings_dept_tab_rows_are_links(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=dept")
    body = r.content.decode()
    assert 'href="/stats/rankings/dept/nominas/"' in body


@pytest.mark.django_db
def test_rankings_unassigned_row_is_not_a_link(client):
    UserFactory(email="orphan@e.com", sede="")
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=sede")
    body = r.content.decode()
    assert "Sin asignar" in body
    assert 'href="/stats/rankings/sede/__none__/"' not in body


@pytest.mark.django_db
def test_rankings_header_links_to_historico(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    body = r.content.decode()
    assert reverse("stats:historico") in body
    assert "Histórico" in body
