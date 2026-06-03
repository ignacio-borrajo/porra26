# Despliegue en Railway

Esta guía sustituye al despliegue en PythonAnywhere (`docs/DEPLOY.md`). El motivo del cambio: Railway permite **tráfico SMTP saliente**, lo que habilita el flujo *email-driven* de Teams (la app envía el PDF de cierre por correo a un buzón corporativo y Power Automate lo recoge y publica en el chat de grupo). Además montamos **PostgreSQL gestionado** y dejamos los avatares en un **volumen persistente**.

> El despliegue queda totalmente declarativo: el repo lleva `Procfile`, `railway.toml`, `runtime.txt` y `.env.railway.example`. Railway autodetecta el resto.

---

## 1. Pre-requisitos

- Cuenta en https://railway.com (la que ya tiene Ignacio).
- Repo conectable a Railway (GitHub).
- Cuenta en https://resend.com como proveedor SMTP saliente. **No requiere dominio propio**: con el remitente de pruebas `onboarding@resend.dev` se puede enviar a la dirección con la que te registras en Resend, que es justo lo que necesita el flujo (la app envía a tu propio buzón corporativo). Tier gratuito: 100 emails/día, 3 000/mes.
- Tu buzón corporativo (`ignacio.borrajo@edisa.com`) actúa como destino: ahí caen los PDFs y desde ahí los recoge Power Automate. No hace falta crear un buzón dedicado en M365.

## 2. Ficheros del repo que Railway usa

Todos están versionados en la raíz:

| Fichero | Para qué sirve |
|---------|----------------|
| `Procfile` | Comando `web` (gunicorn). Las migraciones viven en `preDeployCommand` de `railway.toml`, no en un `release:` del Procfile (este último corre en build-time sin acceso a Postgres). |
| `railway.toml` | Builder Railpack, `preDeployCommand` (migrate + collectstatic), política de reinicio y *healthcheck* (`/healthz/`). |
| `runtime.txt` | Pin de Python 3.12.x. |
| `requirements.txt` | Incluye ya `psycopg`, `dj-database-url`, `gunicorn` y `whitenoise`. |
| `.env.railway.example` | Plantilla de variables a pegar en el panel "Variables" del servicio. |
| `porra26/settings/prod.py` | Lee `DATABASE_URL`, sirve estáticos con Whitenoise, fuerza HTTPS detrás del proxy de Railway y configura SMTP. |

## 3. Primer despliegue

### 3.1 Crear proyecto y conectar GitHub

1. En Railway → **New Project → Deploy from GitHub repo** y selecciona `apuestas-interna`.
2. Railway crea un primer build automático. **Cancélalo** si arranca antes de añadir Postgres y variables: fallará y rebooteará. No pasa nada, lo retomamos en el paso 3.4.

### 3.2 Añadir Postgres

1. Dentro del proyecto: **+ New → Database → Add PostgreSQL**.
2. Cuando termine de aprovisionarse, abre el servicio **web** → pestaña **Variables** → **+ New Variable Reference** y selecciona `DATABASE_URL` del servicio Postgres. A partir de ahora, cada cambio de credenciales en Postgres se propaga solo.

### 3.3 Añadir volumen para `/media`

Los avatares se guardan en `media/avatars/`. Si no hay volumen, se pierden en cada redeploy.

Railway ya no expone los volúmenes dentro de `Settings` del servicio: se crean desde el canvas del proyecto. Usa cualquiera de estos caminos:

- **Command Palette**: pulsa `⌘K` (Mac) o `Ctrl+K` (Windows/Linux), escribe `Create Volume` y selecciónalo.
- **Click derecho** sobre el área vacía del canvas → *Create* → **Volume**.
- Botón **+ New** (arriba a la derecha) → **Volume** (si aparece en tu cuenta).

Configuración:

1. Cuando te pida el servicio, elige el servicio **web**.
2. **Mount path**: `/app/media`.
3. Tamaño inicial: 1 GB (redimensionable en caliente).

Tras crearlo verás un nodo de *Volume* nuevo en el canvas conectado al servicio web; abriéndolo puedes ajustar tamaño y consultar el uso.

### 3.4 Variables de entorno

Antes de pegar nada, **crea una API key en Resend**: panel → *API Keys* → *Create API Key* → permiso *Sending access* → cópiala (se muestra una sola vez).

Pestaña **Variables** del servicio web → **Raw editor** → pega `.env.railway.example`. Sustituye los `replace-me`:

