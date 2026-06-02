from dataclasses import dataclass

from django.db.models import Count, Max, Min, Q

from competition.models import Match, Round


@dataclass
class MatchdayOption:
    round_id: str
    matchday: int | None
    label: str
    key: str  # "<round_id>:<matchday or '_'>" — usado en URLs
    fully_resolved: bool


def matchday_options() -> list[MatchdayOption]:
    """Combinaciones (ronda, jornada) con partidos, en orden cronológico.

    En la fase de grupos cada jornada es una opción independiente; en las rondas
    eliminatorias (sin jornadas) cada ronda es una sola opción.
    """
    combos = (
        Match.objects.values("round_id", "matchday")
        .annotate(
            min_kickoff=Min("kickoff"),
            max_kickoff=Max("kickoff"),
            total=Count("id"),
            resolved=Count("id", filter=Q(result_home__isnull=False)),
        )
        .order_by("min_kickoff")
    )
    rounds_by_id = {r.id: r for r in Round.objects.all()}
    options: list[MatchdayOption] = []
    for c in combos:
        rnd = rounds_by_id.get(c["round_id"])
        round_label = rnd.label if rnd else c["round_id"]
        md = c["matchday"]
        if md is not None:
            if c["round_id"] == "groups":
                label = f"Jornada {md}"
            else:
                label = f"{round_label} · J{md}"
        else:
            label = round_label
        options.append(
            MatchdayOption(
                round_id=c["round_id"],
                matchday=md,
                label=label,
                key=f"{c['round_id']}:{md if md is not None else '_'}",
                fully_resolved=c["resolved"] == c["total"],
            )
        )
    return options


def current_option(options: list[MatchdayOption]) -> MatchdayOption | None:
    """Jornada/ronda «en curso»: la primera con partidos sin resolver."""
    for o in options:
        if not o.fully_resolved:
            return o
    return options[-1] if options else None


def parse_scope_key(key: str | None, options: list[MatchdayOption]) -> MatchdayOption | None:
    if not key:
        return None
    return next((o for o in options if o.key == key), None)
