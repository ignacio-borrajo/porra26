import pytest
from django.core.management import call_command

from competition.models import Match, Prediction, Round
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture(autouse=True)
def _rounds(db):
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)


@pytest.mark.django_db
def test_seed_creates_48_teams_and_72_matches():
    from competition.models import Team

    call_command("seed_world_cup_2026")
    assert Team.objects.count() == 48
    assert Match.objects.filter(round_id="groups").count() == 72
    for md in (1, 2, 3):
        assert Match.objects.filter(round_id="groups", matchday=md).count() == 24


@pytest.mark.django_db
def test_seed_is_idempotent():
    from competition.models import Team

    call_command("seed_world_cup_2026")
    call_command("seed_world_cup_2026")
    assert Team.objects.count() == 48
    assert Match.objects.filter(round_id="groups").count() == 72


@pytest.mark.django_db
def test_seed_preserves_existing_predictions(django_user_model):
    user = django_user_model.objects.create_user(
        email="a@edisa.com", password="x", name="Ana", is_jugador=True
    )
    call_command("seed_world_cup_2026")
    match = Match.objects.filter(round_id="groups", matchday=1).first()
    Prediction.objects.create(player=user, match=match, home=2, away=1)
    call_command("seed_world_cup_2026")
    assert Prediction.objects.filter(player=user, match=match).count() == 1


@pytest.mark.django_db
def test_seed_prune_deletes_orphans():
    foreign_a = TeamFactory(code="ZZA", name="Aliens", flag="🛸")
    foreign_b = TeamFactory(code="ZZB", name="Bots", flag="🤖")
    grp = Round.objects.get(id="groups")
    MatchFactory(round=grp, group="Z", matchday=1, home=foreign_a, away=foreign_b)
    call_command("seed_world_cup_2026", "--prune")
    assert not Match.objects.filter(group="Z").exists()
    assert Match.objects.filter(round_id="groups").count() == 72


@pytest.mark.django_db
def test_seed_keeps_orphans_without_prune():
    foreign_a = TeamFactory(code="ZZA", name="Aliens", flag="🛸")
    foreign_b = TeamFactory(code="ZZB", name="Bots", flag="🤖")
    grp = Round.objects.get(id="groups")
    MatchFactory(round=grp, group="Z", matchday=1, home=foreign_a, away=foreign_b)
    call_command("seed_world_cup_2026")
    assert Match.objects.filter(group="Z").exists()
