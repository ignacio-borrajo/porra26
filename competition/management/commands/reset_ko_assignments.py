from django.core.management.base import BaseCommand
from django.db.models import Q

from competition.models import Match, Prediction

KO_ROUND_IDS = ("r32", "r16", "qf", "sf", "final")


class Command(BaseCommand):
    help = (
        "Nulifica los equipos y borra los pronósticos de los cruces de "
        "eliminatoria SIN resultado oficial. Sirve para limpiar los cruces "
        "creados/auto-asignados de forma incorrecta. Usa --dry-run para "
        "previsualizar sin escribir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista lo que se haría sin modificar la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # No finalizados: excluimos los que tienen ambos marcadores.
        unfinished_ko = Match.objects.filter(round_id__in=KO_ROUND_IDS).exclude(
            result_home__isnull=False, result_away__isnull=False
        )
        affected = unfinished_ko.filter(Q(home__isnull=False) | Q(away__isnull=False))
        affected_ids = list(affected.values_list("id", flat=True))
        pred_count = Prediction.objects.filter(match_id__in=affected_ids).count()

        if dry_run:
            self.stdout.write(
                f"[dry-run] {len(affected_ids)} cruce(s) KO se nulificarían y "
                f"{pred_count} pronóstico(s) se borrarían."
            )
            return

        Prediction.objects.filter(match_id__in=affected_ids).delete()
        Match.objects.filter(id__in=affected_ids).update(home=None, away=None)
        self.stdout.write(
            self.style.SUCCESS(
                f"Reseteados {len(affected_ids)} cruce(s) KO y borrados {pred_count} pronóstico(s)."
            )
        )
