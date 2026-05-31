# Sincronizar nuevas iteraciones del prototipo

Cuando se actualice el prototipo de diseño (carpeta `design-reference/`), aplica los cambios al código de producción con este procedimiento:

## 1. Recibe la nueva versión del prototipo

El responsable de diseño exportará los archivos del prototipo y los volcará en `design-reference/`. **No lo edites a mano** — la siguiente iteración lo sobreescribirá.

## 2. Detecta los cambios

```bash
git diff HEAD~1 -- design-reference/styles.css
git diff HEAD~1 -- 'design-reference/*.jsx'
```

## 3. Aplica los cambios

- **Si cambia `styles.css`:** copia los tokens nuevos/modificados a `static/css/styles.css`. Mantén los nombres de variables (`--c-pink`, `--accent`, etc.).
- **Si cambia un componente JSX:** identifica el partial Django equivalente (p. ej. `match.jsx` → `templates/competition/_match_card.html`) y refleja los cambios estructurales (clases, estilos en línea, jerarquía DOM).
- **Si hay un componente nuevo:** decide si entra en producción o queda como referencia futura. Discútelo con el responsable.

## 4. Valida visualmente

- Arranca dev: `python manage.py runserver --settings=porra26.settings.dev`.
- Abre `http://localhost:8000` y `design-reference/PORRA 26.html` lado a lado.
- Tema oscuro y claro.

## 5. Commitea

```bash
git add design-reference/ static/css/ templates/
git commit -m "design: sincronizar iteración <fecha>"
```
