from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from accounts.tests.factories import GestorFactory, UserFactory
from competition.services.resolve import resolve_match
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
    TeamFactory,
)


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_dashboard_shows_matches(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_predict_post_creates_prediction(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    assert m.predictions.filter(player=u, home=2, away=1).exists()


@pytest.mark.django_db
def test_predict_post_rejected_when_live(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=1))  # live
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 1, "away": 0})
    assert r.status_code == 403


@pytest.mark.django_db
def test_manage_results_requires_gestor(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    r = client.get(reverse("competicion:manage_results"))
    assert r.status_code == 302  # redirect to dashboard


@pytest.mark.django_db
def test_official_post_resolves_match(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=3))
    r = client.post(reverse("competicion:official", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    m.refresh_from_db()
    assert (m.result_home, m.result_away) == (2, 1)


@pytest.mark.django_db
def test_predict_forbidden_for_non_jugador(client):
    gestor_puro = GestorFactory(must_change_password=False, is_jugador=False)
    client.force_login(gestor_puro)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 1, "away": 0})
    assert r.status_code == 403


@pytest.mark.django_db
def test_dashboard_does_not_link_non_jugador_to_predict(client):
    gestor_puro = GestorFactory(must_change_password=False, is_jugador=False)
    client.force_login(gestor_puro)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 200
    predict_url = reverse("competicion:predict", args=[m.id])
    assert predict_url.encode() not in r.content


@pytest.mark.django_db
def test_detail_redirects_when_match_still_editable(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.get(reverse("competicion:detail", args=[m.id]))
    assert r.status_code == 302


@pytest.mark.django_db
def test_detail_lists_all_predictions_when_match_live(client):
    me = UserFactory(must_change_password=False, name="Ana")
    bettor = UserFactory(must_change_password=False, name="Bruno")
    UserFactory(must_change_password=False, name="Carla")  # jugadora sin apuesta
    client.force_login(me)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))  # live
    PredictionFactory(player=me, match=m, home=2, away=1)
    PredictionFactory(player=bettor, match=m, home=0, away=0)

    r = client.get(reverse("competicion:detail", args=[m.id]))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Ana" in body
    assert "Bruno" in body
    assert "Carla" in body  # presente como "no apostó"
    assert "2-1" in body
    assert "0-0" in body
    assert "no apostó" in body
    # Sin resultado oficial: ningún chip de puntos
    assert "pts" not in body


@pytest.mark.django_db
def test_detail_shows_points_and_exact_when_match_done(client):
    me = UserFactory(must_change_password=False, name="Ana")
    other = UserFactory(must_change_password=False, name="Bruno")
    failed = UserFactory(must_change_password=False, name="Carla")
    client.force_login(me)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=3))
    PredictionFactory(player=me, match=m, home=2, away=1)  # exacto
    PredictionFactory(player=other, match=m, home=3, away=2)  # acierta resultado (1)
    PredictionFactory(player=failed, match=m, home=0, away=2)  # falla
    resolve_match(m, home=2, away=1, actor=me)

    r = client.get(reverse("competicion:detail", args=[m.id]))
    assert r.status_code == 200
    body = r.content.decode()
    assert "+3 pts" in body
    assert "exacto" in body
    assert "+1 pts" in body
    assert "0 pts" in body


@pytest.mark.django_db
def test_detail_requires_login(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=3))
    r = client.get(reverse("competicion:detail", args=[m.id]))
    assert r.status_code == 302


@pytest.mark.django_db
def test_detail_marks_exact_via_applied_snapshot(client):
    """La marca 'exacto' se decide contra exact_points_applied (snapshot del
    partido), no contra round.points actual. Si el gestor sube los puntos
    de la ronda después de resolver, los exactos antiguos siguen siendo exactos."""
    me = UserFactory(must_change_password=False, name="Ana")
    client.force_login(me)
    grp = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=3))
    PredictionFactory(player=me, match=m, home=2, away=1)
    resolve_match(m, home=2, away=1, actor=me)

    grp.points = 99
    grp.save()

    r = client.get(reverse("competicion:detail", args=[m.id]))
    assert r.status_code == 200
    assert r.context["round_points"] == 3
    me_row = next(row for row in r.context["rows"] if row.get("is_me"))
    assert me_row["exact"] is True


