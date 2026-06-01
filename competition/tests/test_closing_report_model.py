import pytest
from django.db import IntegrityError

from competition.models import BetsClosingReport
from competition.tests.factories import MatchFactory


@pytest.mark.django_db
def test_betsclosingreport_default_values():
    match = MatchFactory()
    report = BetsClosingReport.objects.create(match=match)
    assert report.attempts == 0
    assert report.generated_at is None
    assert report.sent_at is None
    assert report.last_sha256 == ""
    assert report.created_at is not None


@pytest.mark.django_db
def test_betsclosingreport_is_one_to_one_with_match():
    match = MatchFactory()
    BetsClosingReport.objects.create(match=match)
    with pytest.raises(IntegrityError):
        BetsClosingReport.objects.create(match=match)


@pytest.mark.django_db
def test_match_teams_slug():
    from competition.tests.factories import TeamFactory
    from datetime import datetime
    from django.utils import timezone

    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(
        home=home,
        away=away,
        kickoff=timezone.make_aware(datetime(2026, 6, 14, 21, 0)),
    )
    assert match.teams_slug == "esp-vs-arg-2026-06-14"
