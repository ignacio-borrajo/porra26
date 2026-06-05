from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserSession

STALE_THRESHOLD_DAYS = 35


class Command(BaseCommand):
    help = "Borra UserSession huérfanas (sin Session real) o con last_seen_at > 35 días."

    def handle(self, *args, **options):
        active_keys = set(Session.objects.values_list("session_key", flat=True))
        cutoff = timezone.now() - timedelta(days=STALE_THRESHOLD_DAYS)

        orphan_pks = set(
            UserSession.objects.exclude(session_key__in=active_keys).values_list("pk", flat=True)
        )
        stale_pks = set(
            UserSession.objects.filter(last_seen_at__lt=cutoff).values_list("pk", flat=True)
        )
        pks = orphan_pks | stale_pks
        deleted, _ = UserSession.objects.filter(pk__in=pks).delete()

        self.stdout.write(self.style.SUCCESS(f"Pruned {deleted} UserSession rows."))
