from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory
from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen
from announcements.preview import build_preview
from competition.tests.factories import RoundFactory
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

    def test_round_uses_first_ko_round(self):
        RoundFactory(id="groups", label="Fase de grupos", short="GRP", order=1)
        r16 = RoundFactory(id="r16", label="Octavos", short="R16", points=7, order=3)
        gestor = GestorFactory()
        ann, _ = build_preview("round", tied=False, current_user=gestor)
        assert ann.scope_kind == "round"
        assert ann.scope_round_id == r16.id
        assert ann.title == "¡Ganador de Octavos!"

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

    def test_round_title(self, client):
        RoundFactory(id="groups", label="Fase de grupos", short="GRP", order=1)
        RoundFactory(id="r16", label="Octavos", short="R16", points=7, order=3)
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=round&tied=0")
        assert "¡Ganador de Octavos!" in res.content.decode()

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