- `DJANGO_SETTINGS_MODULE=porra26.settings.prod` → imprescindible. Sin esto, `manage.py` cae a `dev` (SQLite local) y los comandos `railway run python manage.py …` no tocan Postgres. `wsgi.py` ya fuerza prod para el servicio web, pero los comandos administrativos necesitan verla en el entorno inyectado.
- `DJANGO_SECRET_KEY` → genera con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `DJANGO_ALLOWED_HOSTS` → tu dominio Railway (`xxx.up.railway.app`) o tu dominio propio si lo enlazas. `prod.py` añade `RAILWAY_PUBLIC_DOMAIN` automáticamente, pero deja al menos uno aquí explícito.
- `EMAIL_HOST_PASSWORD` → la API key de Resend que acabas de generar. `EMAIL_HOST_USER` se queda en el literal `resend` (Resend espera ese usuario fijo en SMTP).
- `DEFAULT_FROM_EMAIL` → mientras no haya dominio propio, déjalo en `PORRA 26 <onboarding@resend.dev>`. Si más adelante verificas un dominio en Resend (ver §12), cámbialo a `PORRA 26 <bot@tu-dominio>`.
- `TEAMS_DESTINATION_EMAIL` → tu buzón corporativo personal (`ignacio.borrajo@edisa.com`). Tiene que coincidir con la dirección con la que te registraste en Resend mientras estés en modo sin dominio verificado.
- `TEAMS_API_TOKEN` → mismo token que pegarás en el flow de Power Automate (opción B del §8). Si solo usas el flujo *email-driven* (opción A), no hace falta tocarlo, pero conviene dejar un valor aleatorio para no exponer el endpoint REST.

`DATABASE_URL` NO la pegues: viene por referencia del paso 3.2.

### 3.5 Lanzar el deploy

Servicio web → **Deployments → Deploy**. Verás tres fases en los logs:

1. **Build** (Railpack): instala Python 3.12 + `requirements.txt`.
2. **Pre-Deploy**: corre `DJANGO_SETTINGS_MODULE=porra26.settings.prod python manage.py migrate --no-input && ... collectstatic --no-input` (definido en `railway.toml → [deploy].preDeployCommand`). Ya tiene red privada y variables, así que conecta con Postgres.
3. **Web**: arranca gunicorn en el puerto `$PORT`.

Si el *healthcheck* en `/healthz/` responde 200, Railway marca el deploy como `SUCCESS` y enruta el tráfico.

### 3.6 Primer gestor

Abre un **Shell** del servicio (botón ⋮ en el deploy) o desde local con el CLI:

```bash
railway link  # vincula carpeta local a tu proyecto
railway run python manage.py createsuperuser
```

El email debe pertenecer al dominio de `EMAIL_DOMAIN`.

### 3.7 Cargar fixtures del Mundial

Solo la primera vez (después ya está en Postgres):

```bash
railway run python manage.py loaddata fixtures/rounds.json fixtures/teams.json fixtures/world_cup_2026.json
railway run python manage.py createcachetable
```

## 4. Migrar datos desde SQLite (si ya hay jugadores y pronósticos en local)

Si el SQLite local tiene datos que merece la pena conservar:

```bash
# 1) En local, contra dev (SQLite). Genera dump.json en la raíz.
./docs/scripts/export_sqlite_to_json.sh

# 2) Sube y carga en Railway (Postgres).
railway run python manage.py loaddata dump.json
```

El script excluye `contenttypes`, `auth.Permission`, `admin.LogEntry`, `sessions` y `axes` para que Postgres pueda regenerarlas sin chocar con IDs.

## 5. Redeploys

Cada `git push` a `main` dispara un deploy automático (si lo dejas activado en **Settings → Service → Source**). El `release` aplica migraciones y `collectstatic` antes de arrancar gunicorn, así que basta con hacer push.

Para un redeploy manual:

```bash
railway up         # sube el árbol actual y dispara build
# o desde la UI: Deployments → ⋮ → Redeploy
```

## 6. Backup diario de Postgres

Railway no automatiza backups en el plan gratuito; en planes de pago tiene *Daily backups* en **Database → Backups**.

Solución manual: añade un **Cron Job** como nuevo servicio en el mismo proyecto:

