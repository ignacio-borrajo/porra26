# Avatar de jugador — diseño

**Fecha:** 2026-06-01
**Autor:** Ignacio Borrajo (vía Claude Code)
**Estado:** propuesto, pendiente de aprobación

## 1. Objetivo

Permitir que cada usuario suba una foto de perfil desde `/mi-cuenta/` y que esa foto se utilice en toda la interfaz donde hoy se muestra el avatar (topbar, líder de cada grupo en rankings, gráfico de evolución). Si el usuario no sube foto, se mantiene el fallback actual de iniciales coloreadas por nombre.

El diseño debe funcionar tanto en desarrollo local (SQLite + servidor de Django) como en producción en **PythonAnywhere** sin sorpresas operativas.

## 2. Alcance

Dentro:

- Campo `avatar` en `accounts.User` (Pillow + `ImageField`).
- Upload, reemplazo y borrado desde `/mi-cuenta/`.
- Procesado server-side: recorte cuadrado centrado a 256×256, salida JPEG.
- Partial `templates/partials/_avatar.html` único para pintar avatar (`<img>` o iniciales).
- Uso del partial en:
  - `templates/partials/_topbar.html`
  - `templates/stats/rankings.html` (columna "Líder")
  - `templates/accounts/my_account.html` (preview + edición)
- Avatar al final de cada línea del gráfico de evolución (`/estadisticas/`).
- Configuración `MEDIA_URL` / `MEDIA_ROOT` con instrucciones específicas para PythonAnywhere.
- Tests de procesado, borrado, reemplazo y validación.

Fuera:

- Recorte interactivo en cliente (no se ofrece UI de crop manual).
- Avatares en la pantalla de Jugadores del gestor (cuando se implemente, se usará el mismo partial).
- Almacenamiento externo (S3 u otro). Se queda en disco local porque encaja con PA.

## 3. Decisiones tomadas en brainstorming

| Pregunta | Decisión |
|---|---|
| Procesado de imagen | Redimensionar a 256×256 en upload (un único archivo final) |
| Eliminar avatar | Sí, con checkbox "Quitar foto" |
| Alcance UI | Partial reutilizable + topbar + `/mi-cuenta/` + rankings + chart |
| Gráfico | Avatar al final de cada línea (todas, no solo la mía) |

## 4. Modelo de datos

### 4.1 Campo nuevo en `accounts.User`

```python
def avatar_upload_to(instance, filename):
    ext = Path(filename).suffix.lower() or ".jpg"
    return f"avatars/{instance.id}_{uuid.uuid4().hex[:8]}{ext}"

avatar = models.ImageField(
    upload_to=avatar_upload_to,
    blank=True,
    null=True,
)
```

- El `filename` original se descarta — se usa `id + uuid` corto para evitar colisiones y path traversal.
- `blank=True, null=True` permite usuarios sin foto.

### 4.2 Migración

Una sola migración generada por `makemigrations` (Django autonumera; el nombre quedará `accounts/migrations/000N_user_avatar.py`), con `AddField` nullable. SQLite (dev) acepta `AddField` nullable sin reescribir la tabla; MySQL en PA tampoco tendrá problema.

## 5. Procesado de imagen

Archivo nuevo: `accounts/services/avatar.py`.

```python
def process_avatar(uploaded_file) -> ContentFile:
    """Devuelve un ContentFile JPEG 256×256 listo para guardar."""
    with Image.open(uploaded_file) as img:
        img.verify()                      # valida formato real
    uploaded_file.seek(0)
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)    # corrige orientación
    if img.mode != "RGB":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg
    img = ImageOps.fit(img, (256, 256), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return ContentFile(buf.getvalue(), name="avatar.jpg")
```

Reglas:

- Valida MIME real con Pillow (`Image.open(...).verify()`), no por extensión.
- `exif_transpose` antes del recorte.
- PNG/WebP con transparencia se aplanan sobre blanco.
- Salida siempre JPEG calidad 85 (peso ~20–40 KB).

