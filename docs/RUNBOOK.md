# Runbook operativo

> **Despliegue actual: Railway** (Postgres, Resend SMTP, Cron Service). Toda la operativa de este runbook asume Railway. Para el material legacy de PythonAnywhere ver `docs/DEPLOY.md` — se mantiene únicamente como referencia histórica.
>
> Para casi todos los comandos de abajo el patrón es: abrir el shell del servicio web desde el dashboard de Railway (botón ⋮ del último deploy → *Open Shell*), activar el venv (`source /app/.venv/bin/activate`) y exportar el módulo de settings (`export DJANGO_SETTINGS_MODULE=porra26.settings.prod`). Desde local también vale `railway run python manage.py ...` si tienes las deps de prod en `.venv`.

## Restaurar backup de Postgres

Si tienes el plan de pago de Railway hay *Daily backups* en **Database → Backups**. Restaura desde ahí.

Si no, los backups manuales se hacen con el cron de §6 de `DEPLOY_RAILWAY.md`. Para restaurar:

```bash
# Descarga el .sql.gz al local
gunzip -c porra26-YYYY-MM-DD.sql.gz | railway run --service Postgres psql "$DATABASE_URL"
```

## Resetear contraseña a un jugador sin acceder a la app

Desde el shell del servicio web:

```bash
source /app/.venv/bin/activate
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
gestor = User.objects.filter(is_gestor=True).first()
resolve_match(m, home=m.result_home, away=m.result_away, actor=gestor)
EOF
```

## Limpiar bloqueos de django-axes

```bash
python manage.py axes_reset
```

## Verificar uso de Railway (cuota / consumo)

Dashboard del proyecto → **Usage** (gráficas de CPU, RAM y egress por servicio). El plan Hobby tiene una franquicia mensual; cuando se acerca al límite Railway envía email.

## Verificar envíos de cierre por email

El flujo automático es: Cron Service `*/10 min` → `send_pending_closures` → email vía Resend → Outlook → flow → Teams.

Cada lunes (o tras cualquier jornada del Mundial), abre `/competicion/resultados/` como gestor y revisa la sección **"Estado de envíos a Teams"**:

- Todos los partidos cerrados desde la semana pasada deben aparecer con ✓ en Generado y ✓ en Enviado.
- Si algún partido aparece con ⏳ (ámbar) o solo Generado ✓ pero Enviado —, sigue esta cadena:

  1. **Railway → servicio cron → Logs** del último run. Busca `ERR · <slug> · <exc>`. Si hay traza, esa es la causa raíz.
  2. **Resend → Logs** (https://resend.com/logs). El envío debe aparecer como `Delivered`. Si está `Bounced`/`Complained`, problema de destinatario o sender.
  3. **Outlook** (`ignacio.borrajo@edisa.com`): comprueba que el email llegó. Revisa también *Correo no deseado*. Si la regla de PORRA26 lo movió, mira en esa carpeta.
  4. **Power Automate → tu flow → Historial de ejecuciones**: cada ejecución te dice exactamente qué paso falló (trigger, Apply to each, Create file en OneDrive, Post message). Reintenta desde el botón *Resubmit*.
  5. Como solución manual de emergencia, descarga el PDF con el botón **📄 PDF** de la pantalla de Resultados y súbelo al chat de Teams a mano.

Para forzar el reenvío de un match concreto (todo verde excepto el envío real):

```bash
# Limpia el sent_at del match para que send_pending_closures lo vuelva a procesar
python manage.py shell -c "from competition.models import BetsClosingReport; BetsClosingReport.objects.filter(match_id=<id>).update(sent_at=None)"
python manage.py send_pending_closures --match-id <id>
```
