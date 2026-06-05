from decimal import Decimal

from django.http import Http404

from accounts.models import User
from announcements.models import WinnerAnnouncement
from competition.models import Round
from pot.models import PotSettings, Prize
from pot.services.prizes import PodiumEntry

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

    base = _preview_prize_for_position(scope, 1)
    ann.share = (base / len(winners)) if winners else Decimal("0")

    return ann, winners


def build_preview_podium(scope: str, *, tied: bool, current_user) -> list[PodiumEntry]:
    """Podio sintético para la previsualización del modal.

    Puesto 1 = current_user (o empate con otro si tied). Puestos 2 y 3 = otros
    usuarios reales si los hay, para que el gestor vea el layout completo.
    """
    if scope not in _VALID_SCOPES:
        raise Http404(f"scope inválido: {scope}")

    others = list(User.objects.exclude(pk=current_user.pk).order_by("name")[:3])

    first_users = [current_user]
    if tied and others:
        first_users.append(others.pop(0))

    entries: list[PodiumEntry] = []
    base_1 = _preview_prize_for_position(scope, 1)
    entries.append(
        PodiumEntry(
            position=1,
            users=first_users,
            prize_per_user=(base_1 / len(first_users)) if first_users else Decimal("0"),
            tied=len(first_users) > 1,
        )
    )
    if others:
        entries.append(
            PodiumEntry(
                position=2,
                users=[others.pop(0)],
                prize_per_user=_preview_prize_for_position(scope, 2),
                tied=False,
            )
        )
    if others:
        entries.append(
            PodiumEntry(
                position=3,
                users=[others.pop(0)],
                prize_per_user=_preview_prize_for_position(scope, 3),
                tied=False,
            )
        )
    return entries


def _preview_prize_for_position(scope: str, position: int) -> Decimal:
    if scope == "global":
        prize = Prize.objects.filter(scope="global", position=position).first()
        return prize.amount if prize else Decimal("0")
    if position == 1:
        return PotSettings.load().matchday_winner_prize
    return Decimal("0")


def build_preview_sede(*, current_user) -> tuple[WinnerAnnouncement, list]:
    """Construye un anuncio sintético + grid de SedeWinner para previsualizar
    la modal de sede. Para sedes con al menos un jugador real (excluyendo
    current_user para mostrar también un estado 'resolved' realista), usa
    al primer jugador como ganador. Sedes sin jugadores → estado 'desierto'."""
    from pot.models import PotSettings
    from pot.services.prizes import SedeWinner

    ann = WinnerAnnouncement(scope_kind="sede", points=0)

    sede_prize = PotSettings.load().sede_winner_prize
    sede_winners_preview: list[SedeWinner] = []
    for sede_key, sede_label in User.SEDE_CHOICES:
        first = User.objects.filter(sede=sede_key).order_by("name").first()
        if first is None:
            sede_winners_preview.append(SedeWinner(sede_key=sede_key, sede_label=sede_label))
            continue
        sede_winners_preview.append(SedeWinner(
            sede_key=sede_key,
            sede_label=sede_label,
            users=[first],
            points=0,
            prize_per_user=sede_prize,
            status="resolved",
        ))
    return ann, sede_winners_preview
