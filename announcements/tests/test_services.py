import pytest

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement
from announcements.services import detect_after_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)


@pytest.fixture
def r16_round(db):
    return RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)


@pytest.fixture
def final_round(db):
    return RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)


@pytest.mark.django_db
class TestMatchdayScope:
    def test_no_announcement_when_matchday_incomplete(self, groups_round):
        m_open = MatchFactory(round=groups_round, matchday=1, result_home=None)
        MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        created = detect_after_match(m_open)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0

    def test_announcement_created_when_last_matchday_match_resolved(self, groups_round):
        user = UserFactory(name="Ganadora")
        m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
        PredictionFactory(player=user, match=m1, earned=3)
        PredictionFactory(player=user, match=m2, earned=1)
        created = detect_after_match(m2)
        assert len(created) == 1
        ann = created[0]
        assert ann.scope_kind == "matchday"
        assert ann.scope_matchday == 1
        assert ann.points == 4
        assert list(ann.winners.all()) == [user]

    def test_no_announcement_when_status_is_desierto(self, groups_round):
        UserFactory()
        m1 = MatchFactory(round=groups_round, matchday=2, result_home=1, result_away=0)
        created = detect_after_match(m1)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0

    def test_tied_winners_persisted_with_tied_flag(self, groups_round):
        a = UserFactory(name="A")
        b = UserFactory(name="B")
        m = MatchFactory(round=groups_round, matchday=3, result_home=1, result_away=0)
        PredictionFactory(player=a, match=m, earned=3)
        PredictionFactory(player=b, match=m, earned=3)
        created = detect_after_match(m)
        assert len(created) == 1
        ann = created[0]
        assert ann.tied is True
        assert {w.id for w in ann.winners.all()} == {a.id, b.id}

    def test_announcement_idempotent_on_second_call(self, groups_round):
        user = UserFactory()
        m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=3)
        first = detect_after_match(m)
        second = detect_after_match(m)
        assert len(first) == 1
        assert second == []
        assert WinnerAnnouncement.objects.filter(scope_kind="matchday").count() == 1


@pytest.mark.django_db
class TestRoundScope:
    def test_announcement_created_for_round_ko(self, r16_round):
        user = UserFactory()
        m1 = MatchFactory(round=r16_round, matchday=None, result_home=1, result_away=0)
        m2 = MatchFactory(round=r16_round, matchday=None, result_home=0, result_away=2)
        PredictionFactory(player=user, match=m1, earned=7)
        PredictionFactory(player=user, match=m2, earned=1)
        created = detect_after_match(m2)
        assert len(created) == 1
        assert created[0].scope_kind == "round"
        assert created[0].scope_round_id == "r16"

    def test_no_round_announcement_when_round_incomplete(self, r16_round):
        user = UserFactory()
        MatchFactory(round=r16_round, matchday=None, result_home=None)
        m_done = MatchFactory(round=r16_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m_done, earned=7)
        created = detect_after_match(m_done)
        assert created == []


@pytest.mark.django_db
class TestGlobalScope:
    def test_global_announcement_created_only_after_final(self, final_round):
        user = UserFactory()
        m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=user, match=m, earned=20)
        created = detect_after_match(m)
        kinds = sorted(a.scope_kind for a in created)
        assert kinds == ["global", "round"]
        assert WinnerAnnouncement.objects.filter(scope_kind="global").count() == 1
        assert WinnerAnnouncement.objects.filter(scope_kind="round", scope_round_id="final").count() == 1

    def test_no_global_announcement_when_not_final(self, r16_round):
        user = UserFactory()
        m = MatchFactory(round=r16_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=7)
        detect_after_match(m)
        assert WinnerAnnouncement.objects.filter(scope_kind="global").count() == 0


@pytest.mark.django_db
class TestContract:
    def test_uses_matchday_winners_contract(self, groups_round):
        """Si esto rompe, ha cambiado la firma de pot.services.prizes.matchday_winners."""
        from pot.services.prizes import matchday_winners

        user = UserFactory()
        m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=3)
        result = matchday_winners(("matchday", 1))
        # Solo tres atributos: status, winners, points (más tied informativo)
        assert hasattr(result, "status")
        assert hasattr(result, "winners")
        assert hasattr(result, "points")
        assert hasattr(result, "tied")
        assert result.status in {"pending", "desierto", "resolved"}
