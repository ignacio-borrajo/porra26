#!/usr/bin/env bash
set -euo pipefail
cd ~/apuestas-interna
git pull
source ~/.virtualenvs/porra26/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --no-input
PA_USER="${PA_USER:-$(whoami)}"
touch "/var/www/${PA_USER}_pythonanywhere_com_wsgi.py"
echo "Deploy OK · WSGI reloaded."
