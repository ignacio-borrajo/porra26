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

## Verificar envíos a Teams

Cada lunes, abre `/competicion/resultados/` como gestor y revisa la sección **"Estado de envíos a Teams"**:

- Todos los partidos cerrados desde la semana pasada deben aparecer con ✓ en Generado y ✓ en Enviado.
- Si algún partido aparece con ⏳ (ámbar) o solo Generado ✓ pero Enviado —, significa que el flow no consiguió publicar:
  1. Abre https://make.powerautomate.com y revisa el historial del flow `PORRA 26 · Cierre apuestas a Teams`.
  2. Si el error es del conector de Teams, reintenta la ejecución desde Power Automate.
  3. Si el error es de autenticación contra la app, comprueba que `TEAMS_API_TOKEN` coincide en ambos sitios (ver `docs/DEPLOY.md`).
  4. Como solución manual de emergencia, descarga el PDF con el botón "📄 PDF" y súbelo a Teams a mano.
