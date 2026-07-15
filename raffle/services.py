import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import User

from .models import Raffle, RaffleEntry

# Un eliminado cada CADENCE_SECONDS. El estado público solo revela las
# eliminaciones programadas dentro de los próximos REVEAL_AHEAD_SECONDS: lo
# justo para que el cliente apunte el giro, sin destripar el resto del guion.
CADENCE_SECONDS = 30
REVEAL_AHEAD_SECONDS = 20

_rng = random.SystemRandom()


def eligible_players():
    return User.objects.filter(is_active=True, is_jugador=True, payment__paid=True)


def _ms(dt):
    return int(dt.timestamp() * 1000)


def start_raffle():
    """Congela el snapshot y precalcula el guion completo de eliminaciones.

    Devuelve el sorteo iniciado. ValueError si ya hay uno en marcha o si no
    hay participantes suficientes. Un sorteo previo sin iniciar (flujo antiguo
    por tandas) se descarta y se regenera con los elegibles actuales.
    """
    with transaction.atomic():
        existing = Raffle.objects.first()
        if existing is not None:
            if existing.started_at is not None:
                raise ValueError("Ya hay un sorteo en marcha.")
            existing.delete()

        players = list(eligible_players())
        if len(players) < 2:
            raise ValueError("No hay participantes suficientes para sortear.")

        raffle = Raffle.objects.create(started_at=timezone.now())
        order = _rng.sample(players, len(players))
        entries = [
            RaffleEntry(
                raffle=raffle,
                player=player,
                eliminated_order=k,
                eliminated_at=raffle.started_at + timedelta(seconds=k * CADENCE_SECONDS),
            )
            for k, player in enumerate(order[:-1], start=1)
        ]
        entries.append(RaffleEntry(raffle=raffle, player=order[-1]))
        RaffleEntry.objects.bulk_create(entries)
    return raffle


def public_state(now=None):
    """Estado visible del sorteo para cualquier usuario logueado.

    Nunca revela eliminaciones programadas más allá del horizonte
    now + REVEAL_AHEAD_SECONDS; el ganador solo se deduce cuando el guion
    visible está completo.
    """
    now = now or timezone.now()
    horizon = now + timedelta(seconds=REVEAL_AHEAD_SECONDS)
    raffle = Raffle.objects.filter(started_at__isnull=False).first()
    if raffle is None:
        participants = [
            {"id": p.id, "name": p.name, "eliminatedOrder": None, "eliminatedAtMs": None}
            for p in eligible_players().order_by("name")
        ]
        started_ms = None
    else:
        participants = []
        for e in raffle.entries.select_related("player"):
            revealed = e.eliminated_at is not None and e.eliminated_at <= horizon
            participants.append(
                {
                    "id": e.player_id,
                    "name": e.player.name,
                    "eliminatedOrder": e.eliminated_order if revealed else None,
                    "eliminatedAtMs": _ms(e.eliminated_at) if revealed else None,
                }
            )
        started_ms = _ms(raffle.started_at)
    return {
        "serverNowMs": _ms(now),
        "startedAtMs": started_ms,
        "cadenceMs": CADENCE_SECONDS * 1000,
        "participants": participants,
    }
