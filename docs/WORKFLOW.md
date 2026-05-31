# Flujo de trabajo — iterar el diseño y aplicarlo en código

Esta guía explica cómo seguir mejorando el **aspecto** de PORRA 26 en la herramienta de diseño (el prototipo) y aplicar esos cambios al código de producción con Claude Code, de forma cómoda y sin sorpresas.

---

## La idea: el prototipo es la fuente de verdad estética

- **El prototipo (`design-reference/`) manda en lo visual.** Es donde decides colores, tipografías, espaciados, animaciones y micro-interacciones.
- **El código de producción manda en lo funcional.** Backend, base de datos, autenticación, lógica real.
- La carpeta `design-reference/` vive **dentro del propio repositorio**. Así Claude Code siempre tiene el objetivo visual delante y puede comparar su resultado con él.

```
apuestas-interna/
├── design-reference/   ← lo actualizas tú desde la herramienta de diseño
├── src/ (o app/)       ← lo construye y mantiene Claude Code
└── docs/               ← plan y especificación
```

---

## Ciclo de iteración estética

Cuando quieras cambiar algo del aspecto (por ejemplo, un nuevo color de acento, otro estilo de tarjeta, una animación distinta):

1. **Itera aquí, en la herramienta de diseño.** Pide los cambios sobre el prototipo y revísalos en vivo.
2. **Exporta los archivos actualizados** del prototipo (HTML/CSS/JSX). Es el mismo conjunto de archivos que ya está en `design-reference/`.
3. **Sustituye el contenido de `design-reference/`** en tu repositorio local por los archivos exportados (sobrescribe).
4. **Pídeselo a Claude Code** con un mensaje del estilo:

   > « He actualizado `design-reference/`. Compara con la versión anterior (git diff) y aplica los cambios visuales al código de producción manteniendo la funcionalidad. Resume qué has cambiado. »

5. **Revisa** el resultado lado a lado con el prototipo, en tema claro y oscuro.

> 💡 Como `design-reference/` está versionado en git, `git diff` muestra exactamente qué cambió entre dos iteraciones de diseño. Es la mejor pista para que Claude Code aplique solo lo necesario.

---

## Buenas prácticas para que el "puente" funcione bien

- **Mapea los tokens, no los píxeles sueltos.** Casi todo el aspecto vive en las *custom properties* de `design-reference/styles.css`. Si Claude Code implementa el sistema de producción leyendo esas variables (mismos nombres: `--accent`, `--surface`, `--c-pink`, etc.), la mayoría de los retoques estéticos se reducen a actualizar esas variables. Pídele explícitamente que **reutilice los mismos nombres de variables** que el prototipo.
- **Cambios pequeños y frecuentes** son más fáciles de portar que un rediseño enorme de golpe.
- **Un commit por iteración de diseño.** Commitea la actualización de `design-reference/` por separado del código que la implementa; así el historial cuenta la historia.
- **No edites `design-reference/` a mano** en el repo: es un artefacto que se regenera desde la herramienta de diseño. Si lo tocas, la próxima exportación lo pisará.

---

## Sugerencia: un comando de "sincronizar diseño"

Para hacerlo aún más cómodo, puedes pedirle a Claude Code (una sola vez) que cree un pequeño guion o un *prompt* guardado que haga siempre lo mismo:

> « Crea una nota en `docs/` titulada `sync-design.md` con el procedimiento exacto que debes seguir cuando te diga "sincroniza el diseño": (1) `git diff` de `design-reference/`, (2) identificar tokens y componentes afectados, (3) aplicarlos en `src/`, (4) resumen de cambios. »

Después, cada vez que actualices el prototipo, te bastará con decir **"sincroniza el diseño"**.

---

## Qué NO cambia por este flujo

- El **modelo de datos** y las **reglas de negocio** (`DATA_MODEL.md`) no dependen del prototipo visual; cámbialos por separado y de forma explícita.
- La **estructura de pantallas** (qué pantallas existen y qué hacen) tampoco: si quieres añadir o quitar pantallas, dilo expresamente — no surge de un retoque estético.
