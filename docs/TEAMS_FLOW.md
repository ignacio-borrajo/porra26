# Flujo de Power Automate — Cierre de apuestas a Teams

Esta guía describe cómo configurar el *Scheduled cloud flow* que sondea PORRA 26 cada 10 minutos, descarga el PDF de cada cierre pendiente y lo publica en el **chat de grupo** de Teams junto con un enlace al fichero subido a OneDrive.

> **Nota sobre UI en español**: Power Automate está disponible en español. Esta guía usa los nombres en inglés porque la documentación oficial de Microsoft también, pero al final del documento hay una tabla de equivalencias.
>
> **Nota sobre el destino**: esta versión publica en un **chat de grupo**, así que los PDFs se almacenan en el OneDrive personal del autor del flow. Si en el futuro queréis migrar a un canal de Teams, los archivos pasan a vivir en SharePoint y son más persistentes — la estructura del flow es la misma cambiando OneDrive por SharePoint.

## Prerrequisitos

- Cuenta de Microsoft 365 con licencia Power Automate Standard (incluida en la mayoría de planes Business).
- Pertenencia al chat de grupo de Teams de destino.
- Carpeta `/Apps/Porra26/Cierres` creada en tu OneDrive (créala una vez a mano desde OneDrive web).
- Token de la API expuesto por la aplicación: variable `TEAMS_API_TOKEN` en el `.env` de PythonAnywhere (ver `docs/DEPLOY.md`).
- URL pública de la aplicación: `https://porra26.pythonanywhere.com`.

## 1. Crear el flow

1. Entra en https://make.powerautomate.com.
2. **Crear → Flujo de nube programado** (*Scheduled cloud flow*). Nombre sugerido: `PORRA 26 · Cierre apuestas a Teams`.
3. Recurrencia (*Recurrence*): **cada 10 minutos**.

## 2. Acción 1 — Obtener pendientes

Añade acción **HTTP**:

- Method: `GET`
- URI: `https://porra26.pythonanywhere.com/competicion/api/teams/cierres-pendientes/`
- Headers:
  - `Authorization`: `Bearer <pegar TEAMS_API_TOKEN>`
- En `...` (opciones) marca el campo **Authorization** como *Secure input* (en español: **Entrada segura**).

## 3. Parsear la respuesta

Añade **Parse JSON** (*Analizar JSON*):

- Content: el **Body** de la acción HTTP anterior (selecciónalo desde Contenido dinámico).
- Schema: pulsa **"Generate from sample"** (*Generar a partir de una muestra*) y pega una respuesta real del endpoint; o copia literal este esquema:

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

Añade la acción **Apply to each** (en español: **Aplicar a cada uno**) del conector **Control**.

> ¿No la encuentras buscando? En el diseñador nuevo está en la pestaña **Built-in** → conector **Control**. Alternativa más fácil: **no la añadas manualmente**. Crea directamente la acción 4.1 fuera del bucle; cuando referencies un campo dentro de `matches` (que es un array), Power Automate envuelve automáticamente esa acción en un Apply to each.

En el campo "Select an output from previous steps" (*Seleccionar una salida de los pasos anteriores*) selecciona, desde el panel **Contenido dinámico**, el ítem **`matches`** del bloque Parse JSON.

Las tres acciones que siguen van **dentro** del Apply to each, en este orden:

### 4.1 Descargar el PDF

Acción **HTTP**:

- Method: `GET`
- URI: `https://porra26.pythonanywhere.com/competicion/api/teams/cierres/@{items('Apply_to_each')?['id']}/pdf/`
  > Para construir esa URI sin teclear la expresión: escribe la parte fija, abre Contenido dinámico cuando llegues al `@{…}` y elige **`id`** (aparece bajo "Apply to each").
- Headers:
  - `Authorization`: `Bearer <TEAMS_API_TOKEN>` (también *Secure input*).

Renombra esta acción a algo legible como **"HTTP descargar PDF"** (`...` → *Rename*), así las referencias posteriores serán más claras.

### 4.2 Subir el PDF a OneDrive

Acción **OneDrive para la Empresa → Crear archivo** (*Create file*).

| Campo | Valor |
|-------|-------|
| Ruta de carpeta (*Folder Path*) | `/Apps/Porra26/Cierres` |
| Nombre de archivo (*File Name*) | `cierre-@{items('Apply_to_each')?['slug']}.pdf` |
| Contenido del archivo (*File Content*) | El **Body** del HTTP del paso 4.1 (selecciona desde Contenido dinámico → *Body* de "HTTP descargar PDF"). |

### 4.3 Crear vínculo para compartir

Acción **OneDrive para la Empresa → Crear vínculo para compartir** (*Create share link*).

| Campo | Valor |
|-------|-------|
| Archivo (*File*) | El **Id** del archivo del paso 4.2 (Contenido dinámico → "Crear archivo" → *Id*). |
| Tipo de vínculo (*Link Type*) | **Ver** (*View*). |
| Ámbito del vínculo (*Link Scope*) | **Organización** (*Organization*) — solo gente de la empresa puede abrirlo. |

Esta acción devuelve un campo **WebUrl** (o "Vínculo web") que se usa en el paso siguiente.

