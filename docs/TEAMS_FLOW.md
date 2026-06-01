# Flujo de Power Automate — Cierre de apuestas a Teams

Esta guía describe cómo configurar el *Scheduled cloud flow* que sondea PORRA 26 cada 10 minutos, descarga el PDF de cada cierre pendiente y lo publica en el canal interno de Teams.

## Prerrequisitos

- Cuenta de Microsoft 365 con licencia Power Automate Standard (incluida en la mayoría de planes Business).
- Permiso de escritura en el canal de Teams de destino.
- Token de la API expuesto por la aplicación: variable `TEAMS_API_TOKEN` en el `.env` de PythonAnywhere (ver `docs/DEPLOY.md`).
- URL pública de la aplicación: `https://porra26.pythonanywhere.com`.

## 1. Crear el flow

1. Entra en https://make.powerautomate.com.
2. **Crear → Flujo de nube programado**. Nombre sugerido: `PORRA 26 · Cierre apuestas a Teams`.
3. Recurrencia: **cada 10 minutos**.

## 2. Acción 1 — Obtener pendientes

Añade acción **HTTP**:

- Method: `GET`
- URI: `https://porra26.pythonanywhere.com/competicion/api/teams/cierres-pendientes/`
- Headers:
  - `Authorization`: `Bearer <pegar TEAMS_API_TOKEN>`
- En `...` (opciones) marca el campo **Authorization** como *Secure input*.

## 3. Parsear la respuesta

Añade **Parse JSON**:

- Content: `body('HTTP')` (salida de la acción anterior).
- Schema (pegar literal):

```json
{
  "type": "object",
  "properties": {
    "matches": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"},
          "slug": {"type": "string"},
          "round": {"type": "string"},
          "group": {"type": "string"},
          "home": {"type": "object", "properties": {"code": {"type": "string"}, "name": {"type": "string"}}},
          "away": {"type": "object", "properties": {"code": {"type": "string"}, "name": {"type": "string"}}},
          "kickoff": {"type": "string"},
          "closed_at": {"type": "string"}
        }
      }
    }
  }
}
```

## 4. Bucle sobre cada partido

Añade **Apply to each** sobre `body('Parse_JSON')?['matches']`. Dentro:

### 4.1 Descargar PDF

Acción **HTTP**:

- Method: `GET`
- URI: `https://porra26.pythonanywhere.com/competicion/api/teams/cierres/@{items('Apply_to_each')?['id']}/pdf/`
- Headers:
  - `Authorization`: `Bearer <TEAMS_API_TOKEN>` (también *Secure input*).

### 4.2 Publicar en Teams

Acción del conector Teams: **Post message in a chat or channel**.

- **Post as:** Flow bot.
- **Post in:** Channel.
- **Team / Channel:** selecciona el canal interno (p. ej. `Porra 26 / Cierres`).
- **Message:**

  ```
  📣 Cierre de apuestas — @{items('Apply_to_each')?['home']?['name']} vs @{items('Apply_to_each')?['away']?['name']}
  @{items('Apply_to_each')?['round']} · Grupo @{items('Apply_to_each')?['group']} · Saque @{formatDateTime(items('Apply_to_each')?['kickoff'], 'dd/MM/yyyy HH:mm')}
  ```

- **Attachments:** modo *Advanced*. Pega:

  ```json
  [
    {
      "name": "cierre-@{items('Apply_to_each')?['slug']}.pdf",
      "contentBytes": "@{body('HTTP_descargar_PDF')}",
      "contentType": "application/pdf"
    }
  ]
  ```

> El nombre exacto de la acción HTTP (`HTTP_descargar_PDF`) depende de cómo la hayas renombrado. Si no la renombraste, será `HTTP_2`.

### 4.3 Marcar como enviado

Acción **HTTP**:

- Method: `POST`
- URI: `https://porra26.pythonanywhere.com/competicion/api/teams/cierres/@{items('Apply_to_each')?['id']}/marcar-enviado/`
- Headers:
  - `Authorization`: `Bearer <TEAMS_API_TOKEN>` (*Secure input*)
  - `Content-Type`: `application/json`
- Body:

  ```json
  {"teams_message_id": "@{outputs('Post_message_in_a_chat_or_channel')?['body']?['id']}"}
  ```

- En **Configure run after** (menú `...` de la acción), márcala para que se ejecute **solo si "Post message" terminó como `is successful`**. Si Teams falla, no marcamos enviado → el partido reaparece en el próximo ciclo.

## 5. Probar el flow

1. Pulsa **Save**.
2. Pulsa **Test → Manually**.
3. Comprueba en el canal de Teams que llega el mensaje con el PDF adjunto.
4. En la app, entra como gestor a `/competicion/resultados/` y verifica que el partido aparece en la sección "Estado de envíos a Teams" con ✓ en Enviado.

## 6. Rotar el token

Si se sospecha que `TEAMS_API_TOKEN` se ha filtrado:

1. Genera un nuevo token con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Actualiza `TEAMS_API_TOKEN` en `.env` de PythonAnywhere y recarga la web app.
3. Actualiza el token en las **tres** acciones HTTP del flow.
4. Guarda y prueba.
