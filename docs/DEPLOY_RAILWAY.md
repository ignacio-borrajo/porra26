# Despliegue en Railway

Esta guía sustituye al despliegue en PythonAnywhere (`docs/DEPLOY.md`). El motivo del cambio: Railway permite **tráfico SMTP saliente**, lo que habilita el flujo *email-driven* de Teams (la app envía el PDF de cierre por correo a un buzón corporativo y Power Automate lo recoge y publica en el chat de grupo). Además montamos **PostgreSQL gestionado** y dejamos los avatares en un **volumen persistente**.

> El despliegue queda totalmente declarativo: el repo lleva `Procfile`, `railway.toml`, `runtime.txt` y `.env.railway.example`. Railway autodetecta el resto.

---

## 1. Pre-requisitos

- Cuenta en https://railway.com (la que ya tiene Ignacio).
- Repo conectable a Railway (GitHub).
- Buzón corporativo dedicado al bot (`porra26-bot@edisa.com`) con **contraseña de aplicación** generada en Microsoft 365 (Office 365 no permite SMTP autenticado con la contraseña normal si hay MFA).
- Buzón corporativo destino para los PDFs de cierre (`porra26-cierres@edisa.com`). Power Automate suscribe este buzón.

## 2. Ficheros del repo que Railway usa

Todos están versionados en la raíz:

| Fichero | Para qué sirve |
|---------|----------------|
| `Procfile` | Comandos de `release` (migraciones + collectstatic) y `web` (gunicorn). |
| `railway.toml` | Builder Nixpacks, política de reinicio y *healthcheck* (`/healthz/`). |
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

1. Servicio **web** → pestaña **Settings → Volumes → + New Volume**.
2. Mount path: `/app/media`. Tamaño inicial: 1 GB (suficiente; se puede crecer).

### 3.4 Variables de entorno

Pestaña **Variables** del servicio web → **Raw editor** → pega `.env.railway.example`. Sustituye los `replace-me`:

- `DJANGO_SECRET_KEY` → genera con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `DJANGO_ALLOWED_HOSTS` → tu dominio Railway (`xxx.up.railway.app`) o tu dominio propio si lo enlazas. `prod.py` añade `RAILWAY_PUBLIC_DOMAIN` automáticamente, pero deja al menos uno aquí explícito.
- `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` → cuenta `porra26-bot@edisa.com` + su *app password*.
- `TEAMS_DESTINATION_EMAIL` → buzón que vigila Power Automate.
- `TEAMS_API_TOKEN` → mismo token que pegarás en el flow de Power Automate.

`DATABASE_URL` NO la pegues: viene por referencia del paso 3.2.

### 3.5 Lanzar el deploy

Servicio web → **Deployments → Deploy**. Verás dos fases en los logs:

1. **Build** (Nixpacks): instala Python 3.12 + `requirements.txt`.
2. **Release**: corre `python manage.py migrate --no-input && python manage.py collectstatic --no-input`.
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
- **SMTP de Microsoft 365**: el buzón emisor necesita *App password* (con MFA activa) o, mejor, un *Application access policy* + OAuth2. Esta guía asume *App password* por simplicidad.
- **Volumen `/app/media`**: redimensionable en caliente; los datos no se pierden entre deploys pero **sí se pierden si borras el servicio**. Inclúyelo en el backup si los avatares importan.

## 11. Checklist de corte PA → Railway

- [ ] Postgres aprovisionado y `DATABASE_URL` enlazada.
- [ ] Volumen `/app/media` montado.
- [ ] Variables del paso 3.4 puestas (sin `replace-me`).
- [ ] Primer deploy en verde y `/healthz/` devuelve `ok`.
- [ ] `createsuperuser` ejecutado.
- [ ] Fixtures del Mundial cargadas (o `dump.json` importado).
- [ ] DNS apuntando al dominio Railway si aplica.
- [ ] `TEAMS_DESTINATION_EMAIL` recibiendo un email de prueba (envíalo desde `manage.py shell`).
- [ ] Power Automate reconfigurado para escuchar ese buzón.
- [ ] App de PythonAnywhere puesta en pausa (no eliminada todavía) durante 1-2 semanas por si toca rollback.
