from collections.abc import Iterable

from accounts.models import User
from competition.services.standings import standings
from stats.services.matchday_options import current_option, matchday_options, parse_scope_key


def build_general_context(
    user,
    requested_scope_key: str | None,
    *,
    player_ids: Iterable[int] | None = None,
) -> dict:
    """Contexto compartido entre el tab General de Rankings y el detalle por grupo.

    Devuelve el dict con `standings`, `scope_standings`, `md_options`, etc.
    Si `player_ids` está presente, las clasificaciones quedan limitadas a
    esos jugadores y las posiciones se recalculan desde 1 dentro del grupo.
    """
    player_ids_list = list(player_ids) if player_ids is not None else None

    rows = standings(player_ids=player_ids_list)
    has_points = bool(rows) and rows[0].pts > 0
    my_row = next((r for r in rows if r.player_id == user.id), None)
    my_rank = my_row.position if my_row and has_points else None
    my_is_tied = bool(my_row and my_row.is_tied and has_points)
    max_pts = max((r.pts for r in rows), default=0) or 1

    md_opts = matchday_options()
    requested = parse_scope_key(requested_scope_key, md_opts)
    current = current_option(md_opts)
    scope = requested or current
    for o in md_opts:
        o.is_active = scope is not None and o.key == scope.key

    scope_rows: list = []
    scope_my_rank = None
    scope_my_is_tied = False
    scope_max_pts = 1
    scope_label = None
    if scope is not None:
        if scope.round_ids is not None:
            scope_rows = standings(
                round_ids=scope.round_ids,
                player_ids=player_ids_list,
            )
        else:
            scope_rows = standings(
                round_id=scope.round_id,
                matchday=scope.matchday,
                player_ids=player_ids_list,
            )
        scope_has_points = bool(scope_rows) and scope_rows[0].pts > 0
        scope_my_row = next((r for r in scope_rows if r.player_id == user.id), None)
        scope_my_rank = scope_my_row.position if scope_my_row and scope_has_points else None
        scope_my_is_tied = bool(scope_my_row and scope_my_row.is_tied and scope_has_points)
        scope_max_pts = max((r.pts for r in scope_rows), default=0) or 1
        scope_label = scope.label

    all_ids = {r.player_id for r in rows} | {r.player_id for r in scope_rows}
    users_by_id = User.objects.in_bulk(all_ids)
    return {
        "standings": rows,
        "standings_users": users_by_id,
        "my_rank": my_rank,
        "my_is_tied": my_is_tied,
        "max_pts": max_pts,
        "scope_standings": scope_rows,
        "scope_my_rank": scope_my_rank,
        "scope_my_is_tied": scope_my_is_tied,
        "scope_max_pts": scope_max_pts,
        "scope_label": scope_label,
        "md_options": md_opts,
    }