## 6. Formulario y vista

### 6.1 `ProfileForm`

```python
class Meta:
    fields = ["name", "sede", "puesto", "dept", "avatar"]
    labels = {
        "name": "Nombre",
        "sede": "Sede",
        "puesto": "Puesto",
        "dept": "Departamento",
        "avatar": "Foto de perfil",
    }
    widgets = {
        "name": forms.TextInput(attrs=INPUT_ATTRS),
        "sede": forms.Select(attrs=INPUT_ATTRS),
        "puesto": forms.Select(attrs=INPUT_ATTRS),
        "dept": forms.Select(attrs=INPUT_ATTRS),
        "avatar": forms.FileInput(attrs={
            "class": "avatar-input",
            "accept": "image/jpeg,image/png,image/webp",
        }),
    }

def clean_avatar(self):
    f = self.cleaned_data.get("avatar")
    if f in (None, False) or not hasattr(f, "size"):
        return f
    if f.size > 2 * 1024 * 1024:
        raise ValidationError("La foto no puede pesar más de 2 MB.")
    try:
        return process_avatar(f)
    except (UnidentifiedImageError, OSError):
        raise ValidationError("El archivo no es una imagen válida.")
```

### 6.2 `MyAccountView._post_profile`

- `POST` pasa a aceptar `request.FILES`: `ProfileForm(request.POST, request.FILES, instance=request.user)`.
- **Clear manual** (no usamos `ClearableFileInput` para evitar el markup por defecto de Django): si `request.POST.get("avatar-clear")` está presente y no se ha subido archivo nuevo, se elimina el archivo anterior del disco y se pone `user.avatar = None`. La vista hace este paso después de validar el form.
- Si llega un archivo nuevo y ya había avatar previo, se borra el antiguo (`old_avatar.delete(save=False)`) antes de guardar el nuevo.
- `AuditLog.payload["changed"]` incluye `"avatar"` cuando alta/reemplazo/borrado.

### 6.3 Borrado en cascada

Señal `pre_delete` sobre `User` que llama a `user.avatar.delete(save=False)` para no dejar huérfanos cuando un gestor elimina a un jugador.

## 7. Plantilla `/mi-cuenta/`

El `<form>` de "Datos personales" cambia a `enctype="multipart/form-data"`. Bloque nuevo antes del input de correo:

```html
<div class="avatar-edit">
  <div class="avatar-preview">
    {% include "partials/_avatar.html" with u=user size=96 %}
  </div>
  <div class="avatar-actions">
    <label class="btn btn-ghost" for="id_avatar">Cambiar foto</label>
    {{ profile_form.avatar }}
    {% if user.avatar %}
      <label class="check">
        <input type="checkbox" name="avatar-clear" id="avatar-clear">
        Quitar foto
      </label>
    {% endif %}
    <p class="hint">JPG, PNG o WebP. Máx 2 MB. Se recorta cuadrado.</p>
  </div>
</div>
```

JS inline mínimo (sin librerías) para preview en vivo:

```html
<script>
  const fileInput = document.getElementById("id_avatar");
  const preview = document.querySelector(".avatar-preview img, .avatar-preview span");
  fileInput?.addEventListener("change", () => {
    const f = fileInput.files?.[0];
    if (!f) return;
    const url = URL.createObjectURL(f);
    preview.outerHTML = `<img class="avatar" src="${url}" width="96" height="96"
                              style="width:96px;height:96px;border-radius:50%;object-fit:cover">`;
  });
</script>
```

CSS nuevo (final de `static/css/styles.css`, ver §8.1):

```css
.avatar-edit { display:flex; gap:18px; align-items:center; }
.avatar-input { display:none; }
.hint { font-size:12px; color:var(--text-faint); margin:6px 0 0; }
```

## 8. Partial reutilizable y CSS base de `.avatar`

### 8.1 CSS base (`static/css/styles.css`)

