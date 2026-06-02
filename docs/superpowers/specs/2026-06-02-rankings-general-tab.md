# Spec — Pestaña "General" en Rankings

## Problema
La página `/stats/rankings/` permite comparar grupos (sede, puesto, departamento), pero la **clasificación general por jugador** solo está visible en la barra lateral de `/competicion/`. Esa barra lateral en pantallas estrechas se apila debajo del listado de partidos y no es un destino fácil de recordar para "ver el ranking general".

## Objetivo
Añadir una cuarta pestaña en `/stats/rankings/` llamada **General** que reproduzca *exactamente* la clasificación general que se muestra en el sidebar de `/competicion/` (podio top-3 + filas 4+), **con los mismos datos y el mismo estilo visual**.

## Alcance
- Pestaña nueva con `key="general"`, etiqueta `"General"`, posicionada primera (es la vista que más gente buscará).
- Sigue siendo accesible solo para usuarios autenticados (`LoginRequiredMixin`, igual que el resto).
- Datos: el mismo `competition.services.standings.standings()` que alimenta el sidebar de `/competicion/`.
- Estilo: reutiliza `templates/partials/_leaderboard.html` y `_podium_step.html` sin duplicarlos.
- Comportamiento de URL: `?tab=general` la activa; sin parámetro `?tab` la pestaña por defecto pasa a ser `general` (la más importante).

## Fuera de alcance
- Cambios en el cálculo de `standings()`.
- Cambios visuales en los tabs `sede`/`puesto`/`dept`.
- Filtros, paginación o exportación de la clasificación general (ya hay limit 50 implícito en /competicion/; aquí mostraremos también top 50).

## Diseño
La página `rankings.html` hoy renderiza siempre la misma tabla por grupos. Cambio:

1. En `RankingsView`:
   - Añadir `"general"` al inicio de `VALID_TABS` y como tab por defecto.
   - Si `tab == "general"`: cargar `standings()[:50]`, `users` por bulk, `my_rank` y `max_pts` (mismas variables que `CompetitionView`). No cargar `rows`/`top_users`/`my_group` de grupos.
   - Si `tab in (sede|puesto|dept)`: comportamiento actual sin cambios.

2. En `rankings.html`:
   - El header (`<h1>Rankings`) se mantiene, pero el subtítulo cambia según pestaña activa:
     - General → "Clasificación general · top 50 jugadores"
     - Resto → texto actual ("Compara qué sede, puesto o departamento…")
   - La fila de pestañas pasa a tener 4 elementos (`General · Sede · Puesto · Departamento`).
   - Bloque condicional:
     - `{% if tab == "general" %}` → wrapper con `max-width:440px;margin:0 auto` que incluye `partials/_leaderboard.html` con los mismos parámetros que en el dashboard. Así el podio + filas quedan visualmente idénticos.
     - `{% else %}` → tabla de grupos actual sin cambios.

3. CSS:
   - **Ninguna regla nueva**. `_leaderboard.html` ya trae `class="glass leaderboard-aside leaderboard"`. La clase `leaderboard-aside` aplica `position:sticky; top:88px; max-height:calc(100vh - 110px)`. En la página de rankings (sin grid de dashboard) esto no rompe nada: `sticky` se degrada a `static` cuando no hay un ancestro con scroll diferenciado, y el `max-height` solo limita el scroll interno (igual que en /competicion/). El `max-width:440px` envolvente garantiza que el podio no se vea desproporcionado.

## Decisiones tomadas
- **Tab por defecto = general** (no `sede`): es la información que más se consulta y queremos minimizar clicks.
- **Reutilizar el partial existente** en lugar de duplicar: cualquier cambio futuro del podio (por ejemplo, nuevas tendencias) se refleja automáticamente en ambos sitios. Coste: aceptar la clase `leaderboard-aside` y su `position:sticky` inocuo.
- **No tocar `_leaderboard.html` ni su CSS**: evita regresiones en /competicion/ y reduce el blast radius.
- **No mover lógica a un mixin/servicio**: la duplicación entre `CompetitionView` y `RankingsView` es de 4 líneas (`standings`, `users_by_id`, `my_rank`, `max_pts`). Crear una abstracción ahora es YAGNI.
- **Ancho 440px** para imitar el sidebar de 380px + un poco más de aire (la página de rankings no tiene el `<aside>` con padding lateral del grid).

## Riesgos
- `position:sticky` heredado podría comportarse raro en un viewport con scroll alto. Mitigación: validar manualmente en navegador (golden path + scroll largo) durante la verificación.
- Los tests existentes asumen `tab=sede` como default. Hay que actualizarlos (es comportamiento esperado, no regresión).

## Verificación
- **Tests**:
  1. `?tab=general` (o sin parámetro) devuelve 200 y contiene el HTML del podio (`podium-slot--1`).
  2. `?tab=general` pasa al template `rows` con StandingRow (no GroupRow).
  3. `?tab=sede` sigue funcionando (regresión).
  4. Tab inválido cae a `general`.
- **Manual** (con `python manage.py runserver` y datos de prueba): visitar `/stats/rankings/`, comprobar que el podio coincide con el de `/competicion/` y que los enlaces de pestañas alternan correctamente.
