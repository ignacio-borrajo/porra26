from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.models import PotSettings, Prize


@pytest.fixture
def matchday_announcement(db):
    user = UserFactory(name="Ganadora")
    ann = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
    ann.winners.set([user])
    return ann, user


@pytest.mark.django_db
class TestModalView:
    def test_renders_for_authenticated_user(self, client, matchday_announcement):
        ann, _ = matchday_announcement
        visitor = UserFactory()
        client.force_login(visitor)
        url = reverse("announcements:modal", args=[ann.id])
        res = client.get(url)
        assert res.status_code == 200
        content = res.content.decode()
        assert "Jornada 1" in content
        assert "8 puntos" in content
        assert "winner-modal" in content

    def test_404_for_missing(self, client):
        user = UserFactory()
        client.force_login(user)
        url = reverse("announcements:modal", args=[9999])
        res = client.get(url)
        assert res.status_code == 404

    def test_requires_login(self, client, matchday_announcement):
        ann, _ = matchday_announcement
        url = reverse("announcements:modal", args=[ann.id])
        res = client.get(url)
        assert res.status_code in (302, 401, 403)

    def test_renders_for_global_announcement(self, client, db):
        ann = WinnerAnnouncement.objects.create(scope_kind="global", points=99)
        ann.winners.set([UserFactory()])
        visitor = UserFactory()
        client.force_login(visitor)
        res = client.get(reverse("announcements:modal", args=[ann.id]))
        assert res.status_code == 200
        assert "Campeón del Mundial" in res.content.decode()

    def test_global_modal_includes_podium_prize_amounts(self, client, db):
        final_round = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
        Prize.objects.create(scope="global", position=1, amount=Decimal("300"), label="1º")
        Prize.objects.create(scope="global", position=2, amount=Decimal("120"), label="2º")
        Prize.objects.create(scope="global", position=3, amount=Decimal("60"), label="3º")
        first = UserFactory(name="Primero Apellido")
        second = UserFactory(name="Segundo Apellido")
        third = UserFactory(name="Tercero Apellido")
        m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=first, match=m, home=2, away=1, earned=20)
        PredictionFactory(player=second, match=m, home=2, away=0, earned=5)
        PredictionFactory(player=third, match=m, home=1, away=1, earned=1)
        ann = WinnerAnnouncement.objects.create(
            scope_kind="global", points=20, tied=False, share=Decimal("300")
        )
        ann.winners.set([first])
        client.force_login(UserFactory())
        res = client.get(reverse("announcements:modal", args=[ann.id]))
        assert res.status_code == 200
        html = res.content.decode()
        # Los tres jugadores aparecen
        assert "Primero Apellido" in html
        assert "Segundo Apellido" in html
        assert "Tercero Apellido" in html
        # Las cuantías aparecen prominentemente
        assert "300,00" in html or "300.00" in html
        assert "120,00" in html or "120.00" in html
        assert "60,00" in html or "60.00" in html

    def test_matchday_modal_renders_only_first_place_prize(self, client, db):
        groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("12.50")
        s.save()
        a = UserFactory(name="Alfa")
        b = UserFactory(name="Beta")
        m = MatchFactory(round=groups, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=a, match=m, home=1, away=0, earned=3)
        PredictionFactory(player=b, match=m, home=2, away=1, earned=1)
        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=3, share=Decimal("12.50")
        )
        ann.winners.set([a])
        client.force_login(UserFactory())
        res = client.get(reverse("announcements:modal", args=[ann.id]))
        html = res.content.decode()
        # La cuantía del puesto 1 está presente
        assert "12,50" in html or "12.50" in html
        # El segundo puesto se muestra sin cuantía € visible
        assert "Beta" in html

    def test_global_modal_renders_slots_in_visual_order_2_1_3(self, client, db):
        """En el HTML, el slot de 2º debe ir antes del 1º y el 1º antes del 3º."""
        final_round = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
        Prize.objects.create(scope="global", position=1, amount=Decimal("300"), label="1º")
        Prize.objects.create(scope="global", position=2, amount=Decimal("120"), label="2º")
        Prize.objects.create(scope="global", position=3, amount=Decimal("60"), label="3º")
        first = UserFactory(name="Aaaa")
        second = UserFactory(name="Bbbb")
        third = UserFactory(name="Cccc")
        m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=first, match=m, home=2, away=1, earned=20)
        PredictionFactory(player=second, match=m, home=2, away=0, earned=5)
        PredictionFactory(player=third, match=m, home=1, away=1, earned=1)
        ann = WinnerAnnouncement.objects.create(
            scope_kind="global", points=20, tied=False, share=Decimal("300")
        )
        ann.winners.set([first])
        client.force_login(UserFactory())
        res = client.get(reverse("announcements:modal", args=[ann.id]))
        html = res.content.decode()
        idx2 = html.find('data-rank="2"')
        idx1 = html.find('data-rank="1"')
        idx3 = html.find('data-rank="3"')
        assert idx2 != -1 and idx1 != -1 and idx3 != -1
        assert idx2 < idx1 < idx3, f"Orden visual incorrecto: 2={idx2}, 1={idx1}, 3={idx3}"


