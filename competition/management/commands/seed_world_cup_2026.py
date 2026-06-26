"""Carga el calendario del Mundial 2026: 48 selecciones + 72 partidos de grupos + 31 KO.

Idempotente. Claves funcionales:
- Partidos de grupos (sin `bracket_code`): `(round, group, matchday, home, away)`.
- Partidos KO (con `bracket_code`): el propio `bracket_code` (único).

Las selecciones se identifican por su `code`. Con `--prune` borra partidos de `groups`
que no estén en el calendario canónico (junto a sus pronósticos). Los KO no se podan.
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
    help = "Carga el calendario del Mundial 2026 (48 equipos + 72 grupos + 31 KO)."

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

        created_g, updated_g, unchanged_g = 0, 0, 0
        created_ko, updated_ko, unchanged_ko = 0, 0, 0
        canonical_groups: set = set()

        for entry in matches:
            f = entry["fields"]
            kickoff = _parse_dt(f["kickoff"])
            bracket_code = f.get("bracket_code")

            if bracket_code:
                # Partido KO: key = bracket_code.
                # En CREACIÓN tomamos home/away del fixture (normalmente null).
                # En ACTUALIZACIÓN nunca pisamos home/away ya asignados (por
                # propagación o por el gestor); solo refrescamos slots/kickoff.
                existing = Match.objects.filter(bracket_code=bracket_code).first()
                if existing is None:
                    Match.objects.create(
                        bracket_code=bracket_code,
                        round_id=f["round"],
                        group=f["group"],
                        matchday=f.get("matchday"),
                        home_id=f.get("home"),
                        away_id=f.get("away"),
                        home_slot=f.get("home_slot", ""),
                        away_slot=f.get("away_slot", ""),
                        bracket_order=f.get("bracket_order"),
                        kickoff=kickoff,
                    )
                    created_ko += 1
                else:
                    changed = False
                    if existing.kickoff != kickoff:
                        existing.kickoff = kickoff
                        changed = True
                    new_home_slot = f.get("home_slot", "")
                    new_away_slot = f.get("away_slot", "")
                    if existing.home_slot != new_home_slot:
                        existing.home_slot = new_home_slot
                        changed = True
                    if existing.away_slot != new_away_slot:
                        existing.away_slot = new_away_slot
                        changed = True
                    if existing.group != f["group"]:
                        existing.group = f["group"]
                        changed = True
                    if existing.round_id != f["round"]:
                        existing.round_id = f["round"]
                        changed = True
                    new_order = f.get("bracket_order")
                    if existing.bracket_order != new_order:
                        existing.bracket_order = new_order
                        changed = True
                    if changed:
                        existing.save()
                        updated_ko += 1
                    else:
                        unchanged_ko += 1
            else:
                # Partido de grupos: key = (round, group, matchday, home, away)
                key = (f["round"], f["group"], f["matchday"], f["home"], f["away"])
                canonical_groups.add(key)
                obj, created = Match.objects.update_or_create(
                    round_id=f["round"],
                    group=f["group"],
                    matchday=f["matchday"],
                    home_id=f["home"],
                    away_id=f["away"],
                    defaults={"kickoff": kickoff},
                )
                if created:
                    created_g += 1
                elif obj.kickoff != kickoff:
                    updated_g += 1
                else:
                    unchanged_g += 1

        orphans = []
        for m in Match.objects.filter(round_id="groups").select_related("home", "away"):
            key = (m.round_id, m.group, m.matchday, m.home_id, m.away_id)
            if key not in canonical_groups:
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

        # IMPORTANTE: contar antes del set_rollback. Tras marcar la transacción
        # para rollback, Django/Postgres prohíbe ejecutar más queries hasta
        # cerrar el bloque atomic — SQLite es más permisivo, por eso este bug
        # solo se manifestaba en producción.
        teams_total = Team.objects.count()
        groups_total = Match.objects.filter(round_id="groups").count()
        ko_total = Match.objects.exclude(round_id="groups").count()

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(self.style.NOTICE("DRY RUN — sin cambios persistidos"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Equipos: +{created_t} creados, ~{updated_t} actualizados "
                f"(total {teams_total}).\n"
                f"Grupos: +{created_g} creados, ~{updated_g} actualizados, "
                f"={unchanged_g} sin cambios (total {groups_total}).\n"
                f"KO: +{created_ko} creados, ~{updated_ko} actualizados, "
                f"={unchanged_ko} sin cambios (total {ko_total}).\n"
                f"Huérfanos en grupos: {len(orphans)} "
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
