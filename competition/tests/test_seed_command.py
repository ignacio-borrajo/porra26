import pytest
from django.core.management import call_command

from competition.models import Match, Prediction, Round
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture(autouse=True)
def _rounds(db):
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    RoundFactory(id="qf", points=10, label="Cuartos", short="QF", order=4)
    RoundFactory(id="sf", points=15, label="Semifinales", short="SF", order=5)
    RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)


@pytest.mark.django_db
def test_seed_creates_48_teams_and_72_matches():
    from competition.models import Team

    call_command("seed_world_cup_2026")
    assert Team.objects.count() == 48
    assert Match.objects.filter(round_id="groups").count() == 72
    for md in (1, 2, 3):
        assert Match.objects.filter(round_id="groups", matchday=md).count() == 24


@pytest.mark.django_db
def test_seed_creates_31_ko_matches_with_slots_and_null_teams():
    call_command("seed_world_cup_2026")
    ko = Match.objects.exclude(round_id="groups")
    assert ko.count() == 31
    # Cada cruce KO arranca sin equipos y con ambos slots no vacíos
    for m in ko:
        assert m.home_id is None
        assert m.away_id is None
        assert m.bracket_code is not None and m.bracket_code != ""
        assert m.home_slot != ""
        assert m.away_slot != ""
    # Distribución por ronda
    assert ko.filter(round_id="r32").count() == 16
    assert ko.filter(round_id="r16").count() == 8
    assert ko.filter(round_id="qf").count() == 4
    assert ko.filter(round_id="sf").count() == 2
    assert ko.filter(round_id="final").count() == 1


@pytest.mark.django_db
def test_seed_is_idempotent():
    from competition.models import Team

    call_command("seed_world_cup_2026")
    call_command("seed_world_cup_2026")
    assert Team.objects.count() == 48
    assert Match.objects.filter(round_id="groups").count() == 72
    assert Match.objects.exclude(round_id="groups").count() == 31


@pytest.mark.django_db
def test_seed_preserves_manually_assigned_ko_teams():
    """Los equipos ya asignados a un cruce KO (por propagate_after_match o
    por el gestor) no se pierden al re-seedear: el seed solo refresca
    slots y kickoff."""
    call_command("seed_world_cup_2026")
    ko = Match.objects.exclude(round_id="groups").first()
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    ko.home = esp
    ko.away = arg
    ko.save(update_fields=["home", "away"])
    call_command("seed_world_cup_2026")
    ko.refresh_from_db()
    assert ko.home == esp
    assert ko.away == arg


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


@pytest.mark.django_db(transaction=True)
def test_seed_dry_run_does_not_crash_with_real_transactions():
    """Regresión: las queries que se ejecutaban DESPUÉS de
    `transaction.set_rollback(True)` rompían con TransactionManagementError en
    Postgres. Esta variante con `transaction=True` reproduce el bug (SQLite
    permisivo dentro del wrapper de pytest-django no lo cubría)."""
    from competition.models import Team

    # transaction=True descarta el autouse fixture compartido — recreamos rounds.
    for rid, label, short, pts, order in [
        ("groups", "Fase de grupos", "GRP", 3, 1),
        ("r32", "Dieciseisavos", "R32", 5, 2),
        ("r16", "Octavos", "R16", 7, 3),
        ("qf", "Cuartos", "QF", 10, 4),
        ("sf", "Semifinales", "SF", 15, 5),
        ("final", "Final", "FIN", 25, 6),
    ]:
        Round.objects.get_or_create(
            id=rid,
            defaults={"label": label, "short": short, "points": pts, "order": order},
        )

    try:
        call_command("seed_world_cup_2026", "--dry-run")
        # Dry-run no persiste nada
        assert Team.objects.count() == 0
        assert Match.objects.count() == 0
    finally:
        Round.objects.all().delete()


@pytest.mark.django_db
def test_seed_sets_bracket_order_on_r32():
    call_command("seed_world_cup_2026")
    m74 = Match.objects.get(bracket_code="M74")
    assert m74.bracket_order == 1
    m73 = Match.objects.get(bracket_code="M73")
    assert m73.bracket_order == 3


@pytest.mark.django_db
def test_seed_updates_bracket_order_without_touching_teams():
    call_command("seed_world_cup_2026")
    m = Match.objects.get(bracket_code="M73")
    home = TeamFactory(code="ZZ1")
    m.home = home
    m.bracket_order = None
    m.save(update_fields=["home", "bracket_order"])
    call_command("seed_world_cup_2026")
    m.refresh_from_db()
    assert m.bracket_order == 3  # reaplicado
    assert m.home_id == "ZZ1"  # no se pisa el equipo asignado
