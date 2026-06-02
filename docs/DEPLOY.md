# Despliegue en PythonAnywhere (LEGACY)

> ⚠️ **Doc legacy.** La aplicación se desplegó originalmente en PythonAnywhere free pero **el despliegue actual está en Railway** (Postgres, Resend SMTP, Cron Service). Para el despliegue vigente consulta **[`docs/DEPLOY_RAILWAY.md`](DEPLOY_RAILWAY.md)**. Este documento se mantiene únicamente como referencia histórica y como ruta de rollback si Railway fallase.

PORRA 26 originalmente estaba pensada para correr en el plan **free de PythonAnywhere** (MySQL incluida, sin tráfico saliente arbitrario, sin SMTP libre). La limitación de SMTP saliente (necesario para el flujo email-driven de Teams) fue la razón principal de migrar a Railway.

## 1. Pre-requisitos en local

- Repositorio versionado.
- `.env.example` revisado y un `.env` propio (NO se sube al repo).

## 2. Primer despliegue

1. Crea cuenta gratuita en https://www.pythonanywhere.com.
2. Abre una **consola Bash** desde el dashboard.
3. Clona el repo:
   ```bash
   git clone https://github.com/<tu-usuario>/apuestas-interna.git ~/apuestas-interna
   cd ~/apuestas-interna
   ```
4. Crea el virtualenv y dependencias:
   ```bash
   mkvirtualenv -p python3.12 porra26
   pip install -r requirements.txt
   ```
   Si `mysqlclient` falla en local pero quieres MySQL en PythonAnywhere, descoméntalo manualmente en `requirements.txt` antes del `pip install` (el servidor tiene las cabeceras de MySQL ya instaladas).
5. Crea la base de datos MySQL desde el panel "Databases":
   - Nombre: `<tu-usuario>$porra26`
   - Anota la contraseña.
6. Crea `.env` en la raíz:
   ```bash
   cp .env.example .env
   nano .env
   ```
   Rellena:
   - `DJANGO_SECRET_KEY` (genera uno con `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
   - `DJANGO_ALLOWED_HOSTS=<tu-usuario>.pythonanywhere.com`
   - `MYSQL_NAME=<tu-usuario>$porra26`
   - `MYSQL_USER=<tu-usuario>`
   - `MYSQL_PASSWORD=<la del paso 5>`
   - `MYSQL_HOST=<tu-usuario>.mysql.pythonanywhere-services.com`
   - `EMAIL_DOMAIN=edisa.com`
7. Aplica migraciones y carga fixtures:
   ```bash
   export DJANGO_SETTINGS_MODULE=porra26.settings.prod
   python manage.py migrate
   python manage.py loaddata fixtures/rounds.json fixtures/teams.json fixtures/world_cup_2026.json
   python manage.py createcachetable
   ```
8. Crea el primer gestor:
   ```bash
   python manage.py createsuperuser
   ```
   El email debe pertenecer al dominio configurado en `EMAIL_DOMAIN`.
9. Recopila estáticos:
   ```bash
   python manage.py collectstatic --no-input
   ```
10. Configura la **Web app** desde el panel "Web":
    - Manual configuration · Python 3.12.
    - WSGI: edita el fichero y deja sólo:
      ```python
      import os, sys
      path = "/home/<tu-usuario>/apuestas-interna"
      if path not in sys.path:
          sys.path.insert(0, path)
      os.environ["DJANGO_SETTINGS_MODULE"] = "porra26.settings.prod"
      from django.core.wsgi import get_wsgi_application
      application = get_wsgi_application()
      ```
    - Virtualenv: `/home/<tu-usuario>/.virtualenvs/porra26`
    - Static files mapping (añadir las dos entradas):
      - URL `/static/` → directorio `/home/<tu-usuario>/apuestas-interna/staticfiles/`
      - URL `/media/` → directorio `/home/<tu-usuario>/apuestas-interna/media/` (los avatares subidos por los jugadores)
    - Asegura que el directorio `media/` existe: `mkdir -p ~/apuestas-interna/media/avatars`
11. Pulsa **Reload**.

## 3. Redeploys

Desde la consola Bash:
```bash
./docs/scripts/deploy.sh
```

## 4. Backup diario

Configura una tarea diaria en "Tasks" del panel:
```bash
PA_USER=<tu-usuario> bash /home/<tu-usuario>/apuestas-interna/docs/scripts/backup.sh
```

## 5. Restablecer contraseña de un jugador desde consola (workaround)

Si la app está caída pero la BD funciona:
```bash
python manage.py shell
>>> from accounts.models import User
>>> u = User.objects.get(email="jugador@edisa.com")
>>> u.set_password("temporal-nueva-XXXX")
>>> u.must_change_password = True
>>> u.save()
```

## 6. Limitaciones del plan free

- **Quota de CPU diaria.** Si se agota, la web sigue funcionando pero las consolas Bash dejan de abrir.
- **Sin SMTP saliente libre.** Sin recordatorios por email; las contraseñas temporales se entregan en pantalla al gestor.
- **MySQL ≈ 512 MB.** Suficiente para ~50 jugadores y ~120 partidos.
- **Dominio:** `<tu-usuario>.pythonanywhere.com` (sin custom domain).

## 7. Token de integración con Teams

La aplicación expone endpoints en `/competicion/api/teams/` que consume un Flow de Power Automate (ver `docs/TEAMS_FLOW.md`). Protegidos con un token Bearer.

1. Genera un token aleatorio de 64+ caracteres:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. En el `.env` de PythonAnywhere añade:

   ```
   TEAMS_API_TOKEN=<token generado>
   PORRA_BASE_URL=https://porra26.pythonanywhere.com
   ```

3. Recarga la web app desde el panel de PythonAnywhere.

4. Configura el flow siguiendo `docs/TEAMS_FLOW.md` pegando el mismo token en sus tres acciones HTTP.

Si `TEAMS_API_TOKEN` queda vacío, los endpoints siguen respondiendo pero **rechazan toda autenticación Bearer**: nunca se debe arrancar producción sin token configurado.
