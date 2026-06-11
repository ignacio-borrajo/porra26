from dataclasses import dataclass
from typing import Literal

from accounts.models import User
from competition.services.live_standings import live_standings

Dimension = Literal["sede", "puesto", "dept"]

CHOICES_BY_DIMENSION = {
    "sede": User.SEDE_CHOICES,
    "puesto": User.PUESTO_CHOICES,
    "dept": User.DEPT_CHOICES,
}


@dataclass
class GroupRow:
    key: str
    label: str
    players: int
    total: int
    avg: float
    top_name: str
    top_pts: int
    top_user_id: int | None = None
    top_tied_count: int = 1
    position: int | None = None
    is_tied: bool = False
    is_first_in_tie: bool = True


def group_standings(dimension: Dimension) -> list[GroupRow]:
    """Agrega los standings por la dimensión organizativa indicada.

    Devuelve una fila por cada `choice` del enum (incluso si está vacía)
    y, al final, una fila "Sin asignar" con los jugadores que no tienen
    valor en ese campo. Las filas con jugadores se ordenan por media y
    reciben posición densa (1,1,2,2,3) con flags `is_tied`/`is_first_in_tie`.
    """
    choices = CHOICES_BY_DIMENSION[dimension]
    labels = {key: label for key, label in choices}

    standings_rows = live_standings()
    for r in standings_rows:
        r.pts = r.live_pts
    users = User.objects.filter(is_active=True, is_jugador=True).only("id", dimension)
    user_group = {u.id: (getattr(u, dimension) or "__none__") for u in users}

    buckets: dict[str, list] = {key: [] for key, _ in choices}
    buckets["__none__"] = []
    for row in standings_rows:
        key = user_group.get(row.player_id)
        if key is None:
            continue
        buckets[key].append(row)

    rows: list[GroupRow] = []
    for key, _label in choices:
        rows.append(_row_for(key, labels[key], buckets[key]))
    none_rows = buckets["__none__"]
    if none_rows:
        rows.append(_row_for("__none__", "Sin asignar", none_rows))

    head = [r for r in rows if r.key != "__none__"]
    head.sort(key=lambda r: (-r.avg, -r.total, r.label.lower()))
    _assign_dense_positions(head)
    tail = [r for r in rows if r.key == "__none__"]
    return head + tail


def _row_for(key: str, label: str, members) -> GroupRow:
    players = len(members)
    total = sum(r.pts for r in members)
    avg = (total / players) if players else 0.0
    if members:
        # 3 reglas para decidir el líder del grupo. Empate persistente → alfabético solo presentación.
        ordered = sorted(
            members,
            key=lambda r: (-r.pts, -r.exact_hits, -r.hits, r.name.lower()),
        )
        top = ordered[0]
        top_key = (top.pts, top.exact_hits, top.hits)
        tied = [r for r in ordered if (r.pts, r.exact_hits, r.hits) == top_key]
        top_name, top_pts, top_user_id = top.name, top.pts, top.player_id
        top_tied_count = len(tied)
    else:
        top_name, top_pts, top_user_id = "", 0, None
        top_tied_count = 1
    return GroupRow(
        key=key,
        label=label,
        players=players,
        total=total,
        avg=avg,
        top_name=top_name,
        top_pts=top_pts,
        top_user_id=top_user_id,
        top_tied_count=top_tied_count,
    )


def _assign_dense_positions(rows: list[GroupRow]) -> None:
    """Asigna `position`, `is_tied`, `is_first_in_tie` in place sobre filas ya ordenadas."""
    if not rows:
        return
    counts: dict[tuple[float, int], int] = {}
    for r in rows:
        counts[(r.avg, r.total)] = counts.get((r.avg, r.total), 0) + 1
    prev_key: tuple[float, int] | None = None
    position = 0
    for r in rows:
        key = (r.avg, r.total)
        if key != prev_key:
            position += 1
            r.is_first_in_tie = True
        else:
            r.is_first_in_tie = False
        prev_key = key
        r.position = position
        r.is_tied = counts[key] > 1
