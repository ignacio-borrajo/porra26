"""Resolver de slots del cuadro: traduce códigos como '1A', '2C', 'WM49'
al equipo concreto que ocupa esa posición en este momento."""

from __future__ import annotations

import re
from dataclasses import dataclass

from competition.models import Match, Team

GROUP_RE = re.compile(r"^([123])([A-L])$")
WINNER_RE = re.compile(r"^WM(\d+)$")


@dataclass(frozen=True)
class GroupRow:
    team: Team
    pts: int
    gd: int
    gf: int


def _group_standings(group: str) -> list[GroupRow] | None:
    """Clasificación del grupo. None si quedan partidos sin resultado oficial."""
    matches = list(
        Match.objects.filter(round_id="groups", group=group).select_related("home", "away")
    )
    if not matches:
        return None
    if any(not m.has_result for m in matches):
        return None

    stats: dict[str, dict] = {}
    for m in matches:
        for team, gf, ga in (
            (m.home, m.result_home, m.result_away),
            (m.away, m.result_away, m.result_home),
        ):
            s = stats.setdefault(team.code, {"team": team, "pts": 0, "gd": 0, "gf": 0})
            s["gf"] += gf
            s["gd"] += gf - ga
            if gf > ga:
                s["pts"] += 3
            elif gf == ga:
                s["pts"] += 1

    rows = [GroupRow(team=s["team"], pts=s["pts"], gd=s["gd"], gf=s["gf"]) for s in stats.values()]
    rows.sort(key=lambda r: (-r.pts, -r.gd, -r.gf, r.team.code))
    return rows


def resolve_slot(code: str) -> Team | None:
    """Equipo concreto al que apunta el código, o None si no es determinable aún."""
    if not code:
        return None
    if m := GROUP_RE.match(code):
        pos = int(m.group(1))
        group = m.group(2)
        standings = _group_standings(group)
        if standings is None or len(standings) < pos:
            return None
        return standings[pos - 1].team
    if m := WINNER_RE.match(code):
        bracket_code = f"M{m.group(1)}"
        match = Match.objects.filter(bracket_code=bracket_code).first()
        if match is None or not match.has_result:
            return None
        if match.result_home == match.result_away:
            return None  # empate 90': el gestor decide
        return match.home if match.result_home > match.result_away else match.away
    return None


def propagate_after_match(match: Match) -> list[Match]:
    """Rellena home/away en todos los partidos cuyos slots queden resolvibles
    tras procesar `match`. Idempotente: solo escribe donde está a None."""
    # R32 (Dieciseisavos) se excluye a propósito: sus equipos los asigna siempre
    # un gestor a mano para evitar errores. Octavos+ sí se propagan desde los
    # ganadores (`WM…`) una vez el gestor ha confirmado el resultado del R32.
    pending = (
        (
            Match.objects.filter(home__isnull=True).exclude(home_slot="")
            | Match.objects.filter(away__isnull=True).exclude(away_slot="")
        )
        .distinct()
        .exclude(round_id="r32")
    )
    updated: list[Match] = []
    for m in pending:
        update_fields: list[str] = []
        if m.home_id is None and m.home_slot:
            team = resolve_slot(m.home_slot)
            if team is not None:
                m.home = team
                update_fields.append("home")
        if m.away_id is None and m.away_slot:
            team = resolve_slot(m.away_slot)
            if team is not None:
                m.away = team
                update_fields.append("away")
        if update_fields:
            m.save(update_fields=update_fields)
            updated.append(m)
    return updated
