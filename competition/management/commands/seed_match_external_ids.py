"""Rellena `Match.external_id` casando contra el calendario de football-data.org.

Comando one-shot que se ejecuta tras desplegar (o tras añadir partidos KO
cuando los equipos quedan resueltos). Sin esto, el provider de
football-data.org no sabe qué IDs consultar y el endpoint `live/tick/`
devuelve siempre `skipped_no_external_id`.

Match contra nuestro modelo:
- Misma fecha UTC del kickoff (día del año).
- TLA de los equipos coincide con `Team.code` (en cualquier orden, por si
  football-data los lista al revés).

Para partidos KO sin equipos resueltos todavía en BD (`home_id`/`away_id`
nulos) no podemos casar — vuelve a ejecutar el comando cuando los equipos
estén asignados.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from competition.models import Match

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Casa partidos contra football-data.org y rellena Match.external_id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Sobreescribe external_id ya asignados (uso normal: solo rellena vacíos).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Imprime los matches que se rellenarían pero no persiste.",
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, "FOOTBALL_DATA_API_KEY", "") or ""
        if not api_key:
            raise CommandError(
                "FOOTBALL_DATA_API_KEY vacía. Configura la variable en Railway "
                "(o en .env local) antes de ejecutar este comando."
            )
        competition = getattr(settings, "FOOTBALL_DATA_COMPETITION", "WC")
        base_url = "https://api.football-data.org/v4"

        params = urlencode({})  # sin filtros: queremos todo el calendario
        url = f"{base_url}/competitions/{competition}/matches?{params}"
        request = Request(
            url,
            headers={"X-Auth-Token": api_key, "Accept": "application/json"},
        )
        self.stdout.write(f"Consultando {url}…")
        with urlopen(request, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        fd_matches = payload.get("matches", [])
        self.stdout.write(f"Recibidos {len(fd_matches)} partidos de football-data.")

        force = options["force"]
        dry_run = options["dry_run"]

        candidates = Match.objects.select_related("home", "away").filter(
            home__isnull=False, away__isnull=False
        )
        if not force:
            candidates = candidates.filter(external_id__isnull=True) | candidates.filter(
                external_id=""
            )

        by_key: dict[tuple[str, frozenset[str]], list[Match]] = defaultdict(list)
        for m in candidates:
            key = (m.kickoff.date().isoformat(), frozenset({m.home_id, m.away_id}))
            by_key[key].append(m)

        matched = skipped_unknown = skipped_already = 0
        for fd in fd_matches:
            home = (fd.get("homeTeam") or {}).get("tla")
            away = (fd.get("awayTeam") or {}).get("tla")
            utc = fd.get("utcDate")
            fd_id = fd.get("id")
            if not (home and away and utc and fd_id):
                continue
            try:
                day = datetime.fromisoformat(utc.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                continue

            key = (day, frozenset({home, away}))
            ours = by_key.get(key, [])
            if not ours:
                skipped_unknown += 1
                continue
            target = ours[0]
            if target.external_id and not force:
                skipped_already += 1
                continue
            new_id = str(fd_id)
            self.stdout.write(
                f"  {target.home_id} vs {target.away_id} @ {day} → external_id={new_id}"
            )
            if not dry_run:
                target.external_id = new_id
                target.save(update_fields=["external_id"])
            matched += 1

        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: no se ha persistido nada."))
        self.stdout.write(
            self.style.SUCCESS(
                f"Casados: {matched} · sin coincidencia local: {skipped_unknown} · "
                f"ya tenían external_id: {skipped_already}"
            )
        )
