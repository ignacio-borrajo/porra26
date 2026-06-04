"""Comando de cron / debug para enviar recordatorios pre-cierre.

Llamado por GitHub Actions a través del endpoint ``/api/recordatorios/disparar/``
y también disponible para invocación manual en local. Sin args recorre las dos
ventanas (T-4h y T-2.5h) y dispara los pendientes.
"""

import logging

from django.core.management.base import BaseCommand

from competition.models import BetsReminderLog, Match
from competition.services.reminder_email import send_reminder_email
from competition.services.reminders import matches_due_for_kind

logger = logging.getLogger(__name__)

AUTO_KINDS = list(BetsReminderLog.AUTO_KINDS)


class Command(BaseCommand):
    help = "Envía recordatorios pre-cierre a Teams (vía email)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista los matches que se enviarían pero no envía nada.",
        )
        parser.add_argument(
            "--match-id",
            type=int,
            default=None,
            help="Envía solo el match indicado (para reintentos o pruebas).",
        )
        parser.add_argument(
            "--kind",
            choices=[k for k, _ in BetsReminderLog.KIND_CHOICES],
            default=None,
            help="Restringe al kind dado. Por defecto procesa los dos AUTO.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        match_id: int | None = options["match_id"]
        kind_filter: str | None = options["kind"]

        kinds = AUTO_KINDS if kind_filter is None else [kind_filter]

        ok = ko = skipped = 0
        for kind in kinds:
            if kind == BetsReminderLog.KIND_MANUAL:
                # MANUAL no tiene ventana — el botón del gestor lo dispara aparte.
                continue
            qs = matches_due_for_kind(kind)
            if match_id is not None:
                qs = qs.filter(pk=match_id)
            for match in qs:
                if dry_run:
                    self.stdout.write(f"DRY · {kind} · {match.teams_slug}")
                    continue
                try:
                    result = send_reminder_email(match, kind)
                except Exception as exc:  # noqa: BLE001
                    ko += 1
                    logger.exception("send_reminder_email falló · match=%s kind=%s", match.id, kind)
                    self.stderr.write(f"ERR · {kind} · {match.teams_slug} · {exc}")
                    continue
                if result is None:
                    skipped += 1
                    self.stdout.write(f"SKIP · {kind} · {match.teams_slug} (sin pendientes)")
                else:
                    ok += 1
                    self.stdout.write(f"OK · {kind} · {match.teams_slug}")

        # Si se pidió un match-id concreto que no existe en ninguna ventana, avisar.
        if match_id is not None and (ok + ko + skipped) == 0 and not dry_run:
            if not Match.objects.filter(pk=match_id).exists():
                self.stderr.write(f"send_match_reminders: match {match_id} no existe.")
            else:
                self.stderr.write(
                    f"send_match_reminders: match {match_id} fuera de ventana o ya enviado."
                )
            return

        if not dry_run:
            self.stdout.write(f"send_match_reminders: {ok} OK · {ko} ERR · {skipped} SKIP")
