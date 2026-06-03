import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen


@pytest.fixture
def matchday_announcement(db):
    user = UserFactory(name="Ganadora")
    ann = WinnerAnnouncement.objects.create(
        scope_kind="matchday", scope_matchday=1, points=8
    )
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


@pytest.mark.django_db
class TestSeenView:
    def test_creates_record_and_returns_next_header(self, client):
        u = UserFactory()
        a1 = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=8
        )
        a2 = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=2, points=10
        )
        client.force_login(u)
        url = reverse("announcements:seen", args=[a1.id])
        res = client.post(url)
        assert res.status_code == 204
        assert WinnerAnnouncementSeen.objects.filter(announcement=a1, user=u).exists()
        next_url = res.headers.get("X-Modal-Next")
        assert next_url == reverse("announcements:modal", args=[a2.id])

    def test_no_next_returns_204_no_header(self, client):
        u = UserFactory()
        a = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=8
        )
        client.force_login(u)
        res = client.post(reverse("announcements:seen", args=[a.id]))
        assert res.status_code == 204
        assert "X-Modal-Next" not in res.headers

    def test_idempotent(self, client):
        u = UserFactory()
        a = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=8
        )
        client.force_login(u)
        url = reverse("announcements:seen", args=[a.id])
        client.post(url)
        res = client.post(url)
        assert res.status_code == 204
        assert WinnerAnnouncementSeen.objects.filter(announcement=a, user=u).count() == 1

    def test_requires_login(self, client):
        a = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=8
        )
        res = client.post(reverse("announcements:seen", args=[a.id]))
        assert res.status_code in (302, 401, 403)

    def test_seen_pending_for_other_user_does_not_affect_next(self, client):
        u1 = UserFactory()
        u2 = UserFactory()
        a1 = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=8
        )
        a2 = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=2, points=8
        )
        # u2 ya ha visto a1
        WinnerAnnouncementSeen.objects.create(announcement=a1, user=u2)
        # u1 marca a1; debe seguir teniendo pendiente a2
        client.force_login(u1)
        res = client.post(reverse("announcements:seen", args=[a1.id]))
        assert res.headers.get("X-Modal-Next") == reverse("announcements:modal", args=[a2.id])
