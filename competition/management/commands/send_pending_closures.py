import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from competition.models import BET_CLOSE_HOURS, Match
from competition.services.closing_email import send_closure_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envía por email los PDFs de cierre de apuestas pendientes."

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
            help="Envía solo el match indicado (útil para reintentos manuales).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        match_id = options["match_id"]
        now = timezone.now()

        qs = Match.objects.filter(
            kickoff__lte=now + timedelta(hours=BET_CLOSE_HOURS)
        ).select_related("home", "away", "round", "closing_report")
        if match_id is not None:
            qs = qs.filter(pk=match_id)

        pendientes = []
        for m in qs.order_by("kickoff"):
            report = getattr(m, "closing_report", None)
            if report is None or report.sent_at is None:
                pendientes.append(m)

        if match_id is not None and not pendientes:
            self.stderr.write(
                f"send_pending_closures: match {match_id} no existe o ya fue enviado."
            )
            return

        if dry_run:
            self.stdout.write(f"send_pending_closures (dry-run): {len(pendientes)} pendientes")
            for m in pendientes:
                self.stdout.write(f"  - {m.id} · {m.teams_slug}")
            return

        ok = 0
        ko = 0
        for m in pendientes:
            try:
                send_closure_email(m)
                ok += 1
                self.stdout.write(f"OK · {m.teams_slug}")
            except Exception as exc:  # noqa: BLE001
                ko += 1
                logger.exception("send_closure_email falló para match %s", m.id)
                self.stderr.write(f"ERR · {m.teams_slug} · {exc}")

        self.stdout.write(f"send_pending_closures: {ok} OK · {ko} ERR · {len(pendientes)} total")
