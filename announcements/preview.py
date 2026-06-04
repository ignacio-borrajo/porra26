from decimal import Decimal

from django.http import Http404

from accounts.models import User
from announcements.models import WinnerAnnouncement
from competition.models import Round
from pot.models import PotSettings

_VALID_SCOPES = {"matchday", "round", "global"}


def build_preview(scope: str, *, tied: bool, current_user) -> tuple[WinnerAnnouncement, list]:
    if scope not in _VALID_SCOPES:
        raise Http404(f"scope inválido: {scope}")

    ann = WinnerAnnouncement(scope_kind=scope, points=12)

    if scope == "matchday":
        ann.scope_matchday = 1
    elif scope == "round":
        ko_round = Round.objects.exclude(id="groups").order_by("order").first()
        if ko_round is None:
            ko_round = Round.objects.order_by("order").first()
        if ko_round is not None:
            ann.scope_round = ko_round

    winners = [current_user]
    if tied:
        other = User.objects.exclude(pk=current_user.pk).order_by("name").first()
        if other is not None:
            winners.append(other)
    ann.tied = len(winners) > 1

    base = PotSettings.load().matchday_winner_prize
    ann.share = (base / len(winners)) if winners else Decimal("0")

    return ann, winners
