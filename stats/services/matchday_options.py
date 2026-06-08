from dataclasses import dataclass, field

from django.db.models import Count, Max, Min, Q

from competition.models import Match, Round

KO_ROUND_IDS: tuple[str, ...] = ("r32", "r16", "qf", "sf", "final")
KO_SCOPE_KEY = "ko:_"
KO_SCOPE_LABEL = "Fases Finales"


@dataclass
class MatchdayOption:
    round_id: str | None
    matchday: int | None
    label: str
    key: str  # "<round_id>:<matchday or '_'>" — usado en URLs ("ko:_" para fases finales)
    fully_resolved: bool
    round_ids: list[str] | None = field(default=None)


def matchday_options() -> list[MatchdayOption]:
    """Opciones del selector de jornada para Rankings.

    La porra tiene 4 jornadas: las tres de la fase de grupos (cada una como
    opción independiente) y «Fases Finales», que agrupa todos los partidos
    eliminatorios (R32, R16, cuartos, semis, final) como una única jornada.
    """
    combos = list(
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
    ko_combos: list[dict] = []
    for c in combos:
        if c["round_id"] in KO_ROUND_IDS:
            ko_combos.append(c)
            continue
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

    if ko_combos:
        total = sum(c["total"] for c in ko_combos)
        resolved = sum(c["resolved"] for c in ko_combos)
        options.append(
            MatchdayOption(
                round_id=None,
                matchday=None,
                label=KO_SCOPE_LABEL,
                key=KO_SCOPE_KEY,
                fully_resolved=total > 0 and resolved == total,
                round_ids=list(KO_ROUND_IDS),
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
