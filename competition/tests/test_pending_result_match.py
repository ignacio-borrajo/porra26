from datetime import timedelta

import pytest
from django.utils import timezone

from competition.services.predictions import (
    next_pending_result_match,
    pending_result_matches_count,
)
from competition.tests.factories import (
    MatchFactory,
    RoundFactory,
)


def _now():
    return timezone.now()


@pytest.fixture
def grp(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_next_pending_result_match_returns_first_closed_or_live(grp):
    # open: kickoff muy en el futuro
    open_m = MatchFactory(round=grp, kickoff=_now() + timedelta(hours=10))
    assert open_m.status == "open"

    # closed: dentro de la ventana de cierre, todavía sin empezar
    closed_m = MatchFactory(round=grp, kickoff=_now() + timedelta(hours=1))
    assert closed_m.status == "closed"

    # live: kickoff en el pasado reciente, sin resultado
    live_m = MatchFactory(round=grp, kickoff=_now() - timedelta(minutes=10))
    assert live_m.status == "live"

    # done: con resultado oficial
    done_m = MatchFactory(round=grp, kickoff=_now() - timedelta(hours=4))
    done_m.result_home = 1
    done_m.result_away = 0
    done_m.save()
    assert done_m.status == "done"

    # Debe devolver el más antiguo por kickoff entre closed/live, que es live_m
    # (kickoff = now - 10min) por delante del closed_m (kickoff = now + 1h).
    assert next_pending_result_match() == live_m


@pytest.mark.django_db
def test_next_pending_result_match_skips_after_match(grp):
    first = MatchFactory(round=grp, kickoff=_now() + timedelta(hours=1))
    second = MatchFactory(round=grp, kickoff=_now() + timedelta(hours=1, minutes=30))
    assert first.status == "closed"
    assert second.status == "closed"

    assert next_pending_result_match() == first
    assert next_pending_result_match(after_match=first) == second
    assert next_pending_result_match(after_match=second) == first


@pytest.mark.django_db
def test_pending_result_matches_count_counts_only_closed_live(grp):
    # 2 closed
    MatchFactory(round=grp, kickoff=_now() + timedelta(hours=1))
    MatchFactory(round=grp, kickoff=_now() + timedelta(hours=1, minutes=30))
    # 1 live
    MatchFactory(round=grp, kickoff=_now() - timedelta(minutes=10))
    # 1 done
    done_m = MatchFactory(round=grp, kickoff=_now() - timedelta(hours=4))
    done_m.result_home = 2
    done_m.result_away = 2
    done_m.save()
    # 1 open
    MatchFactory(round=grp, kickoff=_now() + timedelta(hours=10))

    assert pending_result_matches_count() == 3
