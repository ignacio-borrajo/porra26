from dataclasses import dataclass
from typing import Literal

from accounts.models import User
from competition.services.standings import standings

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


def group_standings(dimension: Dimension) -> list[GroupRow]:
    """Agrega los standings por la dimensión organizativa indicada.

    Devuelve una fila por cada `choice` del enum (incluso si está vacía)
    y, al final, una fila "Sin asignar" con los jugadores que no tienen
    valor en ese campo.
    """
    choices = CHOICES_BY_DIMENSION[dimension]
    labels = {key: label for key, label in choices}

    standings_rows = standings()
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
    tail = [r for r in rows if r.key == "__none__"]
    return head + tail


def _row_for(key: str, label: str, members) -> GroupRow:
    players = len(members)
    total = sum(r.pts for r in members)
    avg = (total / players) if players else 0.0
    if members:
        top = max(members, key=lambda r: (r.pts, -r.player_id))
        top_name, top_pts, top_user_id = top.name, top.pts, top.player_id
    else:
        top_name, top_pts, top_user_id = "", 0, None
    return GroupRow(
        key=key,
        label=label,
        players=players,
        total=total,
        avg=avg,
        top_name=top_name,
        top_pts=top_pts,
        top_user_id=top_user_id,
    )
