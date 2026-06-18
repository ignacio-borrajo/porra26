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

El envío se dispara **automáticamente al kickoff** desde cron-job.org → `POST /competicion/api/teams/cierres/disparar/` cada 15 min → `send_closure_email` → Resend → Outlook → Power Automate → Teams. Detalles del job en `docs/TEAMS_FLOW.md` §0. El botón "✉️ Enviar" del gestor en `/competicion/resultados/` sigue funcionando para reenvíos manuales (mismo service detrás, idempotente).

Cada lunes (o tras cualquier jornada del Mundial), abre `/competicion/resultados/` como gestor y revisa la sección **"Estado de envíos a Teams"**:

- Todos los partidos finalizados desde la semana pasada deben aparecer con ✓ en Generado y ✓ en Enviado.
- Si algún partido tiene `kickoff` ya pasado pero `sent_at` vacío, basta con esperar al siguiente disparo del cron (15 min) o pulsar **✉️ Enviar** en su fila para forzarlo.
- Si algún partido aparece con ⏳ (ámbar) o solo Generado ✓ pero Enviado —, sigue esta cadena:

  1. **cron-job.org → History** del job de cierres: confirma que disparó cerca del kickoff. El body de la respuesta dice `{"checked": N, "sent": N, "errors": N}`.
  2. **Resend → Logs** (https://resend.com/logs). El envío debe aparecer como `Delivered`. Si está `Bounced`/`Complained`, problema de destinatario o sender.
  3. **Outlook** (`ignacio.borrajo@edisa.com`): comprueba que el email llegó. Revisa también *Correo no deseado*. Si la regla de PORRA26 lo movió, mira en esa carpeta.
  4. **Power Automate → tu flow → Historial de ejecuciones**: cada ejecución te dice exactamente qué paso falló (trigger, Apply to each, Create file en OneDrive, Post message). Reintenta desde el botón *Resubmit*.
  5. Vuelve al panel del gestor y pulsa **↻ Reenviar** en la fila del partido — fuerza un envío fresco.
  6. Como solución manual de emergencia, descarga el PDF con el botón **📄 PDF** y súbelo al chat de Teams a mano.

Para reenvío masivo desde CLI (varios partidos pendientes tras una incidencia):

```bash
# Lista los pendientes sin enviar
railway run python manage.py send_pending_closures --dry-run

# Envía todos los pendientes (mismos guard-rails que el botón)
railway run python manage.py send_pending_closures

# Envía solo uno
railway run python manage.py send_pending_closures --match-id <id>
```

## Verificar recordatorios pre-cierre

Los recordatorios (2 h y 30 min antes del cierre) los dispara **GitHub Actions**, no Railway. La cadena: GHA cron `*/15` → `POST /competicion/api/recordatorios/disparar/` con Bearer → `send_reminder_email` → Resend → Outlook → Power Automate (flow distinto) → Teams. Detalles del flow en `docs/TEAMS_FLOW.md` §9.

**Si un partido se cerró sin que llegara el aviso a Teams**, sigue esta cadena:

1. **GitHub → Actions → Recordatorios de apuestas**: ¿el cron ejecutó cerca del momento esperado? Si hay un hueco grande (> 1 h), GHA estuvo lento — usa el botón `Run workflow` (workflow_dispatch) para forzar. Aunque sirve poco si el cierre ya pasó: el backend filtra los avisos tardíos.
2. **AuditLog en Django admin**: filtra por `action="bets_reminder_sent"`. Si no hay entrada para ese partido, el envío nunca se ejecutó (probablemente porque GHA no disparó a tiempo o porque no había rezagados al disparar).
3. **`BetsReminderLog` en admin**: filas por `(match, kind)`. Si está vacío es que el cron no llegó a la ventana.
4. **Botón manual** en `/competicion/resultados/` (sección "Próximos"): si el partido aún no ha cerrado, pulsa **✉ Recordatorio** en su fila.
5. **CLI desde Railway**:

   ```bash
   # Dry-run para ver qué se enviaría
   railway run python manage.py send_match_reminders --dry-run

   # Forzar envío para un match concreto
   railway run python manage.py send_match_reminders --match-id <id> --kind T_MINUS_4H
   ```

El pill 🟠 N sin apostar junto al botón muestra cuántos jugadores quedan rezagados en cada momento, calculado en tiempo real al cargar la página.
