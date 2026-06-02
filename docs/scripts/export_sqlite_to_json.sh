#!/usr/bin/env bash
# Exporta la BD de desarrollo (SQLite) a un JSON que luego se carga en
# la BD de Railway (Postgres) con `manage.py loaddata`.
#
# Uso (desde la raíz del repo, en local):
#   ./docs/scripts/export_sqlite_to_json.sh
#
# Genera dump.json en la raíz. Para cargarlo en Railway:
#   railway run python manage.py loaddata dump.json
# (o desde un Shell de Railway tras `pg_dump` no aplica: aquí migramos datos
#  vía JSON, no a nivel de motor, porque cambia de SQLite a Postgres).
set -euo pipefail
cd "$(dirname "$0")/../.."

DJANGO_SETTINGS_MODULE=porra26.settings.dev \
python manage.py dumpdata \
  --natural-foreign --natural-primary --indent 2 \
  -e contenttypes -e auth.Permission -e admin.LogEntry \
  -e sessions -e axes \
  > dump.json

echo "Volcado SQLite → dump.json ($(wc -l < dump.json) líneas)"
echo "Siguiente paso: railway run python manage.py loaddata dump.json"
