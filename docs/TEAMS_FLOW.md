# Flujo de Power Automate — Cierre de apuestas a Teams (email-driven)

Esta guía describe cómo configurar el *flow* que recibe los emails de cierre que envía PORRA 26 y los publica en el chat de grupo de Teams. Usa **solo conectores estándar** (Outlook + Teams) — sin licencia Power Automate Premium.

> **Cambio respecto a versiones anteriores:** la primera versión de esta guía usaba acciones HTTP para sondear directamente la API de PORRA 26 desde Power Automate. Esas acciones son premium (≈ €12/usuario/mes) y la organización no lo paga. La versión actual delega el sondeo a un Cron Service de Railway (`*/10 min`) que envía un email con el PDF adjunto al buzón corporativo del autor del flow, y este flow solo escucha esa bandeja.

## Arquitectura del flujo end-to-end

```
Railway (Cron */10 min)
   └─ python manage.py send_pending_closures
       └─ send_closure_email(match)
           └─ EmailMessage con PDF adjunto
               ↓ SMTP por puerto 2587
           Resend (smtp.resend.com:2587, onboarding@resend.dev)
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
- Railway con el Cron Service de `send_pending_closures` configurado y enviando emails al buzón corporativo (ver `docs/DEPLOY_RAILWAY.md` §14).
- Resend configurado en Railway con `EMAIL_HOST=smtp.resend.com`, `EMAIL_PORT=2587`, etc. (ver `docs/DEPLOY_RAILWAY.md` §3.4).
- Recibir el email de smoke test en el buzón corporativo: confirma que `[Porra26][TEST]` llega y no se queda en spam.

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
<p>🔒 <b>Cierre de apuestas</b></p>
<p>Adjunto el PDF con los pronósticos de @{triggerOutputs()?['body/Subject']}.</p>
<p><i>Generado por la porra desde Railway · @{utcNow()}</i></p>
```

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
<p>🔒 <b>Cierre de apuestas</b> · @{triggerOutputs()?['body/Subject']}</p>
<p>📄 <a href="@{body('Create_file')?['webUrl']}">Descargar PDF</a></p>
<p><i>Generado por la porra desde Railway · @{utcNow()}</i></p>
```

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

## 9. Cuando lo migremos a un canal de Teams

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
