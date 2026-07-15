import random

from django.db import transaction
from django.utils import timezone

from accounts.models import User

from .models import Raffle, RaffleEntry

# Con más de SINGLE_FROM restantes cada pulsación elimina en tanda de hasta
# BATCH_SIZE; a partir de ahí, de uno en uno (decidido con el gestor).
SINGLE_FROM = 15
BATCH_SIZE = 5

_rng = random.SystemRandom()


def eligible_players():
    return User.objects.filter(is_active=True, is_jugador=True, payment__paid=True)


def get_or_create_raffle():
    """Devuelve el sorteo activo; si no hay, lo crea congelando los participantes."""
    raffle = Raffle.objects.first()
    if raffle is not None:
        return raffle
    with transaction.atomic():
        raffle = Raffle.objects.create()
        RaffleEntry.objects.bulk_create(
            RaffleEntry(raffle=raffle, player=p) for p in eligible_players()
        )
    return raffle


def batch_size(remaining: int) -> int:
    if remaining > SINGLE_FROM:
        return min(BATCH_SIZE, remaining - SINGLE_FROM)
    return 1


def spin(raffle):
    """Elimina la tanda que toca y devuelve (eliminados en orden, nº restantes, ganador|None)."""
    with transaction.atomic():
        alive = list(
            raffle.entries.select_for_update()
            .filter(eliminated_order__isnull=True)
            .select_related("player")
        )
        if len(alive) < 2:
            raise ValueError("No quedan participantes suficientes para girar.")

        next_order = raffle.entries.filter(eliminated_order__isnull=False).count() + 1
        eliminated = []
        for _ in range(batch_size(len(alive))):
            victim = _rng.choice(alive)
            alive.remove(victim)
            victim.eliminated_order = next_order
            victim.eliminated_at = timezone.now()
            victim.save(update_fields=["eliminated_order", "eliminated_at"])
            eliminated.append(victim)
            next_order += 1

        winner = alive[0] if len(alive) == 1 else None
        return eliminated, len(alive), winner
