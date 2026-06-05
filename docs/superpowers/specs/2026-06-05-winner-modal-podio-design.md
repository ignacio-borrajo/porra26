# Modal de ganador: podio 1·2·3 y cuantía corregida

Fecha: 2026-06-05

## Problema

El modal de celebración de ganadores tiene dos problemas:

1. **Bug de cuantía en el modal "Campeón del Mundial"**. `pot/services/prizes.py::matchday_winners` usa `PotSettings.matchday_winner_prize` para todos los scopes, incluido `global`. El campeón del Mundial debería leer `Prize[scope='global', position=1].amount` (configurable desde "Premios y puntos"). El resultado: el campeón ve una cuantía que no corresponde con el premio del podio final.
2. **Falta de presencia del 2.º y 3.º puesto en el cierre del Mundial**. Cuando ya hay campeón, sería natural mostrar también las posiciones 2 y 3 con su cuantía respectiva. Hoy el modal solo presenta a quien ocupa la posición 1.
3. **El importe pasa desapercibido** en los modales de jornada/ronda KO porque va en una línea pequeña ("Se lleva 5,00 €").

## Diseño

### 1. Fix del bug

`pot/services/prizes.py::matchday_winners` deja de usar `PotSettings.matchday_winner_prize` para el scope `global`. En su lugar, lee `Prize.objects.filter(scope='global', position=1).first().amount`. Para `matchday` y `round` no cambia nada.

### 2. Podio en todos los modales

Nueva función `pot/services/prizes.py::announcement_podium(announcement) -> list[PodiumEntry]`:

```python
@dataclass
class PodiumEntry:
    position: int           # 1, 2 o 3
    users: list[User]       # uno o varios si la plaza está empatada
    prize_per_user: Decimal # 0 si la plaza no tiene premio económico
    tied: bool
```

**Reglas por scope:**

| Scope    | Standings filtrados por       | Premio p1                                | Premio p2                                | Premio p3                                |
|----------|-------------------------------|------------------------------------------|------------------------------------------|------------------------------------------|
| matchday | `round='groups', matchday=N`  | `PotSettings.matchday_winner_prize`      | 0                                        | 0                                        |
| round    | `round=R`                     | `PotSettings.matchday_winner_prize`      | 0                                        | 0                                        |
| global   | sin filtro                    | `Prize[scope='global', position=1].amount` | `Prize[scope='global', position=2].amount` | `Prize[scope='global', position=3].amount` |

En matchday/round, las plazas 2 y 3 son honoríficas (sin dinero). Aun así el modal las pinta, porque dan contexto y sirven como recordatorio de progresión hacia el podio final.

**Cálculo:**
- Llama a `standings(...)` filtrado por scope.
- Mantiene solo filas con `pts > 0` y `position <= 3` (omite plazas vacías).
- Agrupa por `position`. Para cada grupo: carga usuarios reales, `prize_per_user = base / len(grupo)`, `tied = len(grupo) > 1`.

**Computa al renderizar**, no se persiste. Justificación: las clasificaciones son estables tras la resolución de los partidos del scope; y si el gestor ajusta cuantías en "Premios y puntos" antes de que un jugador haya visto el modal, queremos que el modal refleje la cuantía vigente.

`WinnerAnnouncement.share` y `WinnerAnnouncement.winners` se mantienen tal cual están (siguen representando la posición 1). No hay migración.

### 3. Render del modal

`templates/announcements/_winner_modal.html`:

- Cabecera: trofeo + título + puntos del líder (igual que ahora).
- Cuerpo: lista vertical de entradas `🥇 · 🥈 · 🥉`, una por `PodiumEntry`. Cada entrada:
  - Medalla y badge de posición (`1º`, `2º`, `3º` cuando hay empate de varios, con el prefijo `=`).
  - Tarjeta(s) de jugador (avatar + nombre).
  - Si `prize_per_user > 0`: una **tarjeta dorada de premio** (icono `€` + cuantía); microtexto "a cada uno" cuando la plaza está empatada.
  - Si `prize_per_user == 0`: nada (sin importe).
- Si solo hay 1 plaza (nadie con puntos en 2 ni 3): se renderiza solo esa fila.
- Confetti y botón de acción se mantienen.

Estilos en `static/css/styles.css` bajo el bloque "Modal ganador". Reutilizamos paleta `--c-gold` para la tarjeta de premio.

### 4. Preview

`announcements/preview.py::build_preview` sigue devolviendo `(WinnerAnnouncement, winners)`, pero se cambia su firma para que también devuelva un `podium`. Reglas:

- Top 1 = `current_user` (gestor). Si `tied=True`, otro usuario.
- Top 2 = otro usuario distinto (si existe en la BD); empate de 2 si `tied=True`.
- Top 3 = otro más (si existe).
- Premios:
  - `matchday`/`round`: pos1 = `PotSettings.matchday_winner_prize`; pos2 y pos3 = 0.
  - `global`: usar las cuantías reales de `Prize.objects.filter(scope='global', position__in=[1,2,3])`.

La vista `AnnouncementPreviewView` y `AnnouncementModalView` inyectan `podium` en el contexto.

### 5. Tests

- `pot/tests/test_prizes.py`:
  - Nuevo: `matchday_winners(("global", None))` usa `Prize[position=1].amount`, no `matchday_winner_prize`.
  - Nuevo: tests para `announcement_podium` cubriendo:
    - scope global → 3 entradas con premios distintos según `Prize`.
    - scope matchday → entrada p1 con premio, p2/p3 con `prize_per_user=0`.
    - scope round → idéntico a matchday.
    - empate en p1 → `tied=True`, share divide en 2.
    - sin nadie con puntos en p3 → solo se devuelven p1 y p2.
- `announcements/tests/test_views.py` (smoke): el modal renderizado contiene cuantías esperadas para cada scope.

## Archivos a tocar

- `pot/services/prizes.py` — fix del scope global + `announcement_podium()` + `PodiumEntry`.
- `announcements/views.py` — inyectar `podium` en contexto (modal real y preview).
- `announcements/preview.py` — generar `podium` sintético.
- `templates/announcements/_winner_modal.html` — nuevo layout.
- `static/css/styles.css` — estilos del podio (tarjeta de premio, badges de posición).
- Tests en `pot/tests/test_prizes.py` y, si procede, `announcements/tests/test_views.py`.

## No incluido

- Persistencia del podio en `WinnerAnnouncement`. Se compute al renderizar.
- Cambios en la página de "Premios y puntos". Los importes ya son configurables.
- Modal de "podio final" separado del modal del Mundial. El modal global es el podio.
