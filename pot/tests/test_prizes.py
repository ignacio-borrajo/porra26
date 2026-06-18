from decimal import Decimal

import pytest

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.models import PotSettings, Prize
from pot.services.prizes import announcement_podium, matchday_winners


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_matchday_pending_if_any_match_unresolved(groups_round):
    MatchFactory(round=groups_round, matchday=1, result_home=None, result_away=None)
    MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    res = matchday_winners(("matchday", 1))
    assert res.status == "pending"


@pytest.mark.django_db
def test_matchday_single_winner(groups_round):
    a = UserFactory(name="A")
    b = UserFactory(name="B")
    m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=a, match=m2, earned=1)
    PredictionFactory(player=b, match=m1, earned=1)
    PredictionFactory(player=b, match=m2, earned=0)
    res = matchday_winners(("matchday", 1))
    assert res.status == "resolved"
    assert [w.id for w in res.winners] == [a.id]


@pytest.mark.django_db
def test_matchday_tie_splits_prize(groups_round):
    a = UserFactory(name="A")
    b = UserFactory(name="B")
    m1 = MatchFactory(round=groups_round, matchday=2, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=b, match=m1, earned=3)
    res = matchday_winners(("matchday", 2))
    assert res.status == "resolved"
    assert sorted(w.id for w in res.winners) == sorted([a.id, b.id])
    assert res.tied is True


@pytest.mark.django_db
def test_matchday_desierto_when_nobody_scored(groups_round):
    UserFactory()
    MatchFactory(round=groups_round, matchday=3, result_home=1, result_away=0)
    res = matchday_winners(("matchday", 3))
    assert res.status == "desierto"


@pytest.mark.django_db
def test_matchday_winners_exact_breaks_tie(groups_round):
    """Mismos pts pero distinto número de exactos: gana el de más exactos."""
    groups_round.partial_points = 1
    groups_round.save()
    a = UserFactory(name="Ana")
    b = UserFactory(name="Borja")
    # Mismos pts (4), Ana con 1 exacto+1 parcial, Borja con 0 exactos+4 parciales no es posible.
    # Hacemos: Ana 3+1=4 (1 exacto). Borja 1+1+1+1=4 con 4 parciales — necesita 4 partidos.
    # Más simple: 2 partidos donde Ana hace 1 exacto y Borja 0 exactos pero los mismos pts totales.
    m1 = MatchFactory(round=groups_round, matchday=4, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=4, result_home=2, result_away=2)
    # Ana: exacto en m1 (3 pts) + parcial en m2 (1 pt) = 4 pts, 1 exacto, 2 aciertos
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m2, home=0, away=0, earned=1)
    # Borja: parcial en m1 (1 pt) + exacto en m2 (3 pts) = 4 pts, 1 exacto, 2 aciertos → siguen empatados
    PredictionFactory(player=b, match=m1, home=2, away=0, earned=1)
    PredictionFactory(player=b, match=m2, home=2, away=2, earned=3)
    res = matchday_winners(("matchday", 4))
    assert res.status == "resolved"
    assert res.tied is True
    assert {w.id for w in res.winners} == {a.id, b.id}


@pytest.mark.django_db
def test_matchday_winners_share_is_split_when_tied(groups_round):
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("25")
    s.save()
    a = UserFactory(name="Ana")
    b = UserFactory(name="Borja")
    m1 = MatchFactory(round=groups_round, matchday=5, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)
    res = matchday_winners(("matchday", 5))
    assert res.tied is True
    assert res.share == Decimal("12.5")


@pytest.mark.django_db
def test_matchday_winners_share_full_when_single(groups_round):
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("25")
    s.save()
    a = UserFactory(name="Ana")
    b = UserFactory(name="Borja")
    m1 = MatchFactory(round=groups_round, matchday=6, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=0, away=1, earned=0)
    res = matchday_winners(("matchday", 6))
    assert res.tied is False
    assert res.share == Decimal("25")
    assert [w.id for w in res.winners] == [a.id]


@pytest.fixture
def final_round(db):
    return RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)


@pytest.mark.django_db
def test_global_winner_share_uses_prize_position_1_not_matchday_setting(final_round):
    """Regresión: matchday_winners(global) debe usar Prize[scope=global, position=1].amount."""
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("5.00")
    s.save()
    Prize.objects.create(scope="global", position=1, amount=Decimal("300.00"), label="1º")
    Prize.objects.create(scope="global", position=2, amount=Decimal("100.00"), label="2º")
    a = UserFactory(name="Ana")
    m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
    PredictionFactory(player=a, match=m, home=2, away=1, earned=20)
    res = matchday_winners(("global", None))
    assert res.status == "resolved"
    assert res.share == Decimal("300.00")


