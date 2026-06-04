"""Tests del colapso visual del podio con 3+ jugadores empatados.

El template `_podium_step.html` se renderiza vía `_leaderboard_panel.html`,
que es el que hace `regroup ... by position`. Construimos `rows` ya con
posiciones explícitas para forzar cada caso.
"""

import pytest
from django.template.loader import render_to_string

from accounts.tests.factories import UserFactory
from competition.services.standings import StandingRow


def _row(user, position: int, pts: int = 30, *, is_tied: bool, is_first_in_tie: bool):
    return StandingRow(
        position=position,
        is_tied=is_tied,
        is_first_in_tie=is_first_in_tie,
        player_id=user.id,
        name=user.name,
        email=user.email,
        pts=pts,
        hits=0,
        exact_hits=0,
    )


def _render(rows, users, *, me=None, max_pts: int = 30):
    return render_to_string(
        "partials/_leaderboard_panel.html",
        {"rows": rows, "users": users, "me": me, "max_pts": max_pts},
    )


@pytest.mark.django_db
def test_podium_renders_collapsed_with_three_or_more_ties():
    users = [UserFactory(name=n) for n in ("Ana", "Borja", "Carla")]
    rows = [
        _row(u, position=1, is_tied=True, is_first_in_tie=(i == 0)) for i, u in enumerate(users)
    ]
    html = _render(rows, {u.id: u for u in users})
    assert "Varios (3)" in html
    assert "podium-tied" in html


@pytest.mark.django_db
def test_podium_two_ties_still_renders_avatars_stacked():
    users = [UserFactory(name=n) for n in ("Ana", "Borja")]
    rows = [
        _row(u, position=1, is_tied=True, is_first_in_tie=(i == 0)) for i, u in enumerate(users)
    ]
    html = _render(rows, {u.id: u for u in users})
    assert "Varios (" not in html
    assert "Ana" in html
    assert "Borja" in html


@pytest.mark.django_db
def test_podium_single_player_unchanged():
    user = UserFactory(name="Ana")
    rows = [_row(user, position=1, is_tied=False, is_first_in_tie=True)]
    html = _render(rows, {user.id: user})
    assert "Varios (" not in html
    assert "podium-tied" not in html
    assert "Ana" in html


@pytest.mark.django_db
def test_podium_tooltip_lists_all_tied_names():
    users = [UserFactory(name=n) for n in ("Ana", "Borja", "Carla", "Dani")]
    rows = [
        _row(u, position=1, is_tied=True, is_first_in_tie=(i == 0)) for i, u in enumerate(users)
    ]
    html = _render(rows, {u.id: u for u in users})
    assert "podium-tied__tooltip" in html
    for name in ("Ana", "Borja", "Carla", "Dani"):
        assert name in html


@pytest.mark.django_db
def test_podium_tied_is_me_class_applied_when_user_in_group():
    users = [UserFactory(name=n) for n in ("Ana", "Borja", "Carla")]
    rows = [
        _row(u, position=1, is_tied=True, is_first_in_tie=(i == 0)) for i, u in enumerate(users)
    ]
    html = _render(rows, {u.id: u for u in users}, me=users[1])
    assert "podium-tied" in html
    assert "is-me" in html


@pytest.mark.django_db
def test_podium_collapses_only_affected_slot():
    """1º con 3 empatados (colapsado), 2º con 1 jugador (sin cambios)."""
    tied = [UserFactory(name=n) for n in ("Ana", "Borja", "Carla")]
    solo = UserFactory(name="Zoe")
    rows = [
        *[
            _row(u, position=1, pts=30, is_tied=True, is_first_in_tie=(i == 0))
            for i, u in enumerate(tied)
        ],
        _row(solo, position=2, pts=20, is_tied=False, is_first_in_tie=True),
    ]
    html = _render(rows, {u.id: u for u in [*tied, solo]})
    assert "Varios (3)" in html
    assert "Zoe" in html