1. **+ New → Empty Service → Settings → Cron Schedule**: `0 3 * * *`.
2. Comando:

   ```bash
   pg_dump "$DATABASE_URL" | gzip > /tmp/porra26-$(date +%F).sql.gz && \
     curl -F "file=@/tmp/porra26-$(date +%F).sql.gz" "$BACKUP_UPLOAD_URL"
   ```

   Donde `BACKUP_UPLOAD_URL` apunta a un endpoint privado (S3 firmado, Drive, …). Si solo queréis retener una semana en el propio Railway, monta otro volumen y guarda ahí.

## 7. Restablecer contraseña de un jugador

```bash
railway run python manage.py shell
>>> from accounts.models import User
>>> u = User.objects.get(email="jugador@edisa.com")
>>> u.set_password("temporal-nueva-XXXX")
>>> u.must_change_password = True
>>> u.save()
```

## 8. Token de integración con Teams

La aplicación expone los endpoints en `/competicion/api/teams/` (`docs/TEAMS_FLOW.md`). El nuevo flujo *email-driven* hace que la app **envíe el PDF por correo** además de exponer el endpoint REST. Power Automate puede:

- **Opción A (email-driven)**: vigilar `TEAMS_DESTINATION_EMAIL` con el trigger *When a new email arrives* y publicar el adjunto en el chat. No necesita el token Bearer.
- **Opción B (HTTP polling, la actual)**: seguir consumiendo `/cierres-pendientes/`. Necesita `TEAMS_API_TOKEN`.