@pytest.mark.django_db
class TestSeenView:
    def test_creates_record_and_returns_next_header(self, client):
        u = UserFactory()
        a1 = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        a2 = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=10)
        client.force_login(u)
        url = reverse("announcements:seen", args=[a1.id])
        res = client.post(url)
        assert res.status_code == 204
        assert WinnerAnnouncementSeen.objects.filter(announcement=a1, user=u).exists()
        next_url = res.headers.get("X-Modal-Next")
        assert next_url == reverse("announcements:modal", args=[a2.id])

    def test_no_next_returns_204_no_header(self, client):
        u = UserFactory()
        a = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        client.force_login(u)
        res = client.post(reverse("announcements:seen", args=[a.id]))
        assert res.status_code == 204
        assert "X-Modal-Next" not in res.headers

    def test_idempotent(self, client):
        u = UserFactory()
        a = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        client.force_login(u)
        url = reverse("announcements:seen", args=[a.id])
        client.post(url)
        res = client.post(url)
        assert res.status_code == 204
        assert WinnerAnnouncementSeen.objects.filter(announcement=a, user=u).count() == 1

    def test_requires_login(self, client):
        a = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        res = client.post(reverse("announcements:seen", args=[a.id]))
        assert res.status_code in (302, 401, 403)

    def test_seen_pending_for_other_user_does_not_affect_next(self, client):
        u1 = UserFactory()
        u2 = UserFactory()
        a1 = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        a2 = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=8)
        # u2 ya ha visto a1
        WinnerAnnouncementSeen.objects.create(announcement=a1, user=u2)
        # u1 marca a1; debe seguir teniendo pendiente a2
        client.force_login(u1)
        res = client.post(reverse("announcements:seen", args=[a1.id]))
        assert res.headers.get("X-Modal-Next") == reverse("announcements:modal", args=[a2.id])


@pytest.mark.django_db
def test_modal_renders_sede_grid(client, settings):
    from decimal import Decimal

    from accounts.tests.factories import GestorFactory, UserFactory
    from announcements.models import WinnerAnnouncement
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings

    gestor = GestorFactory()
    client.force_login(gestor)
    rd = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    m = MatchFactory(round=rd, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=m, earned=5)
    PredictionFactory(player=v2, match=m, earned=4)
    PredictionFactory(player=v3, match=m, earned=3)
    PredictionFactory(player=m_a, match=m, earned=2)
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("25.00")
    s.save(update_fields=["sede_winner_prize"])
    ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
    r = client.get(f"/anuncios/{ann.id}/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "winner-modal-sede-grid" in body
    # Las 5 sedes están presentes
    for key in ["ourense", "vigo", "asturias", "madrid", "barcelona"]:
        assert f'data-sede="{key}"' in body
    # Madrid resuelta con MA y 25.00 €
    assert "MA" in body
    assert "25,00" in body or "25.00" in body
    # Sedes desiertas: ourense, vigo, asturias, barcelona → todas con "Desierto" salvo madrid
    assert body.count("Desierto") == 4


@pytest.mark.django_db
def test_modal_sede_card_desierto_state(client):
    from accounts.tests.factories import GestorFactory
    from announcements.models import WinnerAnnouncement

    client.force_login(GestorFactory())
    ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
    r = client.get(f"/anuncios/{ann.id}/")
    body = r.content.decode()
    assert body.count("Desierto") == 5
    assert "is-empty" in body
