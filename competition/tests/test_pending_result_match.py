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
def test_next_pending_result_match_returns_first_live(grp):
    # open: kickoff en el futuro (apuestas siguen abiertas)
    open_m = MatchFactory(round=grp, kickoff=_now() + timedelta(hours=1))
    assert open_m.status == "open"

    # live: kickoff en el pasado reciente, sin resultado
    live_m = MatchFactory(round=grp, kickoff=_now() - timedelta(minutes=10))
    assert live_m.status == "live"

    # otro live más antiguo aún sin resultado
    older_live = MatchFactory(round=grp, kickoff=_now() - timedelta(hours=2))
    assert older_live.status == "live"

    # done: con resultado oficial
    done_m = MatchFactory(round=grp, kickoff=_now() - timedelta(hours=4))
    done_m.result_home = 1
    done_m.result_away = 0
    done_m.save()
    assert done_m.status == "done"

    # Devuelve el más antiguo por kickoff entre los live: older_live.
    assert next_pending_result_match() == older_live


@pytest.mark.django_db
def test_next_pending_result_match_skips_after_match(grp):
    first = MatchFactory(round=grp, kickoff=_now() - timedelta(hours=2))
    second = MatchFactory(round=grp, kickoff=_now() - timedelta(hours=1, minutes=30))
    assert first.status == "live"
    assert second.status == "live"

    assert next_pending_result_match() == first
    assert next_pending_result_match(after_match=first) == second
    assert next_pending_result_match(after_match=second) == first


@pytest.mark.django_db
def test_pending_result_matches_count_counts_only_live(grp):
    # 3 live (kickoff pasado, sin resultado)
    MatchFactory(round=grp, kickoff=_now() - timedelta(hours=2))
    MatchFactory(round=grp, kickoff=_now() - timedelta(hours=1))
    MatchFactory(round=grp, kickoff=_now() - timedelta(minutes=10))
    # 1 done
    done_m = MatchFactory(round=grp, kickoff=_now() - timedelta(hours=4))
    done_m.result_home = 2
    done_m.result_away = 2
    done_m.save()
    # 1 open
    MatchFactory(round=grp, kickoff=_now() + timedelta(hours=10))

    assert pending_result_matches_count() == 3
