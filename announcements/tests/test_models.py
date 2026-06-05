import pytest
from django.db import IntegrityError

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen


@pytest.mark.django_db
class TestWinnerAnnouncementStr:
    def test_str_for_matchday(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=9)
        assert "2" in str(ann)

    def test_str_for_ko(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="ko", points=42)
        assert "eliminatoria" in str(ann)

    def test_str_for_global(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="global", points=50)
        assert "Mundial" in str(ann)

    def test_str_for_sede(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
        assert "sede" in str(ann).lower()


@pytest.mark.django_db
class TestWinnerAnnouncementTitle:
    def test_title_singular_matchday(self):
        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=8, tied=False
        )
        assert ann.title == "¡Ganador de la Jornada 1!"

    def test_title_plural_matchday(self):
        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=3, points=8, tied=True
        )
        assert ann.title == "¡Ganadores de la Jornada 3!"

    def test_title_singular_ko(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="ko", points=42, tied=False)
        assert ann.title == "¡Ganador de las eliminatorias!"

    def test_title_plural_ko(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="ko", points=42, tied=True)
        assert ann.title == "¡Ganadores de las eliminatorias!"

    def test_title_singular_global(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="global", points=99, tied=False)
        assert ann.title == "¡Campeón del Mundial!"

    def test_title_plural_global(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="global", points=99, tied=True)
        assert ann.title == "¡Campeones del Mundial!"

    def test_title_sede(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
        assert ann.title == "¡Ganadores por sede!"


@pytest.mark.django_db
class TestUniquenessConstraints:
    def test_uniqueness_constraint_matchday(self):
        WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=10)

    def test_uniqueness_constraint_ko(self):
        WinnerAnnouncement.objects.create(scope_kind="ko", points=42)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="ko", points=50)

    def test_uniqueness_constraint_global(self):
        WinnerAnnouncement.objects.create(scope_kind="global", points=99)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="global", points=100)

    def test_uniqueness_constraint_sede(self):
        WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="sede", points=0)

    def test_different_matchdays_allowed(self):
        WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=10)
        assert WinnerAnnouncement.objects.filter(scope_kind="matchday").count() == 2


@pytest.mark.django_db
class TestSeenUniqueness:
    def test_seen_uniqueness_per_user(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        user = UserFactory()
        WinnerAnnouncementSeen.objects.create(announcement=ann, user=user)
        with pytest.raises(IntegrityError):
            WinnerAnnouncementSeen.objects.create(announcement=ann, user=user)

    def test_seen_allows_multiple_users(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        u1 = UserFactory()
        u2 = UserFactory()
        WinnerAnnouncementSeen.objects.create(announcement=ann, user=u1)
        WinnerAnnouncementSeen.objects.create(announcement=ann, user=u2)
        assert WinnerAnnouncementSeen.objects.filter(announcement=ann).count() == 2
