# PORRA 26 — Porra interna del Mundial 2026

Paquete de arranque (*handoff*) para implementar la aplicación real con **Claude Code**, partiendo del prototipo estético ya validado.

---

## 1. Qué es esto

**PORRA 26** es una aplicación web interna de empresa para jugar una porra (quiniela) del **Mundial de fútbol FIFA 2026**. Los empleados pronostican los resultados de los partidos, suman puntos según sus aciertos y compiten por un bote común. Hay dos roles: **jugador** (pronostica y consulta su rendimiento) y **gestor** (administra jugadores, pagos e introduce los resultados oficiales).

Este repositorio contiene:

- **Un plan de implementación completo** (`docs/`) — qué construir, en qué orden, con qué reglas de negocio.
- **El prototipo estético de referencia** (`design-reference/`) — un prototipo en HTML/React que define con exactitud el aspecto y comportamiento que debe tener la aplicación final.
- **Instrucciones persistentes para Claude Code** (`CLAUDE.md`) — para que mantenga el contexto y la fidelidad al diseño en cada sesión.

> ⚠️ **Importante:** los archivos de `design-reference/` son **una referencia de diseño**, no el código de producción. Son un prototipo (React vía Babel en el navegador, datos *mock* en memoria) que muestra el aspecto y las interacciones deseadas. La tarea de Claude Code es **recrear ese diseño con fidelidad de píxel** dentro de un stack de producción real (ver más abajo), no copiar el prototipo tal cual.

---

## 2. Fidelidad del prototipo

El prototipo es **alta fidelidad (hi-fi)**: colores, tipografías, espaciados, radios, sombras, animaciones e interacciones son los definitivos. Claude Code debe reproducirlos exactamente. Todos los valores exactos están documentados en [`docs/DESIGN_SPEC.md`](docs/DESIGN_SPEC.md) y, como fuente última de verdad, en `design-reference/styles.css`.

---

## 3. Stack recomendado

El prototipo usa React. Para producción se recomienda un stack moderno, tipado y con backend incluido, fácil de desplegar para una herramienta interna:

| Capa | Recomendación | Por qué |
|------|---------------|---------|
| Framework | **Next.js (App Router) + TypeScript** | SSR/rutas, API integrada, fácil despliegue |
| Estilos | **CSS variables + CSS Modules** (o Tailwind con los tokens mapeados) | El prototipo ya está construido sobre *custom properties*; se trasladan casi 1:1 |
| Base de datos | **PostgreSQL** (vía Prisma) | Relacional encaja con jugadores/partidos/pronósticos |
| Auth | **Auth.js / NextAuth** con credenciales (correo de empresa) | Requisito: login con correo corporativo, sin auto-recuperación |
| Hosting | **Vercel** + Postgres gestionado (Neon/Supabase) | Despliegue interno rápido |

> Si el equipo prefiere otro stack (Vite + React SPA + API aparte, Remix, etc.), es válido: lo esencial es respetar el **diseño** y el **modelo de datos / reglas de negocio**. Claude Code debe confirmar el stack contigo antes de empezar a generar código.

---

## 4. Cómo arrancar con Claude Code

1. Coloca esta carpeta como raíz de tu repositorio local (ya está pensada para vivir en `~/Documents/GitHub/apuestas-interna`).
2. Abre la carpeta con Claude Code.
3. Claude Code leerá automáticamente `CLAUDE.md` (contexto del proyecto y reglas de fidelidad al diseño).
4. Primer mensaje sugerido:

   > « Lee `README.md`, `CLAUDE.md` y todo `docs/`. Abre el prototipo `design-reference/PORRA 26.html` para entender el aspecto objetivo. Confirma el stack conmigo y luego empieza por la **Fase 0** del plan (`docs/PLAN.md`). »

5. Ve avanzando fase por fase. No dejes que genere todo de golpe: revisa cada fase contra el prototipo.

---

## 5. Ver el prototipo

Abre `design-reference/PORRA 26.html` en un navegador (doble clic, o con un servidor estático). Necesita conexión a internet (carga React, Babel y las fuentes desde CDN). Credenciales de demo precargadas; pulsa **Entrar** eligiendo rol **Jugador** o **Gestor** para ver ambas vistas. El botón flotante de *Tweaks* (si está disponible) permite cambiar tema, color de acento y variantes.

---

## 6. Estructura de este paquete

```
apuestas-interna/
├── README.md            ← este archivo
├── CLAUDE.md            ← contexto persistente para Claude Code (lo lee solo)
├── docs/
│   ├── PLAN.md          ← plan de implementación por fases
│   ├── DESIGN_SPEC.md   ← tokens de diseño, pantallas y componentes (valores exactos)
│   ├── DATA_MODEL.md    ← entidades, relaciones y reglas de negocio
│   └── WORKFLOW.md      ← cómo seguir iterando el diseño aquí y aplicarlo en código
└── design-reference/    ← PROTOTIPO de referencia (no es código de producción)
    ├── PORRA 26.html
    ├── styles.css        ← fuente de verdad de los tokens visuales
    ├── *.jsx             ← pantallas y componentes del prototipo
```

---

## 7. Mantener diseño y código sincronizados

Seguirás iterando el **aspecto** en la herramienta de diseño (este prototipo). Cuando lo hagas, vuelca los archivos actualizados en `design-reference/` y pídele a Claude Code que aplique los cambios al código de producción. El procedimiento detallado está en [`docs/WORKFLOW.md`](docs/WORKFLOW.md).
