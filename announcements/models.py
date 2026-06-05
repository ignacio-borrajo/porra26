from decimal import Decimal

from django.db import models
from django.db.models import Q, UniqueConstraint


class WinnerAnnouncement(models.Model):
    SCOPE_CHOICES = [
        ("matchday", "Jornada de grupos"),
        ("round", "Ronda KO"),
        ("global", "Campeón del Mundial"),
        ("sede", "Ganadores por sede"),
    ]

    scope_kind = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    scope_matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    scope_round = models.ForeignKey(
        "competition.Round",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="announcements",
    )
    points = models.PositiveIntegerField()
    tied = models.BooleanField(default=False)
    share = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    winners = models.ManyToManyField(
        "accounts.User",
        related_name="winning_announcements",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            UniqueConstraint(
                fields=["scope_kind", "scope_matchday"],
                condition=Q(scope_kind="matchday"),
                name="uniq_ann_matchday",
            ),
            UniqueConstraint(
                fields=["scope_kind", "scope_round"],
                condition=Q(scope_kind="round"),
                name="uniq_ann_round",
            ),
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="global"),
                name="uniq_ann_global",
            ),
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="sede"),
                name="uniq_ann_sede",
            ),
        ]

    def __str__(self):
        if self.scope_kind == "matchday":
            return f"Anuncio jornada {self.scope_matchday}"
        if self.scope_kind == "round":
            return f"Anuncio ronda {self.scope_round_id}"
        return "Anuncio campeón del Mundial"

    @property
    def title(self) -> str:
        if self.scope_kind == "matchday":
            if self.tied:
                return f"¡Ganadores de la Jornada {self.scope_matchday}!"
            return f"¡Ganador de la Jornada {self.scope_matchday}!"
        if self.scope_kind == "round":
            label = self.scope_round.label if self.scope_round_id else "la ronda"
            if self.tied:
                return f"¡Ganadores de {label}!"
            return f"¡Ganador de {label}!"
        if self.scope_kind == "sede":
            return "¡Ganadores por sede!"
        return "¡Campeones del Mundial!" if self.tied else "¡Campeón del Mundial!"


class WinnerAnnouncementSeen(models.Model):
    announcement = models.ForeignKey(
        WinnerAnnouncement,
        on_delete=models.CASCADE,
        related_name="seen_by",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="seen_announcements",
    )
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [UniqueConstraint(fields=["announcement", "user"], name="uniq_seen_per_user")]
        indexes = [models.Index(fields=["user", "announcement"])]

    def __str__(self):
        return f"Seen({self.user_id} → {self.announcement_id})"
