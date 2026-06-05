from datetime import timedelta

import pytest
from auditlog.models import LogEntry
from django.utils import timezone

from accounts.models import User
from competition.models import Match, Prediction, Round, Team


@pytest.fixture
def setup(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    esp = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    arg = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    m = Match.objects.create(
        round=grp,
        group="A",
        matchday=1,
        home=esp,
        away=arg,
        kickoff=timezone.now() + timedelta(days=1),
    )
    u = User.objects.create_user(email="a@edisa.com", password="x", name="Ana")
    return u, m


@pytest.mark.django_db
def test_prediction_create_is_audited(setup):
    u, m = setup
    p = Prediction.objects.create(player=u, match=m, home=2, away=1)
    entry = LogEntry.objects.get_for_object(p).first()
    assert entry is not None
    assert entry.action == LogEntry.Action.CREATE
    assert "home" in entry.changes_dict
    assert "away" in entry.changes_dict


@pytest.mark.django_db
def test_prediction_update_records_diff(setup):
    u, m = setup
    p = Prediction.objects.create(player=u, match=m, home=2, away=1)
    p.home = 3
    p.away = 0
    p.save()
    update = LogEntry.objects.get_for_object(p).filter(action=LogEntry.Action.UPDATE).first()
    assert update is not None
    changes = update.changes_dict
    assert changes["home"] == ["2", "3"]
    assert changes["away"] == ["1", "0"]


@pytest.mark.django_db
def test_match_result_is_audited(setup):
    _, m = setup
    m.result_home = 1
    m.result_away = 0
    m.finished_at = timezone.now()
    m.save(update_fields=["result_home", "result_away", "finished_at"])
    update = LogEntry.objects.get_for_object(m).filter(action=LogEntry.Action.UPDATE).first()
    assert update is not None
    changes = update.changes_dict
    assert changes["result_home"] == ["None", "1"]
    assert changes["result_away"] == ["None", "0"]
