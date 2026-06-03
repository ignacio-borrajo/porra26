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
def test_detail_lists_all_predictions_when_match_closed(client):
    me = UserFactory(must_change_password=False, name="Ana")
    bettor = UserFactory(must_change_password=False, name="Bruno")
    UserFactory(must_change_password=False, name="Carla")  # jugadora sin apuesta
    client.force_login(me)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(minutes=30))  # closed
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
def test_dashboard_shows_locked_banner_for_blocked_matchday(client):
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
        assert "bloqueada" in body or "se desbloquea" in body


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