@pytest.mark.django_db
def test_global_winner_share_splits_when_tied_using_prize(final_round):
    Prize.objects.create(scope="global", position=1, amount=Decimal("300.00"), label="1º")
    a = UserFactory(name="Ana")
    b = UserFactory(name="Borja")
    m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
    PredictionFactory(player=a, match=m, home=2, away=1, earned=20)
    PredictionFactory(player=b, match=m, home=2, away=1, earned=20)
    res = matchday_winners(("global", None))
    assert res.tied is True
    assert res.share == Decimal("150.00")


@pytest.mark.django_db
def test_global_winner_share_zero_when_no_prize_configured(final_round):
    a = UserFactory(name="Ana")
    m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
    PredictionFactory(player=a, match=m, home=2, away=1, earned=20)
    res = matchday_winners(("global", None))
    assert res.status == "resolved"
    assert res.share == Decimal("0")


class TestAnnouncementPodium:
    @pytest.mark.django_db
    def test_global_returns_three_positions_with_prize_per_position(self, final_round):
        Prize.objects.create(scope="global", position=1, amount=Decimal("300"), label="1º")
        Prize.objects.create(scope="global", position=2, amount=Decimal("100"), label="2º")
        Prize.objects.create(scope="global", position=3, amount=Decimal("50"), label="3º")
        first = UserFactory(name="Primero")
        second = UserFactory(name="Segundo")
        third = UserFactory(name="Tercero")
        m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=first, match=m, home=2, away=1, earned=20)
        PredictionFactory(player=second, match=m, home=2, away=0, earned=5)
        PredictionFactory(player=third, match=m, home=1, away=1, earned=1)
        from announcements.models import WinnerAnnouncement

        ann = WinnerAnnouncement.objects.create(
            scope_kind="global", points=20, tied=False, share=Decimal("300")
        )
        ann.winners.set([first])
        entries = announcement_podium(ann)
        assert [e.position for e in entries] == [1, 2, 3]
        assert [u.id for u in entries[0].users] == [first.id]
        assert entries[0].prize_per_user == Decimal("300")
        assert entries[1].prize_per_user == Decimal("100")
        assert entries[2].prize_per_user == Decimal("50")
        assert [u.id for u in entries[1].users] == [second.id]
        assert [u.id for u in entries[2].users] == [third.id]

    @pytest.mark.django_db
    def test_matchday_only_position_1_has_prize(self, groups_round):
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("10")
        s.save()
        a = UserFactory(name="A")
        b = UserFactory(name="B")
        c = UserFactory(name="C")
        m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
        PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
        PredictionFactory(player=a, match=m2, home=2, away=2, earned=3)
        PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)
        PredictionFactory(player=b, match=m2, home=0, away=0, earned=1)
        PredictionFactory(player=c, match=m1, home=2, away=1, earned=1)
        PredictionFactory(player=c, match=m2, home=0, away=0, earned=1)
        from announcements.models import WinnerAnnouncement

        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday",
            scope_matchday=1,
            points=6,
            tied=False,
            share=Decimal("10"),
        )
        ann.winners.set([a])
        entries = announcement_podium(ann)
        positions = [e.position for e in entries]
        assert positions == [1, 2, 3]
        assert entries[0].prize_per_user == Decimal("10")
        assert entries[1].prize_per_user == Decimal("0")
        assert entries[2].prize_per_user == Decimal("0")

    @pytest.mark.django_db
    def test_finals_only_position_1_has_prize(self, db):
        r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("20")
        s.save()
        a = UserFactory(name="A")
        b = UserFactory(name="B")
        m = MatchFactory(round=r16, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=a, match=m, home=1, away=0, earned=7)
        PredictionFactory(player=b, match=m, home=2, away=1, earned=1)
        from announcements.models import WinnerAnnouncement

        ann = WinnerAnnouncement.objects.create(
            scope_kind="finals",
            points=7,
            tied=False,
            share=Decimal("20"),
        )
        ann.winners.set([a])
        entries = announcement_podium(ann)
        assert [e.position for e in entries] == [1, 2]
        assert entries[0].prize_per_user == Decimal("20")
        assert entries[1].prize_per_user == Decimal("0")

    @pytest.mark.django_db
    def test_tied_position_splits_prize(self, groups_round):
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("10")
        s.save()
        a = UserFactory(name="A")
        b = UserFactory(name="B")
        m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=a, match=m, home=1, away=0, earned=3)
        PredictionFactory(player=b, match=m, home=1, away=0, earned=3)
        from announcements.models import WinnerAnnouncement

        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday",
            scope_matchday=1,
            points=3,
            tied=True,
            share=Decimal("5"),
        )
        ann.winners.set([a, b])
        entries = announcement_podium(ann)
        assert entries[0].position == 1
        assert entries[0].tied is True
        assert sorted(u.id for u in entries[0].users) == sorted([a.id, b.id])
        assert entries[0].prize_per_user == Decimal("5")

    @pytest.mark.django_db
    def test_skips_positions_without_anyone_scoring(self, groups_round):
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("10")
        s.save()
        a = UserFactory(name="A")
        UserFactory(name="B")  # sin predicciones, queda fuera
        m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=a, match=m, home=1, away=0, earned=3)
        from announcements.models import WinnerAnnouncement

        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday",
            scope_matchday=1,
            points=3,
            tied=False,
            share=Decimal("10"),
        )
        ann.winners.set([a])
        entries = announcement_podium(ann)
        assert [e.position for e in entries] == [1]