**Importante:** la clase `.avatar` no está estilada actualmente en `static/css/styles.css`; las plantillas la usan pero el aspecto real proviene de estilos inline. En este PR la añadimos como parte fundamental del trabajo, replicando el `<Avatar>` del prototipo (`design-reference/shared.jsx:34-46`).

```css
.avatar {
  border-radius: 50%;          /* el prototipo usa 12px; aquí elegimos círculo para coherencia con foto */
  flex-shrink: 0;
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-weight: 700;
  color: white;
  box-shadow: 0 2px 8px -2px oklch(0 0 0 / 0.4);
}
/* Fallback de iniciales: degradado por id de usuario.
   La hue se inyecta desde la plantilla con --hue (0-359). */
span.avatar {
  background: linear-gradient(
    135deg,
    oklch(0.62 0.19 var(--hue, 250)),
    oklch(0.66 0.20 calc(var(--hue, 250) + 60))
  );
  font-size: calc(var(--avatar-size, 32px) * 0.36);
}
img.avatar { object-fit: cover; }
```

### 8.2 Filtro de plantilla `avatar_hue`

Nuevo filtro en `core/templatetags/avatar_extras.py`:

```python
@register.filter
def avatar_hue(user) -> int:
    """Replica el prototipo: (charCode del último char del id) * 47 % 360."""
    pk_str = str(user.pk) if getattr(user, "pk", None) is not None else "?"
    return (ord(pk_str[-1]) * 47) % 360
```

### 8.3 Partial `templates/partials/_avatar.html`

```django
{% load avatar_extras %}
{% with s=size|default:32 %}
{% if u.avatar %}
  <img class="avatar" src="{{ u.avatar.url }}" alt="{{ u.name }}"
       width="{{ s }}" height="{{ s }}"
       style="width:{{ s }}px;height:{{ s }}px">
{% else %}
  <span class="avatar"
        style="width:{{ s }}px;height:{{ s }}px;--hue:{{ u|avatar_hue }};--avatar-size:{{ s }}px">
    {{ u.initials }}
  </span>
{% endif %}
{% endwith %}
```

Usos:

- `templates/partials/_topbar.html:38` → `{% include "partials/_avatar.html" with u=user size=32 %}`.
- `templates/stats/rankings.html:30` → ídem, pero requiere que la vista pase un dict de usuarios indexado por id (ver §9).

## 9. Rankings de grupo (`group_standings`)

`GroupRow` añade `top_user_id: int | None`.

`RankingsView` precarga los usuarios líderes en bloque:

```python
top_ids = [r.top_user_id for r in rows if r.top_user_id]
top_users = User.objects.in_bulk(top_ids)  # {id: User}
```

Y la plantilla resuelve `{% include "partials/_avatar.html" with u=top_users|get_item:r.top_user_id size=28 %}` (filtro `get_item` simple en `core/templatetags/dict_extras.py` si no existe ya).

## 10. Gráfico de evolución

### 10.1 Datos

`ChartDataView` añade al JSON un mapa `players`:

```json
{
  "history": { "12": [...], ... },
  "me": 12,
  "players": {
    "12": {"name": "Ana López", "initials": "AL", "hue": 145, "avatar_url": "/media/avatars/12_abcd.jpg"},
    "13": {"name": "Marc Oller", "initials": "MO", "hue": 277, "avatar_url": null}
  }
}
```

`hue` se calcula con la misma fórmula del prototipo (último char del id × 47 mod 360) para que el chart y los `<span class="avatar">` server-rendered usen el mismo color.

Se calcula con un único `User.objects.in_bulk(history.keys(), field_name="id")`.

### 10.2 Renderizado

`static/js/rank-chart.js` añade, al final de cada línea, un grupo `<g>` posicionado en `(xScale(xMax), yScale(últimoPunto.pts))`:

- Si `avatar_url` → `<image href width=24 height=24 x=-12 y=-12 clip-path="circle(12px at 12px 12px)">`.
- Si no → `<circle r=12 fill="oklch(0.64 0.19 ${hue})">` + `<text>` con iniciales centrado.

