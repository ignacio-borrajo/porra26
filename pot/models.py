from decimal import Decimal
from django.db import models


class PotSettings(models.Model):
    per_player = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10.00"))
    allowed_email_domains = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Pot settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
