from django.db import models


class Raffle(models.Model):
    """Sorteo por descarte. El activo es el más reciente; reiniciar lo borra.

    Al iniciarse se fija `started_at` y se precalcula el guion completo de
    eliminaciones; los clientes lo reproducen sincronizados con el reloj del
    servidor.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Raffle({self.pk}, {self.created_at:%d-%m-%Y %H:%M})"


class RaffleEntry(models.Model):
    """Snapshot de un participante; `eliminated_order` 1..n-1 según el guion.

    `eliminated_at` es el instante PROGRAMADO de la caída (started_at + orden ×
    cadencia); puede estar en el futuro. El ganador es la única entry sin orden.
    """

    raffle = models.ForeignKey(Raffle, on_delete=models.CASCADE, related_name="entries")
    player = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="+")
    eliminated_order = models.PositiveIntegerField(null=True, blank=True)
    eliminated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["player__name"]
        constraints = [
            models.UniqueConstraint(fields=["raffle", "player"], name="uniq_raffle_player"),
            models.UniqueConstraint(
                fields=["raffle", "eliminated_order"], name="uniq_raffle_elim_order"
            ),
        ]

    def __str__(self):
        return f"RaffleEntry({self.player_id}, order={self.eliminated_order})"
