from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory
from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen
from announcements.preview import build_preview
from pot.models import PotSettings


@pytest.mark.django_db
class TestPreviewPermissions:
    def test_redirects_player_to_dashboard(self, client):
        client.force_login(UserFactory(is_gestor=False))
        res = client.get(reverse("announcements:preview"))
        assert res.status_code == 302
        assert reverse("competicion:dashboard") in res.headers["Location"]

    def test_gestor_gets_200(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview"))
        assert res.status_code == 200


@pytest.mark.django_db
class TestBuildPreview:
    def test_matchday_single_uses_current_user(self):
        gestor = GestorFactory(name="Iñaki")
        ann, winners = build_preview("matchday", tied=False, current_user=gestor)
        assert ann.pk is None
        assert ann.scope_kind == "matchday"
        assert ann.scope_matchday == 1
        assert ann.tied is False
        assert winners == [gestor]

    def test_matchday_tied_picks_a_second_user(self):
        gestor = GestorFactory(name="Iñaki")
        other = UserFactory(name="Ana")
        ann, winners = build_preview("matchday", tied=True, current_user=gestor)
        assert ann.tied is True
        assert gestor in winners and other in winners
        assert len(winners) == 2

    def test_tied_falls_back_to_single_when_no_other_user(self):
        gestor = GestorFactory(name="Iñaki")
        ann, winners = build_preview("matchday", tied=True, current_user=gestor)
        assert winners == [gestor]
        assert ann.tied is False

    def test_ko_builds_announcement_without_extra_state(self):
        gestor = GestorFactory()
        ann, winners = build_preview("ko", tied=False, current_user=gestor)
        assert ann.scope_kind == "ko"
        assert ann.scope_matchday is None
        assert ann.title == "¡Ganador de las eliminatorias!"
        assert winners == [gestor]

    def test_global(self):
        gestor = GestorFactory()
        ann, _ = build_preview("global", tied=False, current_user=gestor)
        assert ann.scope_kind == "global"
        assert ann.title == "¡Campeón del Mundial!"

    def test_share_uses_pot_settings_single(self):
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("50")
        s.save()
        gestor = GestorFactory()
        ann, _ = build_preview("matchday", tied=False, current_user=gestor)
        assert ann.share == Decimal("50")

    def test_share_uses_pot_settings_split_when_tied(self):
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("50")
        s.save()
        gestor = GestorFactory()
        UserFactory(name="Ana")
        ann, _ = build_preview("matchday", tied=True, current_user=gestor)
        assert ann.share == Decimal("25")


@pytest.mark.django_db
class TestPreviewView:
    def test_renders_current_user_and_no_seen_url(self, client):
        gestor = GestorFactory(name="Iñaki Demo")
        client.force_login(gestor)
        res = client.get(reverse("announcements:preview") + "?scope=matchday&tied=0")
        assert res.status_code == 200
        html = res.content.decode()
        assert "Iñaki Demo" in html
        assert "data-seen-url" not in html
        assert "Vista previa" in html

    def test_tied_renders_two_winners_and_split_copy(self, client):
        gestor = GestorFactory(name="Iñaki Demo")
        UserFactory(name="Ana Demo")
        client.force_login(gestor)
        res = client.get(reverse("announcements:preview") + "?scope=matchday&tied=1")
        assert res.status_code == 200
        html = res.content.decode()
        assert "Iñaki Demo" in html
        assert "Ana Demo" in html
        assert "Empate en la cima" in html

    def test_ko_title(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=ko&tied=0")
        assert "¡Ganador de las eliminatorias!" in res.content.decode()

    def test_global_title(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=global&tied=0")
        assert "¡Campeón del Mundial!" in res.content.decode()

    def test_unknown_scope_returns_404(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=bogus")
        assert res.status_code == 404

    def test_does_not_persist_announcements(self, client):
        client.force_login(GestorFactory())
        before_ann = WinnerAnnouncement.objects.count()
        before_seen = WinnerAnnouncementSeen.objects.count()
        client.get(reverse("announcements:preview") + "?scope=matchday&tied=0")
        client.get(reverse("announcements:preview") + "?scope=global&tied=1")
        assert WinnerAnnouncement.objects.count() == before_ann
        assert WinnerAnnouncementSeen.objects.count() == before_seen


@pytest.mark.django_db
def test_preview_sede_for_gestor(client):
    from decimal import Decimal

    from accounts.tests.factories import GestorFactory, UserFactory
    from pot.models import PotSettings

    UserFactory(name="A", sede="madrid")
    UserFactory(name="B", sede="vigo")
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("30.00")
    s.save(update_fields=["sede_winner_prize"])
    client.force_login(GestorFactory(sede="barcelona"))
    r = client.get("/anuncios/preview/?scope=sede")
    assert r.status_code == 200
    body = r.content.decode()
    assert "winner-modal-sede-grid" in body
    assert "Vista previa" in body


@pytest.mark.django_db
def test_preview_sede_forbidden_for_jugador(client):
    from accounts.tests.factories import UserFactory

    client.force_login(UserFactory())
    r = client.get("/anuncios/preview/?scope=sede")
    assert r.status_code in (302, 403)  # GestorRequiredMixin redirige o prohíbe
