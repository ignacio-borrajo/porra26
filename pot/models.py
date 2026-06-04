from decimal import Decimal

from django.db import models


class PotSettings(models.Model):
    per_player = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10.00"))
    allowed_email_domains = models.JSONField(default=list, blank=True)
    matchday_winner_prize = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0")
    )
    maintenance_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))

    class Meta:
        verbose_name = "Pot settings"

    def __str__(self):
        return f"PotSettings(per_player={self.per_player})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Prize(models.Model):
    SCOPE_CHOICES = [("global", "Global"), ("matchday", "Jornada"), ("round", "Ronda KO")]

    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    position = models.PositiveSmallIntegerField(null=True, blank=True)
    matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    round = models.ForeignKey(
        "competition.Round", on_delete=models.PROTECT, null=True, blank=True, related_name="prizes"
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    label = models.CharField(max_length=60)

    class Meta:
        ordering = ["scope", "position", "matchday", "round_id"]

    def __str__(self):
        return self.label


class Payment(models.Model):
    player = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="payment")
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment({self.player_id}, paid={self.paid})"
