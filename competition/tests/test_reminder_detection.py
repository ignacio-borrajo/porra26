from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import GestorFactory, UserFactory
from competition.models import BetsReminderLog
from competition.services.reminders import get_pending_bettors, matches_due_for_kind
from competition.tests.factories import MatchFactory, PredictionFactory

# -------------------------------------------------------------------
# get_pending_bettors
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_pending_bettors_excludes_those_who_bet():
    match = MatchFactory()
    u1 = UserFactory(name="Ana")
    u2 = UserFactory(name="Beto")
    PredictionFactory(player=u1, match=match)
    pending = get_pending_bettors(match)
    assert u1 not in pending
    assert u2 in pending


@pytest.mark.django_db
def test_pending_bettors_excludes_inactive_users():
    match = MatchFactory()
    UserFactory(name="Activo")
    UserFactory(name="Inactivo", is_active=False)
    names = [u.name for u in get_pending_bettors(match)]
    assert "Activo" in names
    assert "Inactivo" not in names


@pytest.mark.django_db
def test_pending_bettors_excludes_non_jugador():
    match = MatchFactory()
    UserFactory(name="Jugador")
    UserFactory(name="GestorPuro", is_jugador=False, is_gestor=True)
    names = [u.name for u in get_pending_bettors(match)]
    assert "Jugador" in names
    assert "GestorPuro" not in names


@pytest.mark.django_db
def test_pending_bettors_includes_gestor_who_plays():
    match = MatchFactory()
    GestorFactory(name="GestorJugador")
    names = [u.name for u in get_pending_bettors(match)]
    assert "GestorJugador" in names


@pytest.mark.django_db
def test_pending_bettors_ordered_by_name():
    match = MatchFactory()
    UserFactory(name="Zara")
    UserFactory(name="Ana")
    UserFactory(name="Mario")
    names = [u.name for u in get_pending_bettors(match)]
    assert names == sorted(names)


# -------------------------------------------------------------------
# matches_due_for_kind
# -------------------------------------------------------------------


@pytest.mark.django_db
def test_matches_due_t_minus_4h_returns_match_inside_window():
    """Match con kickoff en 3h (= ya pasó T-4h pero antes del cierre T-2h)."""
    match = MatchFactory(kickoff=timezone.now() + timedelta(hours=3))
    due = list(matches_due_for_kind(BetsReminderLog.KIND_T_MINUS_4H))
    assert match in due


@pytest.mark.django_db
def test_matches_due_t_minus_4h_excludes_match_too_far_in_future():
    """Match con kickoff en 5h (= T-4h aún no llegó)."""
    MatchFactory(kickoff=timezone.now() + timedelta(hours=5))
    due = list(matches_due_for_kind(BetsReminderLog.KIND_T_MINUS_4H))
    assert due == []


@pytest.mark.django_db
def test_matches_due_excludes_match_after_closure():
    """Match con kickoff en 1h (= cierre T-2h ya pasó)."""
    MatchFactory(kickoff=timezone.now() + timedelta(hours=1))
    due_4h = list(matches_due_for_kind(BetsReminderLog.KIND_T_MINUS_4H))
    due_2_5h = list(matches_due_for_kind(BetsReminderLog.KIND_T_MINUS_2_5H))
    assert due_4h == []
    assert due_2_5h == []


@pytest.mark.django_db
def test_matches_due_excludes_match_with_existing_log_for_kind():
    match = MatchFactory(kickoff=timezone.now() + timedelta(hours=3))
    BetsReminderLog.objects.create(
        match=match,
        kind=BetsReminderLog.KIND_T_MINUS_4H,
        sent_at=timezone.now(),
        pending_count=2,
        pending_names=["X", "Y"],
    )
    due = list(matches_due_for_kind(BetsReminderLog.KIND_T_MINUS_4H))
    assert due == []


@pytest.mark.django_db
def test_matches_due_includes_match_with_log_for_other_kind():
    """Tener el aviso T-4h enviado no impide enviar el T-2.5h."""
    match = MatchFactory(kickoff=timezone.now() + timedelta(hours=2, minutes=15))
    BetsReminderLog.objects.create(
        match=match,
        kind=BetsReminderLog.KIND_T_MINUS_4H,
        sent_at=timezone.now() - timedelta(hours=2),
        pending_count=1,
        pending_names=["X"],
    )
    due = list(matches_due_for_kind(BetsReminderLog.KIND_T_MINUS_2_5H))
    assert match in due


@pytest.mark.django_db
def test_matches_due_t_minus_2_5h_window():
    """Match a 2h15min de kickoff: T-2.5h ya llegó y T-2h aún no."""
    match = MatchFactory(kickoff=timezone.now() + timedelta(hours=2, minutes=15))
    due = list(matches_due_for_kind(BetsReminderLog.KIND_T_MINUS_2_5H))
    assert match in due


@pytest.mark.django_db
def test_matches_due_rejects_unknown_kind():
    with pytest.raises(ValueError):
        list(matches_due_for_kind("UNKNOWN"))


@pytest.mark.django_db
def test_matches_due_rejects_manual_kind():
    """MANUAL no tiene ventana — se envía con kind=MANUAL solo desde el botón."""
    with pytest.raises(ValueError):
        list(matches_due_for_kind(BetsReminderLog.KIND_MANUAL))
