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


def _remove_invalidated_announcements(match: Match) -> None:
    """Tras borrar el resultado, elimina los `WinnerAnnouncement` cuyo scope
    incluye este partido y ya no se considera resuelto."""
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
    else:
        scope_filters.append(
            (
                ("round", match.round_id),
                {"scope_kind": "round", "scope_round_id": match.round_id},
            )
        )
        if match.round_id == "final":
            scope_filters.append((("global", None), {"scope_kind": "global"}))

    for scope_key, filter_kwargs in scope_filters:
        if matchday_winners(scope_key).status == "resolved":
            continue
        WinnerAnnouncement.objects.filter(**filter_kwargs).delete()