### 4.4 Publicar mensaje en el chat de grupo

Acción **Microsoft Teams → Publicar mensaje en un chat o canal** (*Post message in a chat or channel*).

- **Publicar como** (*Post as*): **Flow bot**.
- **Publicar en** (*Post in*): **Chat de grupo** (*Group chat*).
- **Chat de grupo** (*Group chat*): selecciona del desplegable el chat de Porra 26. Si no aparece, comprueba que tu cuenta está en ese chat.
- **Mensaje** (*Message*) — acepta HTML básico:

  ```html
  📣 <b>Cierre de apuestas</b> — @{items('Apply_to_each')?['home']?['name']} vs @{items('Apply_to_each')?['away']?['name']}<br>
  @{items('Apply_to_each')?['round']} · Grupo @{items('Apply_to_each')?['group']} · Saque @{formatDateTime(items('Apply_to_each')?['kickoff'], 'dd/MM/yyyy HH:mm')}<br><br>
  📄 <a href="@{outputs('Crear_vínculo_para_compartir')?['body/link/webUrl']}">Descargar PDF de cierre</a>
  ```

  > El nombre exacto del campo de salida es `link/webUrl`; en Contenido dinámico aparece como **"Vínculo web"** del paso "Crear vínculo para compartir". Si renombraste esa acción, ajusta el `'Crear_vínculo_para_compartir'` al nombre que le pusiste (los espacios se sustituyen por `_`).

### 4.5 Marcar como enviado

Acción **HTTP**:

- Method: `POST`
- URI: `https://porra26.pythonanywhere.com/competicion/api/teams/cierres/@{items('Apply_to_each')?['id']}/marcar-enviado/`
- Headers:
  - `Authorization`: `Bearer <TEAMS_API_TOKEN>` (*Secure input*)
  - `Content-Type`: `application/json`
- Body:

  ```json
  {"teams_message_id": "@{outputs('Publicar_mensaje_en_un_chat_o_canal')?['body/messageId']}"}
  ```

- En **Configure run after** (menú `...` de la acción → en español **Configurar ejecutar después**), márcala para que se ejecute **solo si "Publicar mensaje" terminó como `is successful`** (*correcto*). Si Teams falla, no marcamos enviado → el partido reaparece en el próximo ciclo.

  > Idealmente, configura *Configurar ejecutar después* en CADA paso desde 4.2 en adelante para que solo se ejecute si el anterior fue *correcto*. Así, si OneDrive falla en 4.2, no se intenta el mensaje y el partido reaparece para reintentarse en el siguiente ciclo.

## 5. Probar el flow

1. Pulsa **Save** (*Guardar*).
2. Pulsa **Test → Manually** (*Probar → Manualmente*).
3. Comprueba:
   - En tu OneDrive, dentro de `/Apps/Porra26/Cierres`, aparece el fichero `cierre-<slug>.pdf`.
   - En el chat de grupo de Teams llega el mensaje con el enlace clicable, y al pulsarlo se abre el PDF.
   - En la app, entra como gestor a `/competicion/resultados/` y verifica que el partido aparece en la sección "Estado de envíos a Teams" con ✓ en Enviado.

## 6. Rotar el token

Si se sospecha que `TEAMS_API_TOKEN` se ha filtrado:

1. Genera un nuevo token con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Actualiza `TEAMS_API_TOKEN` en `.env` de PythonAnywhere y recarga la web app.
3. Actualiza el token en las **tres** acciones HTTP del flow (pasos 2, 4.1 y 4.5).
4. Guarda y prueba.

## 7. Consideraciones de almacenamiento

- Los PDFs viven en el OneDrive de la cuenta que creó el flow. Si esa cuenta se desactiva o cambia de propietario, los enlaces dejan de funcionar y el histórico se pierde.
- Para retención a largo plazo de los cierres (todo el campeonato), considera migrar a un **canal de Teams**: los ficheros pasan a vivir en la biblioteca SharePoint del equipo, son persistentes y accesibles por todo el equipo aunque cambie quién mantiene el flow. La adaptación es sustituir los pasos 4.2 y 4.3 por **SharePoint → Crear archivo** apuntando a `/Shared Documents/General/...` del sitio del equipo, y el paso 4.4 cambia "Chat de grupo" por "Canal".

## 8. Equivalencias UI inglés ⇄ español

| Inglés | Español |
|--------|---------|
| Scheduled cloud flow | Flujo de nube programado |
| Recurrence | Periodicidad |
| Apply to each / For each | Aplicar a cada uno |
| Parse JSON | Analizar JSON |
| Built-in | Integrado / Incorporado |
| Dynamic content | Contenido dinámico |
| Expression | Expresión |
| Secure input | Entrada segura |
| Configure run after | Configurar ejecutar después |
| Post message in a chat or channel | Publicar mensaje en un chat o canal |
| Group chat | Chat de grupo |
| Channel | Canal |
| Create file | Crear archivo |
| Create share link | Crear vínculo para compartir |
| WebUrl / Link to item | Vínculo web / Vínculo al elemento |
| Run after: is successful | Ejecutar después: correcto |
| Save / Test | Guardar / Probar |
