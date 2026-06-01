"""Carga el calendario del Mundial 2026: 48 selecciones + 72 partidos de fase de grupos.

Idempotente. Clave funcional de un partido: (round, group, matchday, home, away).
Las selecciones se identifican por su `code`. Con --prune borra partidos en `groups`
que no estén en el calendario canónico (junto a sus pronósticos).
"""

import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from competition.models import Match, Round, Team

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


class Command(BaseCommand):
    help = "Carga el calendario del Mundial 2026 (48 equipos + 72 partidos de grupos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Borra partidos de 'groups' que no estén en el calendario canónico.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué haría sin tocar la BD.",
        )

    @transaction.atomic
    def handle(self, *, prune: bool, dry_run: bool, **opts):
        if not Round.objects.filter(id="groups").exists():
            raise CommandError(
                "Falta la ronda 'groups'. Carga primero fixtures/rounds.json: "
                "python manage.py loaddata fixtures/rounds.json"
            )

        teams = _load_json("teams.json")
        matches = _load_json("world_cup_2026.json")

        created_t, updated_t = 0, 0
        for entry in teams:
            code = entry["pk"]
            fields = entry["fields"]
            _, created = Team.objects.update_or_create(
                code=code,
                defaults={"name": fields["name"], "flag": fields["flag"]},
            )
            if created:
                created_t += 1
            else:
                updated_t += 1

        created_m, updated_m, unchanged_m = 0, 0, 0
        canonical_keys = set()
        for entry in matches:
            f = entry["fields"]
            key = (f["round"], f["group"], f["matchday"], f["home"], f["away"])
            canonical_keys.add(key)
            kickoff = _parse_dt(f["kickoff"])
            obj, created = Match.objects.update_or_create(
                round_id=f["round"],
                group=f["group"],
                matchday=f["matchday"],
                home_id=f["home"],
                away_id=f["away"],
                defaults={"kickoff": kickoff},
            )
            if created:
                created_m += 1
            elif obj.kickoff != kickoff:
                updated_m += 1
            else:
                unchanged_m += 1

        orphans = []
        for m in Match.objects.filter(round_id="groups").select_related("home", "away"):
            key = (m.round_id, m.group, m.matchday, m.home_id, m.away_id)
            if key not in canonical_keys:
                orphans.append(m)

        pruned = 0
        if orphans:
            if prune:
                for o in orphans:
                    o.delete()
                    pruned += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"{len(orphans)} partido(s) huérfano(s) en 'groups' (no en fixture). "
                        "Ejecuta con --prune para borrarlos."
                    )
                )

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(self.style.NOTICE("DRY RUN — sin cambios persistidos"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Equipos: +{created_t} creados, ~{updated_t} actualizados "
                f"(total {Team.objects.count()}).\n"
                f"Partidos: +{created_m} creados, ~{updated_m} actualizados, "
                f"={unchanged_m} sin cambios "
                f"(total {Match.objects.filter(round_id='groups').count()}).\n"
                f"Huérfanos: {len(orphans)} "
                f"({'borrados' if prune else 'intactos'}, pruned={pruned})."
            )
        )


def _load_json(filename: str):
    path = FIXTURES_DIR / filename
    if not path.exists():
        raise CommandError(f"No existe el fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt
