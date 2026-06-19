from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import Match, Prediction
from competition.services.score import score


@transaction.atomic
def resolve_match(match: Match, *, home: int, away: int, actor) -> None:
    """Confirma el resultado oficial y recalcula `earned` de los pronósticos."""
    match.result_home = home
    match.result_away = away
    match.finished_at = timezone.now()
    update_fields = ["result_home", "result_away", "finished_at"]

    if match.exact_points_applied is None:
        match.exact_points_applied = match.round.points
        match.partial_points_applied = match.round.partial_points
        update_fields += ["exact_points_applied", "partial_points_applied"]

    match.save(update_fields=update_fields)

    preds = list(
        Prediction.objects.select_for_update().filter(match=match).select_related("match__round")
    )
    for p in preds:
        p.earned = score(p, match)
    if preds:
        Prediction.objects.bulk_update(preds, ["earned"])

    AuditLog.objects.create(
        actor=actor,
        action="match_resolved",
        target_type="match",
        target_id=str(match.id),
        payload={"home": home, "away": away},
    )

    from competition.services.bracket import propagate_after_match

    propagate_after_match(match)

    from announcements.services import detect_after_match

    detect_after_match(match)


@transaction.atomic
def clear_match_result(match: Match, *, actor) -> None:
    """Deshace el resultado oficial: borra marcador, descongela los puntos y
    resetea `earned` de los pronósticos. Si la jornada/ronda/global ya tenía un
    anuncio de ganador derivado de este partido, también lo elimina (porque el
    scope deja de estar completo).

    No toca `BetsClosingReport` (cierre/PDF) ni `BetsReminderLog` (recordatorios):
    los envíos a Teams ya realizados se preservan."""
    prev_home = match.result_home
    prev_away = match.result_away

    match.result_home = None
    match.result_away = None
    match.finished_at = None
    match.exact_points_applied = None
    match.partial_points_applied = None
    match.save(
        update_fields=[
            "result_home",
            "result_away",
            "finished_at",
            "exact_points_applied",
            "partial_points_applied",
        ]
    )

    Prediction.objects.select_for_update().filter(match=match).update(earned=None)

    _remove_invalidated_announcements(match)

    AuditLog.objects.create(
        actor=actor,
        action="match_result_cleared",
        target_type="match",
        target_id=str(match.id),
        payload={"home": prev_home, "away": prev_away},
    )


@transaction.atomic
def delete_match(match: Match, *, actor) -> None:
    """Borra un partido por completo. Pensado para limpiar partidos creados por
    error (p. ej. cruces de prueba en producción).

    Al eliminar el `Match` se borran en cascada sus pronósticos, marcador en
    vivo, informe de cierre y registros de recordatorio (todos con
    `on_delete=CASCADE`). Si el partido tenía resultado y había generado un
    anuncio de ganador cuyo scope deja de estar resuelto, también se elimina.
    Queda registro en `AuditLog`.
    """
    payload = {
        "round": match.round_id,
        "matchday": match.matchday,
        "home": match.home_id,
        "away": match.away_id,
        "home_slot": match.home_slot,
        "away_slot": match.away_slot,
        "bracket_code": match.bracket_code,
        "kickoff": match.kickoff.isoformat() if match.kickoff else None,
        "result_home": match.result_home,
        "result_away": match.result_away,
    }
    had_result = match.has_result
    match_id = match.id

    match.delete()

    if had_result:
        # El objeto en memoria conserva round_id/matchday tras el delete, así que
        # podemos reutilizar la limpieza de anuncios con el scope ya recalculado.
        _remove_invalidated_announcements(match)

    AuditLog.objects.create(
        actor=actor,
        action="match_deleted",
        target_type="match",
        target_id=str(match_id),
        payload=payload,
    )


def _remove_invalidated_announcements(match: Match) -> None:
    """Tras borrar el resultado, elimina los `WinnerAnnouncement` cuyo scope
    incluye este partido y ya no se considera resuelto (matchday de grupos,
    dieciseisavos `r32`, fases finales `finals`, y `global` al deshacer la Final)."""
    from announcements.models import WinnerAnnouncement
    from pot.services.prizes import matchday_winners

    scope_filters: list[tuple[tuple, dict]] = []
    if match.round_id == "groups" and match.matchday is not None:
        scope_filters.append(
            (
                ("matchday", match.matchday),
                {"scope_kind": "matchday", "scope_matchday": match.matchday},
            )
        )
    elif match.round_id == "r32":
        scope_filters.append((("r32", None), {"scope_kind": "r32"}))
    elif match.round_id in ("r16", "qf", "sf", "final"):
        scope_filters.append((("finals", None), {"scope_kind": "finals"}))
        if match.round_id == "final":
            scope_filters.append((("global", None), {"scope_kind": "global"}))

    for scope_key, filter_kwargs in scope_filters:
        if matchday_winners(scope_key).status == "resolved":
            continue
        WinnerAnnouncement.objects.filter(**filter_kwargs).delete()