@pytest.mark.django_db
def test_dashboard_shows_matchday_subselector_for_groups(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    # Varios partidos por jornada para verificar que el sub-selector
    # no se duplica (regresión: .distinct() arrastra el ordering por kickoff).
    for md in (1, 2, 3):
        for _ in range(4):
            MatchFactory(
                round=grp,
                matchday=md,
                home=TeamFactory(),
                away=TeamFactory(),
                kickoff=timezone.now() + timedelta(days=md, hours=_),
            )
    r = client.get(reverse("competicion:dashboard") + "?round=groups")
    body = r.content.decode()
    assert body.count("matchday=1") == 1
    assert body.count("matchday=2") == 1
    assert body.count("matchday=3") == 1


@pytest.mark.django_db
def test_dashboard_filters_by_matchday(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    j1_home = TeamFactory(code="J1H", name="J1HomeTeam")
    j2_home = TeamFactory(code="J2H", name="J2HomeTeam")
    MatchFactory(
        round=grp,
        matchday=1,
        home=j1_home,
        away=TeamFactory(),
        kickoff=timezone.now() + timedelta(days=1),
    )
    MatchFactory(
        round=grp,
        matchday=2,
        home=j2_home,
        away=TeamFactory(),
        kickoff=timezone.now() + timedelta(days=8),
    )
    r = client.get(reverse("competicion:dashboard") + "?round=groups&matchday=1")
    body = r.content.decode()
    assert "J1HomeTeam" in body
    assert "J2HomeTeam" not in body


@pytest.mark.django_db
def test_dashboard_renders_scope_leaderboard_tab_for_matchday(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    MatchFactory(
        round=grp,
        matchday=1,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=timezone.now() + timedelta(days=1),
    )
    r = client.get(reverse("competicion:dashboard") + "?round=groups&matchday=1")
    body = r.content.decode()
    assert "lb-scope-global" in body
    assert "lb-scope-local" in body
    assert "Jornada 1" in body


@pytest.mark.django_db
def test_dashboard_scope_tab_uses_round_label_outside_groups(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="OCT", order=3)
    MatchFactory(
        round=r16,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=timezone.now() + timedelta(days=20),
    )
    r = client.get(reverse("competicion:dashboard") + "?round=r16")
    body = r.content.decode()
    assert "lb-scope-local" in body
    # Sin jornada activa: la pestaña usa el `short` (o label) de la ronda.
    assert "OCT" in body


@pytest.mark.django_db
def test_dashboard_no_locked_banner_for_future_matchday(client):
    """Sin gate de jornada: J2 nunca aparece bloqueada aunque J1 esté pendiente."""
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    with freeze_time("2026-06-09 10:00:00", tz_offset=0):
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=timezone.now() + timedelta(days=2),
        )
        MatchFactory(
            round=grp,
            matchday=2,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=timezone.now() + timedelta(days=9),
        )
        r = client.get(reverse("competicion:dashboard") + "?round=groups&matchday=2")
        body = r.content.decode().lower()
        assert "bloqueada" not in body and "se desbloquea" not in body


@pytest.mark.django_db
def test_dashboard_passes_first_announcement_id_when_pending(client):
    from announcements.models import WinnerAnnouncement

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a1 = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
    WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=10)
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 200
    assert r.context["first_announcement_id"] == a1.id


@pytest.mark.django_db
def test_dashboard_omits_first_announcement_id_when_all_seen(client):
    from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a1 = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
    WinnerAnnouncementSeen.objects.create(announcement=a1, user=u)
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 200
    assert r.context["first_announcement_id"] is None


@pytest.mark.django_db
def test_dashboard_first_announcement_id_is_oldest_pending(client):
    from announcements.models import WinnerAnnouncement

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    older = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
    WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=10)
    r = client.get(reverse("competicion:dashboard"))
    assert r.context["first_announcement_id"] == older.id


@pytest.mark.django_db
def test_dashboard_ko_view_flag_for_groups(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    r = client.get(reverse("competicion:dashboard") + "?round=groups")
    assert r.status_code == 200
    assert r.context["is_ko_view"] is False


@pytest.mark.django_db
def test_dashboard_ko_view_flag_for_r32(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    rounds_data = [
        ("r32", "Dieciseisavos", "R32", 5, 2),
        ("r16", "Octavos", "R16", 7, 3),
        ("qf", "Cuartos", "QF", 10, 4),
        ("sf", "Semifinales", "SF", 15, 5),
        ("final", "Final", "FIN", 25, 6),
    ]
    for rid, label, short, pts, order in rounds_data:
        RoundFactory(id=rid, points=pts, label=label, short=short, order=order)
    from competition.models import Round
    r32 = Round.objects.get(id="r32")
    MatchFactory(round=r32, bracket_code="M73", kickoff=timezone.now() + timedelta(days=10))

    r = client.get(reverse("competicion:dashboard") + "?round=r32")
    assert r.status_code == 200
    assert r.context["is_ko_view"] is True
    assert r.context["active_ko_id"] == "r32"
    assert len(r.context["ko_rounds"]) == 5
    assert [k["round"].id for k in r.context["ko_rounds"]] == ["r32", "r16", "qf", "sf", "final"]


@pytest.mark.django_db
def test_dashboard_ko_matches_have_feeds_into_code(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    RoundFactory(id="qf", points=10, label="Cuartos", short="QF", order=4)
    RoundFactory(id="sf", points=15, label="Semifinales", short="SF", order=5)
    final = RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)

    MatchFactory(
        round=r32,
        bracket_code="M73",
        kickoff=timezone.now() + timedelta(days=10),
    )
    MatchFactory(
        round=r16,
        bracket_code="M89",
        home=None,
        away=None,
        home_slot="WM73",
        away_slot="WM74",
        kickoff=timezone.now() + timedelta(days=15),
    )
    MatchFactory(
        round=final,
        bracket_code="M104",
        home=None,
        away=None,
        home_slot="WM101",
        away_slot="WM102",
        kickoff=timezone.now() + timedelta(days=30),
    )

    r = client.get(reverse("competicion:dashboard") + "?round=r32")
    assert r.status_code == 200
    matches_by_code = {
        m.bracket_code: m
        for entry in r.context["ko_rounds"]
        for m in entry["matches"]
    }
    assert matches_by_code["M73"].feeds_into_code == "M89"
    assert matches_by_code["M104"].feeds_into_code is None
