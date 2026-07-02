import pytest

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement
from announcements.services import detect_after_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)


@pytest.fixture
def r32_round(db):
    return RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)


@pytest.fixture
def r16_round(db):
    return RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)


@pytest.fixture
def qf_round(db):
    return RoundFactory(id="qf", points=10, label="Cuartos", short="QF", order=4)


@pytest.fixture
def sf_round(db):
    return RoundFactory(id="sf", points=15, label="Semifinales", short="SF", order=5)


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

    def test_announcement_idempotent_on_second_call(self, groups_round):
        user = UserFactory()
        m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=3)
        first = detect_after_match(m)
        second = detect_after_match(m)
        assert len(first) == 1
        assert second == []


@pytest.mark.django_db
class TestR32Scope:
    def test_no_announcement_until_last_r32_resolved(self, r32_round):
        user = UserFactory()
        m_done = MatchFactory(round=r32_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m_done, earned=5)
        MatchFactory(round=r32_round, matchday=None, result_home=None)
        created = detect_after_match(m_done)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0

    def test_r32_announcement_created_when_last_r32_resolved(self, r32_round):
        user = UserFactory(name="Ganadora")
        m1 = MatchFactory(round=r32_round, matchday=None, result_home=1, result_away=0)
        m2 = MatchFactory(round=r32_round, matchday=None, result_home=2, result_away=0)
        PredictionFactory(player=user, match=m1, earned=5)
        PredictionFactory(player=user, match=m2, earned=5)
        created = detect_after_match(m2)
        assert len(created) == 1
        assert created[0].scope_kind == "r32"
        assert created[0].points == 10
        assert list(created[0].winners.all()) == [user]


@pytest.mark.django_db
class TestFinalsSilentRounds:
    def test_resolving_r16_creates_no_announcement(self, r16_round):
        user = UserFactory()
        m = MatchFactory(round=r16_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=7)
        created = detect_after_match(m)
        assert created == []

    def test_resolving_sf_creates_no_announcement(self, sf_round):
        user = UserFactory()
        m = MatchFactory(round=sf_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=15)
        created = detect_after_match(m)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0


@pytest.mark.django_db
class TestFinalTriggers:
    def test_final_creates_finals_sede_global_in_order(
        self, groups_round, r32_round, r16_round, qf_round, sf_round, final_round
    ):
        # Top 3 global = 3 jugadores de vigo (con puntos en grupos). El cuarto
        # (madrid) entra en la sede madrid porque no está en el podio global.
        v1 = UserFactory(name="V1", sede="vigo")
        v2 = UserFactory(name="V2", sede="vigo")
        v3 = UserFactory(name="V3", sede="vigo")
        ma = UserFactory(name="MA", sede="madrid")
        g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=v1, match=g_m, earned=5)
        PredictionFactory(player=v2, match=g_m, earned=4)
        PredictionFactory(player=v3, match=g_m, earned=3)
        PredictionFactory(player=ma, match=g_m, earned=1)
        for r, pts in (
            (r32_round, 5),
            (r16_round, 7),
            (qf_round, 10),
            (sf_round, 15),
        ):
            m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
            PredictionFactory(player=v1, match=m, earned=pts)
        m_final = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=v1, match=m_final, earned=20)

        created = detect_after_match(m_final)
        kinds = [a.scope_kind for a in created]
        assert kinds == ["finals", "sede", "global"]

    def test_final_finals_aggregates_r16_qf_sf_final_points(
        self, r32_round, r16_round, qf_round, sf_round, final_round
    ):
        winner = UserFactory(name="W", sede="madrid")
        # r32 NO cuenta para la jornada finals.
        m_r32 = MatchFactory(round=r32_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=winner, match=m_r32, earned=5)
        for r, pts in (
            (r16_round, 7),
            (qf_round, 10),
            (sf_round, 15),
        ):
            m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
            PredictionFactory(player=winner, match=m, earned=pts)
        m_final = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=winner, match=m_final, earned=20)

        created = detect_after_match(m_final)
        finals = next(a for a in created if a.scope_kind == "finals")
        assert finals.points == 52  # 7+10+15+20, sin el r32

    def test_final_idempotent(self, final_round):
        user = UserFactory(name="W", sede="madrid")
        m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=user, match=m, earned=20)
        first = detect_after_match(m)
        second = detect_after_match(m)
        assert len(first) >= 1
        assert second == []

    def test_finals_waits_for_third_place_match(
        self, r16_round, qf_round, sf_round, final_round
    ):
        winner = UserFactory(name="W", sede="madrid")
        for r, pts in ((r16_round, 7), (qf_round, 10), (sf_round, 15)):
            m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
            PredictionFactory(player=winner, match=m, earned=pts)
        # 3.er puesto (ronda final) SIN resolver todavía.
        third = MatchFactory(
            round=final_round,
            group="3.º y 4.º puesto",
            bracket_code="M104",
            matchday=None,
            result_home=None,
            result_away=None,
        )
        m_final = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=winner, match=m_final, earned=20)

        # La Final está resuelta pero el 3.er puesto no: nada de finals/global.
        created = detect_after_match(m_final)
        assert created == []

        # Al resolver el 3.er puesto se cierra el ámbito y saltan los anuncios.
        third.result_home, third.result_away = 1, 0
        third.save(update_fields=["result_home", "result_away"])
        PredictionFactory(player=winner, match=third, earned=20)
        created = detect_after_match(third)
        kinds = [a.scope_kind for a in created]
        assert "finals" in kinds
        assert "global" in kinds
