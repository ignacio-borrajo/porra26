"""Resetea los cruces KO a estado pendiente y reaplica fechas/orden de R32.

Pensado para producción cuando un administrador asignó equipos por error:
- Reaplica kickoff + bracket_order de R32 desde el fixture (vía seed).
- Devuelve todos los cruces KO con slots a 'pending_teams': limpia equipos,
  resultados, pronósticos, marcador en vivo e informes de cierre.

Idempotente. Ejecutar manualmente tras el deploy:
    python manage.py reset_r32_crosses
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import AuditLog
from competition.models import BetsClosingReport, LiveScore, Match, Prediction


class Command(BaseCommand):
    help = "Resetea los cruces KO a pendiente y reaplica fechas/orden de R32."

    @transaction.atomic
    def handle(self, **opts):
        # 1) Reaplicar kickoff + bracket_order desde el fixture (no toca equipos).
        call_command("seed_world_cup_2026")

        # 2) Limpiar estado de todos los cruces KO con slots.
        ko = (
            Match.objects.exclude(round_id="groups")
            .exclude(home_slot="")
            .exclude(away_slot="")
        )
        n = 0
        for m in ko:
            Prediction.objects.filter(match=m).delete()
            LiveScore.objects.filter(match=m).delete()
            BetsClosingReport.objects.filter(match=m).delete()
            m.home = None
            m.away = None
            m.result_home = None
            m.result_away = None
            m.finished_at = None
            m.exact_points_applied = None
            m.partial_points_applied = None
            m.save(
                update_fields=[
                    "home",
                    "away",
                    "result_home",
                    "result_away",
                    "finished_at",
                    "exact_points_applied",
                    "partial_points_applied",
                ]
            )
            n += 1

        AuditLog.objects.create(
            actor=None,
            action="r32_reset",
            target_type="match",
            target_id="r32",
            payload={"reset_count": n},
        )
        self.stdout.write(self.style.SUCCESS(f"Reseteados {n} cruce(s) KO a pendiente."))
