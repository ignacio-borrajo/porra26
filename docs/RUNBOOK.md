# Runbook operativo

## Restaurar backup de MySQL

```bash
gunzip -c ~/backups/porra26-YYYY-MM-DD.sql.gz | mysql -u $MYSQL_USER -p$MYSQL_PASSWORD -h $MYSQL_HOST $MYSQL_NAME
```

## Resetear contraseña a un jugador sin acceder a la app

```bash
cd ~/apuestas-interna
source ~/.virtualenvs/porra26/bin/activate
export DJANGO_SETTINGS_MODULE=porra26.settings.prod
python manage.py shell <<'EOF'
from accounts.models import User
import secrets
u = User.objects.get(email="jugador@edisa.com")
new = secrets.token_urlsafe(9)
u.set_password(new)
u.must_change_password = True
u.save()
print("Nueva contraseña:", new)
EOF
```

## Forzar recálculo de puntos de un partido

```bash
python manage.py shell <<'EOF'
from competition.models import Match
from competition.services.resolve import resolve_match
from accounts.models import User
m = Match.objects.get(pk=42)
gestor = User.objects.filter(role="gestor").first()
resolve_match(m, home=m.result_home, away=m.result_away, actor=gestor)
EOF
```

## Limpiar bloqueos de django-axes

```bash
python manage.py axes_reset
```

## Verificar quota de PythonAnywhere

Desde el panel: **Account** → **Tarpit & CPU usage**.