El `hue` viene precalculado en el JSON (§10.1) — el cliente no recalcula nada y se garantiza coherencia con los `<span class="avatar">` server-rendered.

El avatar "mío" lleva además `stroke="var(--accent)" stroke-width="2"` para mantener el énfasis actual de la línea.

## 11. Configuración y despliegue

### 11.1 `porra26/settings/base.py`

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

### 11.2 `porra26/urls.py` (servir media solo en dev)

```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### 11.3 `.gitignore`

```
media/
```

### 11.4 `requirements.txt`

```
Pillow>=10.0
```

(Pillow viene pre-instalado en PA; añadirlo a `requirements.txt` solo afecta a entornos limpios.)

### 11.5 Despliegue en PythonAnywhere

Nuevo apartado en `docs/DEPLOY.md`:

1. `pip install -r requirements.txt` en la consola de PA.
2. Tab *Web* → *Static files* añadir las dos entradas:
   - `/static/` → `/home/<usuario>/apuestas-interna/staticfiles/`
   - `/media/` → `/home/<usuario>/apuestas-interna/media/`
3. `python manage.py collectstatic --noinput`.
4. `mkdir -p /home/<usuario>/apuestas-interna/media/avatars` (la primera subida lo crearía igualmente, pero lo dejamos explícito).
5. Reload de la web app.

## 12. Tests

Nuevos archivos:

- `accounts/tests/test_avatar_service.py`
  - `test_process_avatar_resizes_to_256` — entrada 1000×500 → salida 256×256.
  - `test_process_avatar_flattens_transparency` — PNG con alfa → JPEG sin alfa.
  - `test_process_avatar_applies_exif_orientation` — imagen rotada por EXIF → píxel de referencia donde toca.
  - `test_process_avatar_rejects_non_image` — bytes basura → `UnidentifiedImageError`.

- `accounts/tests/test_avatar_upload.py`
  - `test_my_account_post_uploads_avatar` — POST con archivo → `user.avatar` no vacío y el archivo final es JPEG 256×256.
  - `test_my_account_post_oversize_rejected` — 3 MB → form inválido, sin cambios en DB.
  - `test_my_account_post_invalid_type_rejected` — `.txt` renombrado → rechazado.
  - `test_my_account_post_replacement_deletes_old_file`.
  - `test_my_account_post_clear_removes_file`.
  - `test_my_account_renders_img_when_avatar_set` — `<img class="avatar"` presente.
  - `test_my_account_renders_initials_fallback_when_no_avatar` — `<span class="avatar"` presente.
  - `test_audit_log_includes_avatar_change`.

Modificados:

- `accounts/tests/test_my_account.py` — los tests que hacen POST profile deben incluir `enctype` multipart (Django test client lo hace automáticamente cuando hay `files=`).
- `stats/tests/` — `chart_data` JSON ahora incluye `players`; `group_standings` ahora expone `top_user_id`.

Fixture global para no escribir a disco real:

```python
# conftest.py
@pytest.fixture(autouse=True)
def media_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
```

## 13. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Imagen maliciosa (zip-bomb, polyglot) | `Image.verify()` + `ImageOps.fit` re-decodifica; salida siempre JPEG re-encoded. |
| Archivos huérfanos al borrar usuario | Señal `pre_delete` que llama a `avatar.delete(save=False)`. |
| Disco lleno en PA free tier (512 MB) | Cada avatar ~30 KB; para 100 usuarios ≈ 3 MB. Despreciable. |
| MEDIA no mapeado en PA → 404 en producción | Documentado en §11.5; check explícito en `docs/PLAN.md`. |
| Cache de avatar antiguo tras reemplazo | El nombre incluye UUID, así que la URL cambia → no hay colisión de cache. |

## 14. Memoria a actualizar

Añadir entrada de proyecto: "El avatar es parte del perfil del usuario; el partial `partials/_avatar.html` es la única forma de pintarlo en cualquier vista. Para usar el avatar de otro usuario en una plantilla, pásalo por contexto (ej. `top_users[r.top_user_id]`)."
