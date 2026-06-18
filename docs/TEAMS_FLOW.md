# Flujo de Power Automate — Cierre de apuestas a Teams

Esta guía describe cómo configurar el *flow* que recibe los emails de cierre que envía PORRA 26 y los publica en el chat de grupo de Teams. Usa **solo conectores estándar** (Outlook + Teams) — sin licencia Power Automate Premium.

> **Disparo del envío:** desde 2026-06-11 el envío se dispara automáticamente al cierre del partido vía cron-job.org → `POST /competicion/api/teams/cierres/disparar/` (ver §9.1). El botón **✉️ Enviar** del gestor en `/competicion/resultados/` sigue existiendo para reintentos o reenvíos forzados.
>
> Versiones anteriores: la primera usaba acciones HTTP premium en Power Automate (descartada por coste). La segunda movía todo a on-demand desde el panel del gestor (descartada porque dependía de que el gestor recordase pulsar; los jugadores quieren ver el PDF al pitido inicial). La versión vigente combina cron-job.org + botón de reintento.

## Arquitectura del flujo end-to-end

```
cron-job.org cada 15 min                    Gestor (opcional, reintentos)
   └─ POST /competicion/api/teams/         └─ /competicion/resultados/
      cierres/disparar/                       └─ pulsa "✉️ Enviar"
         └─ por cada match con kickoff<=now      └─ POST /cierres/<id>/enviar/
            y sent_at vacío:
            send_closure_email(match)
               └─ EmailMessage con PDF adjunto
                   ↓ SMTP puerto 2587
               Resend (smtp.resend.com:2587)
                   ↓
               Outlook (ignacio.borrajo@edisa.com)
                   ↓ trigger "When a new email arrives (V3)"
               Power Automate flow
                   ↓ acción "Post message in a chat or channel"
               Teams chat de grupo (PDF como adjunto)
```

## Prerrequisitos

- Cuenta de Microsoft 365 con licencia Power Automate Standard (incluida en la mayoría de planes Business).
- Pertenencia al chat de grupo de Teams de destino.
- Railway con SMTP de Resend configurado por el puerto 2587 (ver `docs/DEPLOY_RAILWAY.md` §3.4).
- Job en cron-job.org apuntando a `POST /competicion/api/teams/cierres/disparar/` (ver §0).
- Botón **✉️ Enviar** visible en el panel del gestor en `/competicion/resultados/` para reenvíos manuales (ver `docs/DEPLOY_RAILWAY.md` §14).
- Para probar antes de tener un partido finalizado: `railway run python manage.py send_pending_closures --match-id <id>` desde local. Disparable también desde el botón si el partido ya está cerrado o tiene resultado registrado.

## 0. Disparador automático: cron-job.org