@pytest.mark.django_db
def test_matchday_winners_r32_resolved_uses_only_r32():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings
    from pot.services.prizes import matchday_winners

    pot = PotSettings.load()
    pot.matchday_winner_prize = Decimal("30.00")
    pot.save(update_fields=["matchday_winner_prize"])

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    winner = UserFactory(name="W")
    loser = UserFactory(name="L")
    m_r32 = MatchFactory(round=r32, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=winner, match=m_r32, earned=5)
    PredictionFactory(player=loser, match=m_r32, earned=0)
    # Un partido de r16 con puntos NO debe contar para el scope r32.
    m_r16 = MatchFactory(round=r16, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=loser, match=m_r16, earned=7)

    result = matchday_winners(("r32", None))
    assert result.status == "resolved"
    assert result.points == 5
    assert [u.name for u in result.winners] == ["W"]
    assert result.share == Decimal("30.00")


@pytest.mark.django_db
def test_matchday_winners_r32_pending_until_all_r32_resolved():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    user = UserFactory()
    m_done = MatchFactory(round=r32, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=user, match=m_done, earned=5)
    MatchFactory(round=r32, matchday=None, result_home=None)

    result = matchday_winners(("r32", None))
    assert result.status == "pending"


@pytest.mark.django_db
def test_matchday_winners_finals_pending_until_all_finals_resolved():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    qf = RoundFactory(id="qf", points=10, label="QF", short="QF", order=4)
    sf = RoundFactory(id="sf", points=15, label="SF", short="SF", order=5)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory()
    for r in (r16, qf, sf):
        m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=r.points)
    MatchFactory(round=fn, matchday=None, result_home=None)

    result = matchday_winners(("finals", None))
    assert result.status == "pending"


@pytest.mark.django_db
def test_matchday_winners_finals_not_pending_when_only_r32_unresolved():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory()
    MatchFactory(round=r32, matchday=None, result_home=None)  # r32 sin resolver
    m_fn = MatchFactory(round=fn, matchday=None, result_home=2, result_away=1)
    PredictionFactory(player=user, match=m_fn, earned=20)

    result = matchday_winners(("finals", None))
    assert result.status == "resolved"
    assert result.points == 20


@pytest.mark.django_db
def test_matchday_winners_finals_aggregates_r16_qf_sf_final_excluding_r32():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings
    from pot.services.prizes import matchday_winners

    pot = PotSettings.load()
    pot.matchday_winner_prize = Decimal("30.00")
    pot.save(update_fields=["matchday_winner_prize"])

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    qf = RoundFactory(id="qf", points=10, label="QF", short="QF", order=4)
    sf = RoundFactory(id="sf", points=15, label="SF", short="SF", order=5)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)

    winner = UserFactory(name="W")
    loser = UserFactory(name="L")
    # r32 NO cuenta para finals: damos al loser muchos puntos en r32.
    m_r32 = MatchFactory(round=r32, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=loser, match=m_r32, earned=99)
    for r, pts in ((r16, 7), (qf, 10), (sf, 15), (fn, 20)):
        m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=winner, match=m, earned=pts)
        PredictionFactory(player=loser, match=m, earned=0)

    result = matchday_winners(("finals", None))
    assert result.status == "resolved"
    assert result.points == 52  # 7+10+15+20, sin el r32
    assert [u.name for u in result.winners] == ["W"]
    assert result.share == Decimal("30.00")


@pytest.mark.django_db
def test_matchday_winners_finals_excludes_groups_points():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory()
    m_grp = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_fn = MatchFactory(round=fn, matchday=None, result_home=2, result_away=1)
    PredictionFactory(player=user, match=m_grp, earned=3)
    PredictionFactory(player=user, match=m_fn, earned=20)

    result = matchday_winners(("finals", None))
    assert result.status == "resolved"
    assert result.points == 20
