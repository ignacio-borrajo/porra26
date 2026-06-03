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