El envío se dispara desde un job en [cron-job.org](https://cron-job.org) — mismo servicio que ya usamos para `live_tick` y para los recordatorios pre-cierre. El job se configura desde el dashboard y **no vive en el repo**:

| Campo | Valor |
|---|---|
| URL | `https://laporradeljefe.es/competicion/api/teams/cierres/disparar/` |
| Método | `POST` |
| Schedule | cada 15 min |
| Header | `Authorization: Bearer <TEAMS_API_TOKEN>` (mismo valor que la env var de Railway). |

Cada disparo hace POST al endpoint y el backend recorre todos los `Match` con `kickoff <= now` y `BetsClosingReport.sent_at` vacío, enviando un email por cada uno. El service es idempotente: una vez `sent_at` queda fijado el siguiente disparo lo ignora. La respuesta es JSON con `{"checked": N, "sent": N, "errors": N}` y queda en los logs del job para auditoría.

**Por qué cron-job.org y no automático en el resolve del gestor:** los jugadores quieren ver el PDF en Teams **al pitido inicial**, no cuando el gestor mete el resultado oficial (que puede llegar horas después). El PDF muestra solo los pronósticos (sin marcador) si el resultado todavía no se ha registrado — `closing_report.py` pinta "VS" en vez del marcador.

Para disparo manual desde cron-job.org: cualquier job tiene botón **Run now**.

## 1. Crear regla en Outlook (recomendado)

Antes de crear el flow conviene asegurar que los emails llegan a una carpeta dedicada — evita ruido en bandeja y facilita el filtro del flow.

1. Outlook web → **Configuración → Reglas → + Añadir nueva regla**.
2. Condición: **De → `onboarding@resend.dev`** (o tu dominio verificado en Resend si ya lo tienes).
3. Condición adicional: **Asunto contiene → `[Porra26]`**.
4. Acción: **Mover a carpeta → PORRA26** (créala antes).
5. Acción adicional: **Marcar como leído** (opcional).

Con esto los emails caen en `PORRA26` y la bandeja queda limpia, pero el flow los sigue viendo igual (la regla se ejecuta después del trigger).

## 2. Crear el flow

1. Entra en https://make.powerautomate.com.
2. **+ Crear → Flujo automatizado en la nube** (*Automated cloud flow*).
3. Nombre: `PORRA 26 · Cierre apuestas a Teams`.
4. Trigger: **When a new email arrives (V3)** del conector *Outlook 365*. Pulsa **Crear**.

## 3. Configurar el trigger

| Campo | Valor |
|---|---|
| Folder | `PORRA26` si creaste la regla del paso 1, o `Inbox` si prefieres filtrar todo desde aquí. |
| From | `onboarding@resend.dev` (o el remitente que uses si tienes dominio verificado en Resend). |
| Subject Filter | `[Porra26]` — el management command pone exactamente este prefijo. |
| Importance | `Any`. |
| Only with Attachments | **Yes**. |
| Include Attachments | **Yes**. |

> Dejar el filtro de **From** vacío es un error: el flow se dispararía con cualquier email que tenga `[Porra26]` en el asunto y un adjunto.

## 4. Añadir acción para postear en Teams

1. Después del trigger, **+ Nuevo paso → Add an action**.
2. Busca **Microsoft Teams** → **Post message in a chat or channel**.
3. Configuración:

| Campo | Valor |
|---|---|
| Post as | `Flow bot` |
| Post in | `Group chat` |
| Group chat | Selecciona el chat de grupo de la porra. |
| Message | Ver bloque de abajo. |

Mensaje (HTML, pegar tal cual en *Code view*):

```html
<p>📣 <b>Cierre de apuestas</b> · @{replace(triggerOutputs()?['body/Subject'], '[Porra26] ', '')}</p>
<p>Adjunto el PDF con los pronósticos.</p>
<p><i>Generado por la porra desde Railway · @{utcNow()}</i></p>
```

> El asunto que pone Django es del tipo `[Porra26] España vs Argentina · 15/06 18:00`. La expresión `replace(..., '[Porra26] ', '')` retira el prefijo y deja solo `España vs Argentina · 15/06 18:00`. Si más adelante cambias el prefijo en `closing_email.py`, actualiza también este `replace`.

> El conector estándar de Teams **no permite adjuntos directamente en este paso**. Hay dos opciones:
> - **A**: añadir un paso intermedio que sube el PDF a OneDrive personal y luego publica el enlace en Teams. Requiere licencia OneDrive (incluida en M365 Business).
> - **B**: usar la acción **Post adaptive card and wait for a response** que sí permite adjuntar contenido binario inline. Más complejo.

## 5. Opción A — Subir a OneDrive y enlazar (recomendado)

Entre el trigger y la acción de Teams, inserta dos pasos.

### 5.1 Apply to each (sobre attachments)

- **+ Nuevo paso → Add an action → Apply to each**.
- Input: **Attachments** del trigger (selecciónalo desde Contenido dinámico).

### 5.2 Dentro del bucle: Create file en OneDrive

- **Add an action → OneDrive for Business → Create file**.
- Configuración:

| Campo | Valor |
|---|---|
| Folder Path | `/Apps/Porra26/Cierres` (crea la carpeta a mano una vez en OneDrive web). |
| File Name | `@{items('Apply_to_each')?['Name']}` (el nombre original del adjunto, e.g. `cierre-esp-vs-arg-2026-06-15.pdf`). |
| File Content | `@{items('Apply_to_each')?['ContentBytes']}` |

### 5.3 Adapta el mensaje de Teams

Cambia el `Message` a:

```html
<p>📣 <b>Cierre de apuestas</b> · @{replace(triggerOutputs()?['body/Subject'], '[Porra26] ', '')}</p>
<p>📄 <a href="@{body('Create_file')?['webUrl']}">Descargar PDF</a></p>
<p><i>Generado por la porra desde Railway · @{utcNow()}</i></p>
```

Importante: para que el `<a href="…">Descargar PDF</a>` se renderice como enlace en Teams (y no como URL pelada), pega el HTML en la **vista código** del editor de Message — botón `</>` en la esquina inferior derecha del campo. Si lo pegas en la vista rich-text Power Automate escapa los tags.

> La acción **Post message in a chat or channel** debe quedar **fuera** del `Apply to each` para no postear un mensaje por adjunto (el cierre siempre lleva un solo PDF, pero por defensa nos quedamos con un mensaje único).

## 6. Guardar y probar

1. **Guardar** el flow.
2. Forzar un smoke test:
   ```bash
   railway run --service <cron-service> python manage.py send_pending_closures --match-id <id-de-test>
   ```
3. Esperar 1-2 minutos. El flow debería dispararse y publicar el mensaje en Teams con el enlace al PDF en OneDrive.
4. Si no dispara: **Power Automate → Flujos → tu flow → Historial de ejecuciones**. Cada ejecución te dice exactamente dónde falló (con los inputs/outputs de cada paso).

## 7. Diagnóstico de problemas comunes

| Síntoma | Causa probable | Cómo confirmarlo / arreglarlo |
|---|---|---|
| El flow no se dispara. | El email no está cayendo en la carpeta que vigila el trigger, o el filtro `From`/`Subject Filter` no matchea. | Confirma en Outlook que el email llega. Revisa que `Folder` del trigger es donde realmente cae el email. Ojo: si Outlook tiene reglas que lo marquen como leído + lo muevan antes del trigger, depende de la rapidez con que Power Automate sondee la carpeta. |
| El flow se dispara pero falla en "Create file". | `Folder Path` no existe, o la sesión OneDrive caducó. | Abre OneDrive web y comprueba la carpeta. Re-autentica el conector OneDrive en Power Automate. |
| El mensaje se publica pero sin enlace al PDF. | El `Apply to each` no encontró attachments. | Trigger configurado sin `Include Attachments: Yes`. Edita el trigger. |
| Resend marca el envío como `Delivered` pero el flow nunca dispara. | El email cae directamente en *Junk Email* / *Correo no deseado*. | Marca el primer email como "no es correo no deseado" + crea una regla que no lo mueva a junk. |

## 8. Migrar a dominio propio (cuando esté en Resend)

Cuando verifiques un dominio propio en Resend (ver `docs/DEPLOY_RAILWAY.md` §12), actualiza:

1. `DEFAULT_FROM_EMAIL` en Railway pasa a `PORRA 26 <bot@tu-dominio>`.
2. En el trigger del flow, cambia `From` a `bot@tu-dominio`.
3. En la regla de Outlook (paso 1), idem.

## 9. Flow de recordatorios pre-cierre (independiente del flow de cierre)

Aparte del PDF de cierre, hay un **segundo flow** que publica avisos en Teams 2 h y 30 min antes de que se cierren las apuestas, listando a los rezagados (ver `docs/superpowers/specs/2026-06-04-recordatorios-apuestas-design.md`). Es independiente del flow descrito arriba — mismo buzón Outlook destino, mismo chat de Teams, distinto filtro de asunto y sin adjunto.

### 9.1 Disparador externo: cron-job.org

El cron vive fuera de Railway, en [cron-job.org](https://cron-job.org) — mismo servicio que ya usamos para `live_tick` (Fase 9). El job se configura desde el dashboard de cron-job.org y **no vive en el repo**:

| Campo | Valor |
|---|---|
| URL | `https://laporradeljefe.es/competicion/api/teams/recordatorios/disparar/` |
| Método | `POST` |
| Schedule | cada 15 min |
| Header | `Authorization: Bearer <TEAMS_API_TOKEN>` (mismo valor que la env var de Railway). |

Cada disparo hace POST al endpoint y el backend recorre las dos ventanas (T-2h, T-30min) enviando un email por cada partido con rezagados. La respuesta es JSON con el resumen (`{"T_MINUS_2H": {"checked": N, "sent": N, …}, …}`) — los logs del job en cron-job.org guardan el body para auditoría.

**Por qué cron-job.org y no GitHub Actions**: arrancamos esto en `.github/workflows/match-reminders.yml`, pero el cron de GitHub Actions se retrasaba 1–5 h en picos de carga (gaps reales de 67–292 min frente a los 15 min declarados). La ventana T-30M (que solo es 30 min de ancho) se perdía casi siempre. cron-job.org sí cumple la cadencia con precisión de minuto. Migrado el 2026-06-11.

Para disparo manual desde el dashboard de cron-job.org: cualquier job tiene botón **Run now**. Equivalente al `workflow_dispatch` que teníamos antes.

### 9.2 El flow en Power Automate

Solo **dos pasos**, mucho más simple que el de cierre porque el email no lleva adjunto.

1. **Trigger** *When a new email arrives (V3)*:

| Campo | Valor |
|---|---|
| Folder | `PORRA26` (el mismo del flow de cierre). |
| From | `onboarding@resend.dev` (o el dominio verificado si lo tienes). |
| Subject Filter | `[Porra26 RECORDATORIO]` — distinto del prefijo de cierre. |
| Only with Attachments | **No**. |
| Include Attachments | **No**. |

2. **Acción** *Post message in a chat or channel*:

| Campo | Valor |
|---|---|
| Post as | Flow bot |
| Post in | Group chat |
| Group chat | El mismo del flow de cierre. |
| Message (Code view, HTML) | `@{triggerOutputs()?['body/Body']}` |

El email de recordatorio se envía como `multipart/alternative` con HTML estructurado: PA reenvía ese HTML tal cual y Teams lo renderiza.

### 9.3 Prueba manual

Desde local con un partido en ventana T-2h:

```bash
railway run python manage.py send_match_reminders --match-id <id>
```

O forzar el endpoint directo con `curl`:

```bash
curl -fsS -X POST \
  -H "Authorization: Bearer $TEAMS_API_TOKEN" \
  https://laporradeljefe.es/competicion/api/teams/recordatorios/disparar/
```

### 9.4 Verificación

- **cron-job.org → History** del job: el panel muestra cada disparo con código HTTP, latencia y el JSON de respuesta del backend.
- **AuditLog en Django admin**: filas con `action="bets_reminder_sent"` muestran qué se envió, a quién y cuándo.
- **BetsReminderLog**: una fila por `(match, kind)`. Si falta el log de una ventana esperada, no se envió (probablemente porque no había rezagados).

## 10. Cuando lo migremos a un canal de Teams

Si en el futuro queremos publicar en un canal (no en un chat de grupo), los archivos pasan a vivir en SharePoint en vez de OneDrive personal:

1. **Post in** → `Channel` en lugar de `Group chat`.
2. **Create file** → conector **SharePoint** en lugar de **OneDrive**, apuntando a la biblioteca de documentos del equipo.

La estructura del flow es idéntica.

## Equivalencias UI español/inglés

| Inglés | Español |
|---|---|
| When a new email arrives (V3) | Cuando llega un correo nuevo (V3) |
| Subject Filter | Filtro de asunto |
| Include Attachments | Incluir datos adjuntos |
| Apply to each | Aplicar a cada uno |
| Create file | Crear archivo |
| Post message in a chat or channel | Publicar mensaje en un chat o canal |
| Group chat | Chat de grupo |
| Run history | Historial de ejecuciones |
