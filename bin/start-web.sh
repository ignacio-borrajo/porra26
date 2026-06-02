#!/usr/bin/env bash
# Script de arranque del servicio web en Railway.
# Lo invoca el Procfile (`web: bash bin/start-web.sh`) en lugar de encadenar
# comandos con `&&` directamente en el Procfile: Railpack puede ejecutar la
# línea del Procfile con `exec` sin shell intermedio, en cuyo caso los
# operadores `&&` se ignoran y solo se lanza el primer comando.
#
# Por qué collectstatic vive aquí y no en preDeployCommand (railway.toml):
# Railway corre el preDeployCommand en un contenedor efímero distinto al del
# web service; los ficheros que escribe en /app/staticfiles no llegan al
# runtime y gunicorn loguea `No directory at: /app/staticfiles/`. Aquí, en el
# arranque del propio web, los estáticos se generan en el FS del contenedor
# que sirve el tráfico.
set -euo pipefail

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-porra26.settings.prod}"

echo "[start-web] Running collectstatic..."
python manage.py collectstatic --no-input

echo "[start-web] Starting gunicorn..."
exec gunicorn porra26.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers 2 \
    --threads 2 \
    --timeout 60 \
    --log-file -