Ambas opciones pueden convivir mientras se valida el switch. El token se rota igual que antes:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
# Pega el nuevo valor en Railway → Variables → TEAMS_API_TOKEN y reinicia el servicio.
```

## 9. Dominio propio (opcional)

Servicio web → **Settings → Domains → + Custom Domain**, añade `porra26.edisa.com`, copia el CNAME a Cloudflare/DNS corporativo. Railway termina TLS automáticamente (Let's Encrypt). Recuerda añadir el dominio a `DJANGO_ALLOWED_HOSTS`.

## 10. Limitaciones a vigilar

- **Plan**: Railway cobra por uso (CPU/RAM/egress). Para ~50 jugadores el consumo es ínfimo, pero conviene monitorizar el primer mes.
- **Egress**: cada PDF enviado por SMTP cuenta como tráfico saliente. Despreciable a este volumen.
- **Puerto SMTP 587 bloqueado**: Railway no permite tráfico saliente por el 587 (medida antispam habitual en cloud providers). Usamos el **2587** de Resend, que es el mismo SMTP con STARTTLS pero por un puerto sin bloqueo. Si algún día migras de proveedor, comprueba sus puertos alternativos.
- **SMTP de Resend (modo sin dominio)**: usando `onboarding@resend.dev` solo se puede enviar a la dirección con la que te registraste. Esto encaja con el flujo actual (la app se envía al buzón que vigila Power Automate). Si el día de mañana hay varios destinatarios o quieres un remitente "de marca", verifica un dominio (ver §12).
- **Resend free tier**: 100 envíos/día, 3 000/mes. Una porra del Mundial con ~50 jugadores no se acerca. Si lo superas, el siguiente tier es de pago.
- **Volumen `/app/media`**: redimensionable en caliente; los datos no se pierden entre deploys pero **sí se pierden si borras el servicio**. Inclúyelo en el backup si los avatares importan.

## 11. Checklist de corte PA → Railway

- [ ] Cuenta en Resend creada con el email que actuará de destinatario (`ignacio.borrajo@edisa.com`) y API key generada.
- [ ] Postgres aprovisionado y `DATABASE_URL` enlazada.
- [ ] Volumen `/app/media` montado.
- [ ] Variables del paso 3.4 puestas (sin `replace-me`).
- [ ] Primer deploy en verde y `/healthz/` devuelve `ok`.
- [ ] `createsuperuser` ejecutado.
- [ ] Fixtures del Mundial cargadas (o `dump.json` importado).
- [ ] DNS apuntando al dominio Railway si aplica.
- [ ] `TEAMS_DESTINATION_EMAIL` recibiendo un email de prueba (envíalo desde `manage.py shell` — ver §13).
- [ ] Regla en Outlook que mueve los correos con asunto `[PORRA26]` a una carpeta dedicada (evita ruido en bandeja y facilita el filtro de Power Automate).
- [ ] Power Automate reconfigurado: trigger *When a new email arrives (V3)* con `From = onboarding@resend.dev` y `Subject Filter = [PORRA26][CIERRE]`.
- [ ] App de PythonAnywhere puesta en pausa (no eliminada todavía) durante 1-2 semanas por si toca rollback.

## 12. Migrar a dominio propio en Resend (opcional)

Mientras uses `onboarding@resend.dev` el remitente es genérico y Outlook puede aplicarle filtros antispam. Cuando quieras "dignificar" el envío:

1. Registra un dominio barato (porkbun, namecheap, ~8-12 €/año) o usa un subdominio que controles (`porra.tu-dominio.com`).
2. En Resend → *Domains → Add Domain* → introduce el dominio y copia los 3 registros DNS que muestra (SPF, DKIM y MX opcional para *return path*).
3. Pega los registros en el panel DNS del registrar y espera unos minutos. Resend marca el dominio como *Verified* en cuanto los detecta.
4. En Railway → Variables: cambia `DEFAULT_FROM_EMAIL` a `PORRA 26 <bot@tu-dominio>` y reinicia el servicio.
5. En Power Automate ajusta el filtro `From` al nuevo remitente.

Ya no hace falta que el destinatario coincida con la cuenta de Resend: puedes enviar a cualquier dirección.

## 13. Prueba de envío de extremo a extremo

Desde local con CLI:

```bash
railway run python manage.py shell
>>> from django.core.mail import EmailMessage
>>> msg = EmailMessage(
...     subject="[PORRA26][TEST] Smoke test SMTP",
...     body="Si llegas a mi buzón, Resend va bien.",
...     to=["ignacio.borrajo@edisa.com"],
... )
>>> msg.send()
1
```

En el panel de Resend → *Logs* verás el envío como `Delivered`. Si aparece como `Bounced` o `Complained`, revisa que `to` coincide con la cuenta con la que te registraste (restricción del modo sin dominio verificado).

## 14. Envío del PDF de cierre a Teams

El envío no es automático por cron — lo dispara el **gestor** desde la UI con un botón. Razón: la porra son ~104 partidos en todo el Mundial; un cron `*/10 min` haría miles de invocaciones para mover solo 100 emails (mal ratio), y el gestor ya entra a la plataforma para introducir el resultado oficial, así que pulsar el botón es trivial.

### 14.1 Disparo desde la UI

1. Gestor → `/competicion/resultados/`.
2. En la fila del partido (sección **PENDIENTES** o **FINALIZADOS**) hay un botón **✉️ Enviar** que llama al endpoint `POST /competicion/api/teams/cierres/<id>/enviar/`.
3. Si el match ya tiene `BetsClosingReport.sent_at` fijado, el botón se transforma en **↻ Reenviar** y vuelve a generar + enviar (resetea `sent_at` antes de llamar al service).
4. Tras enviar, la página se recarga y el toast superior muestra "PDF enviado a Teams para X vs Y".

El endpoint acepta sesión de gestor o `Authorization: Bearer <TEAMS_API_TOKEN>`. Detecta navegador vs API por la cabecera `Accept`: si el cliente pide HTML, redirige a la pantalla de Resultados con mensaje flash; si es API, devuelve JSON `{match_id, sent_at}`.

### 14.2 Reenvío masivo desde CLI (emergencia)

El comando `send_pending_closures` se mantiene como herramienta de batch para casos extremos (caída del SMTP durante la fase de grupos, varios partidos pendientes de reenviar tras una incidencia):

```bash
# Lista lo que mandaría sin hacerlo
railway run python manage.py send_pending_closures --dry-run

# Envía solo un partido concreto
railway run python manage.py send_pending_closures --match-id <id>

# Envía todos los pendientes (los que tengan kickoff − 2h pasado y sent_at NULL)
railway run python manage.py send_pending_closures
```

No hay cron service enlazado al comando — corre solo cuando lo invocas explícitamente.

### 14.3 Observabilidad

- **Resend → Logs**: una entrada por email enviado con estado `Delivered`.
- **Railway → servicio web → Logs**: el endpoint logea cualquier excepción de SMTP. Si `send_closure_email` lanza, el botón devuelve 500 y la UI mostraría el error de Django.
- **BD**: `BetsClosingReport.sent_at`, `attempts` y `last_sha256` se actualizan en cada envío. `accounts.AuditLog` lleva `action="bets_pdf_emailed"` con el match y destinatario.
- **UI**: la sección colapsable *"ESTADO DE ENVÍOS A TEAMS"* de `/competicion/resultados/` lista todos los `BetsClosingReport` con su estado (Generado / Enviado / Intentos / Última generación).
