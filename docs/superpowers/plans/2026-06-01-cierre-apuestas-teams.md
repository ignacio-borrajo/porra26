# Cierre de apuestas → PDF → Teams — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cuando se cierra la ventana de apuestas de un partido (`kickoff − 2 h`), el canal de Teams de la empresa recibe automáticamente un PDF con las apuestas, un resumen estadístico y la clasificación general. La aplicación expone endpoints autenticados; un Flow externo de Power Automate los sondea, publica en Teams y confirma el envío.

**Architecture:** Patrón *pull*. Django ofrece tres endpoints bajo `/api/teams/` protegidos con token Bearer. Una nueva tabla `BetsClosingReport` (1‑1 con `Match`) lleva el estado por partido. El PDF se genera al vuelo con ReportLab en cada GET (idempotente porque el partido ya está cerrado). Hay además un botón de descarga manual para el gestor desde la página de Resultados.

**Tech Stack:** Django 5 · Python 3.12 · `reportlab>=4` para PDF · `pdfplumber` para tests de contenido · `secrets.compare_digest` para auth · pytest-django + factory-boy + freezegun para tests.

**Spec de referencia:** [`docs/superpowers/specs/2026-06-01-cierre-apuestas-teams-design.md`](../specs/2026-06-01-cierre-apuestas-teams-design.md).

---

## Estructura de archivos

**Nuevos:**

- `competition/migrations/0005_betsclosingreport.py` — migración (auto-generada con `makemigrations`).
- `competition/services/closing_report.py` — `compute_closing_stats(match)` + `build_closing_pdf(match)`.
- `competition/api/__init__.py`
- `competition/api/auth.py` — decorador `require_teams_api_token`.
- `competition/api/views.py` — `cierres_pendientes`, `cierre_pdf`, `marcar_enviado`.
- `competition/api/urls.py` — sub-urlconf bajo `/api/teams/`.
- `competition/tests/test_teams_api_auth.py` — tests del decorador.
- `competition/tests/test_teams_api_endpoints.py` — tests de los tres endpoints.
- `competition/tests/test_closing_report_service.py` — tests del service (stats + PDF).
- `docs/TEAMS_FLOW.md` — guía paso a paso del Flow de Power Automate.

**Modificados:**

- `competition/models.py` — añade modelo `BetsClosingReport` + propiedad `Match.teams_slug`.
- `competition/admin.py` — registra `BetsClosingReport`.
- `competition/urls.py` — incluye `api/urls.py`.
- `competition/views.py` — `ManageResultsView` carga datos de envíos para la nueva sección.
- `templates/competition/manage_results.html` — botón "PDF cierre" y bloque "Estado de envíos a Teams".
- `requirements.txt` — añade `reportlab>=4.0`.
- `requirements-dev.txt` — añade `pdfplumber>=0.11`.
- `porra26/settings/base.py` — añade lectura de `TEAMS_API_TOKEN`.
- `.env.example` — añade `TEAMS_API_TOKEN` y `PORRA_BASE_URL`.
- `docs/DEPLOY.md` — sección "Token de integración Teams".
- `docs/RUNBOOK.md` — verificación periódica de envíos.

---

## Task 1: Dependencias y configuración

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Modify: `porra26/settings/base.py`
- Modify: `.env.example`

- [ ] **Step 1: Añadir `reportlab` a `requirements.txt`**

Edita `requirements.txt` y añade al final:

```
reportlab>=4.0,<5
```

- [ ] **Step 2: Añadir `pdfplumber` a `requirements-dev.txt`**

Edita `requirements-dev.txt` y añade al final:

```
pdfplumber>=0.11
```

- [ ] **Step 3: Instalar dependencias**

```bash
pip install -r requirements-dev.txt
```

Expected: instala `reportlab` y `pdfplumber` sin errores.

- [ ] **Step 4: Añadir lectura del token en settings**

En `porra26/settings/base.py`, al final del fichero, añade:

```python
TEAMS_API_TOKEN = os.getenv("TEAMS_API_TOKEN", "")
```

- [ ] **Step 5: Añadir variables a `.env.example`**

En `.env.example`, al final:

```
TEAMS_API_TOKEN=
PORRA_BASE_URL=https://porra26.pythonanywhere.com
```

- [ ] **Step 6: Verificar que Django arranca**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 7: Commit**

```bash
git add requirements.txt requirements-dev.txt porra26/settings/base.py .env.example
git commit -m "feat(teams): añade reportlab/pdfplumber y variable TEAMS_API_TOKEN"
```

---

## Task 2: Modelo `BetsClosingReport` y propiedad `Match.teams_slug`

**Files:**
- Modify: `competition/models.py`
- Create: `competition/migrations/0005_betsclosingreport.py` (auto-generada)
- Create: `competition/tests/test_closing_report_model.py`

- [ ] **Step 1: Crear test fallido del modelo**

Crea `competition/tests/test_closing_report_model.py`:

```python
import pytest
from django.db import IntegrityError

from competition.models import BetsClosingReport
from competition.tests.factories import MatchFactory


@pytest.mark.django_db
def test_betsclosingreport_default_values():
    match = MatchFactory()
    report = BetsClosingReport.objects.create(match=match)
    assert report.attempts == 0
    assert report.generated_at is None
    assert report.sent_at is None
    assert report.last_sha256 == ""
    assert report.created_at is not None


@pytest.mark.django_db
def test_betsclosingreport_is_one_to_one_with_match():
    match = MatchFactory()
    BetsClosingReport.objects.create(match=match)
    with pytest.raises(IntegrityError):
        BetsClosingReport.objects.create(match=match)


@pytest.mark.django_db
def test_match_teams_slug():
    from competition.tests.factories import TeamFactory
    from datetime import datetime
    from django.utils import timezone

    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(
        home=home,
        away=away,
        kickoff=timezone.make_aware(datetime(2026, 6, 14, 21, 0)),
    )
    assert match.teams_slug == "esp-vs-arg-2026-06-14"
```

- [ ] **Step 2: Ejecutar test (debe fallar)**

```bash
pytest competition/tests/test_closing_report_model.py -v
```

Expected: FAIL con `ImportError: cannot import name 'BetsClosingReport'` y `AttributeError` para `teams_slug`.

- [ ] **Step 3: Añadir modelo y propiedad**

En `competition/models.py`, al final del fichero:

```python
class BetsClosingReport(models.Model):
    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="closing_report",
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["sent_at"])]

    def __str__(self):
        return f"ClosingReport(match={self.match_id}, sent={self.sent_at is not None})"
```

Y en la clase `Match`, junto a las demás propiedades:

```python
    @property
    def teams_slug(self) -> str:
        return f"{self.home_id.lower()}-vs-{self.away_id.lower()}-{self.kickoff:%Y-%m-%d}"
```

- [ ] **Step 4: Generar la migración**

```bash
python manage.py makemigrations competition --name betsclosingreport
```

Expected: crea `competition/migrations/0005_betsclosingreport.py`.

- [ ] **Step 5: Aplicar la migración**

```bash
python manage.py migrate
```

Expected: `Applying competition.0005_betsclosingreport... OK`.

- [ ] **Step 6: Ejecutar tests**

```bash
pytest competition/tests/test_closing_report_model.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add competition/models.py competition/migrations/0005_betsclosingreport.py competition/tests/test_closing_report_model.py
git commit -m "feat(teams): modelo BetsClosingReport y Match.teams_slug"
```

---

## Task 3: Service — estadísticas de cierre

**Files:**
- Create: `competition/services/closing_report.py`
- Create: `competition/tests/test_closing_report_service.py`

- [ ] **Step 1: Crear test fallido de `compute_closing_stats`**

Crea `competition/tests/test_closing_report_service.py`:

```python
import pytest

from accounts.tests.factories import UserFactory
from competition.services.closing_report import compute_closing_stats
from competition.tests.factories import MatchFactory, PredictionFactory


@pytest.mark.django_db
def test_stats_count_active_jugadores_only():
    match = MatchFactory()
    UserFactory(is_jugador=True, is_active=True)
    UserFactory(is_jugador=True, is_active=True)
    UserFactory(is_jugador=False, is_active=True)
    UserFactory(is_jugador=True, is_active=False)
    stats = compute_closing_stats(match)
    assert stats.total_players == 2


@pytest.mark.django_db
def test_stats_count_bets_and_absentees():
    match = MatchFactory()
    p1 = UserFactory(is_jugador=True, is_active=True, name="Ana")
    p2 = UserFactory(is_jugador=True, is_active=True, name="Beto")
    p3 = UserFactory(is_jugador=True, is_active=True, name="Carla")
    PredictionFactory(match=match, player=p1, home=2, away=1)
    PredictionFactory(match=match, player=p2, home=2, away=1)
    stats = compute_closing_stats(match)
    assert stats.total_players == 3
    assert stats.bets_count == 2
    assert stats.absent_names == ["Carla"]


@pytest.mark.django_db
def test_stats_most_popular_score():
    match = MatchFactory()
    for i in range(3):
        PredictionFactory(match=match, player=UserFactory(), home=2, away=1)
    PredictionFactory(match=match, player=UserFactory(), home=1, away=0)
    stats = compute_closing_stats(match)
    assert stats.most_popular == [("2-1", 3)]


@pytest.mark.django_db
def test_stats_most_popular_tie():
    match = MatchFactory()
    PredictionFactory(match=match, player=UserFactory(), home=2, away=1)
    PredictionFactory(match=match, player=UserFactory(), home=1, away=0)
    stats = compute_closing_stats(match)
    # empate a 1 voto cada uno → ambos
    assert len(stats.most_popular) == 2


@pytest.mark.django_db
def test_stats_split_1x2():
    match = MatchFactory()
    # 3 victorias locales, 1 empate, 1 visitante
    for _ in range(3):
        PredictionFactory(match=match, player=UserFactory(), home=2, away=0)
    PredictionFactory(match=match, player=UserFactory(), home=1, away=1)
    PredictionFactory(match=match, player=UserFactory(), home=0, away=2)
    stats = compute_closing_stats(match)
    assert stats.split_home == 3
    assert stats.split_draw == 1
    assert stats.split_away == 1


@pytest.mark.django_db
def test_stats_empty_match():
    match = MatchFactory()
    UserFactory(is_jugador=True, is_active=True)
    stats = compute_closing_stats(match)
    assert stats.bets_count == 0
    assert stats.most_popular == []
    assert stats.split_home == 0 and stats.split_draw == 0 and stats.split_away == 0
```

- [ ] **Step 2: Ejecutar test (debe fallar)**

```bash
pytest competition/tests/test_closing_report_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'competition.services.closing_report'`.

- [ ] **Step 3: Implementar `compute_closing_stats`**

Crea `competition/services/closing_report.py`:

```python
from dataclasses import dataclass, field

from accounts.models import User
from competition.models import Match, Prediction


@dataclass
class ClosingStats:
    total_players: int
    bets_count: int
    absent_names: list[str] = field(default_factory=list)
    most_popular: list[tuple[str, int]] = field(default_factory=list)
    split_home: int = 0
    split_draw: int = 0
    split_away: int = 0

    @property
    def split_total(self) -> int:
        return self.split_home + self.split_draw + self.split_away


def compute_closing_stats(match: Match) -> ClosingStats:
    active_jugadores = list(
        User.objects.filter(is_jugador=True, is_active=True).order_by("name")
    )
    preds = list(
        Prediction.objects.filter(match=match).select_related("player")
    )
    bettor_ids = {p.player_id for p in preds}
    absent_names = [u.name for u in active_jugadores if u.id not in bettor_ids]

    counter: dict[str, int] = {}
    split_home = split_draw = split_away = 0
    for p in preds:
        key = f"{p.home}-{p.away}"
        counter[key] = counter.get(key, 0) + 1
        if p.home > p.away:
            split_home += 1
        elif p.home == p.away:
            split_draw += 1
        else:
            split_away += 1

    most_popular: list[tuple[str, int]] = []
    if counter:
        top = max(counter.values())
        most_popular = sorted(
            [(k, v) for k, v in counter.items() if v == top],
            key=lambda kv: kv[0],
        )

    return ClosingStats(
        total_players=len(active_jugadores),
        bets_count=len(preds),
        absent_names=absent_names,
        most_popular=most_popular,
        split_home=split_home,
        split_draw=split_draw,
        split_away=split_away,
    )
```

- [ ] **Step 4: Ejecutar tests**

```bash
pytest competition/tests/test_closing_report_service.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add competition/services/closing_report.py competition/tests/test_closing_report_service.py
git commit -m "feat(teams): service compute_closing_stats con tests"
```

---

## Task 4: Service — generación del PDF

**Files:**
- Modify: `competition/services/closing_report.py`
- Modify: `competition/tests/test_closing_report_service.py`

- [ ] **Step 1: Añadir tests fallidos de `build_closing_pdf`**

Añade al final de `competition/tests/test_closing_report_service.py`:

```python
import io

import pdfplumber

from competition.services.closing_report import build_closing_pdf


@pytest.mark.django_db
def test_pdf_is_valid_pdf_bytes():
    match = MatchFactory()
    pdf = build_closing_pdf(match)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF-")


@pytest.mark.django_db
def test_pdf_contains_match_header():
    from competition.tests.factories import TeamFactory

    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(home=home, away=away, group="D")
    pdf = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(page.extract_text() or "" for page in doc.pages)
    assert "PORRA 26" in text
    assert "Cierre de apuestas" in text
    assert "España" in text
    assert "Argentina" in text
    assert "Grupo D" in text


@pytest.mark.django_db
def test_pdf_contains_predictions():
    match = MatchFactory()
    p1 = UserFactory(is_jugador=True, is_active=True, name="Ana García")
    p2 = UserFactory(is_jugador=True, is_active=True, name="Beto López")
    PredictionFactory(match=match, player=p1, home=2, away=1)
    PredictionFactory(match=match, player=p2, home=0, away=0)
    pdf = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(page.extract_text() or "" for page in doc.pages)
    assert "Ana García" in text
    assert "2 - 1" in text
    assert "Beto López" in text
    assert "0 - 0" in text


@pytest.mark.django_db
def test_pdf_shows_dash_for_absent_jugadores():
    match = MatchFactory()
    UserFactory(is_jugador=True, is_active=True, name="Carlos Sin")
    pdf = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(page.extract_text() or "" for page in doc.pages)
    assert "Carlos Sin" in text
    assert "—" in text


@pytest.mark.django_db
def test_pdf_summary_shows_bet_counts():
    match = MatchFactory()
    for _ in range(3):
        PredictionFactory(match=match, player=UserFactory(is_jugador=True, is_active=True))
    UserFactory(is_jugador=True, is_active=True)  # no apuesta
    pdf = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(page.extract_text() or "" for page in doc.pages)
    assert "3 de 4" in text


@pytest.mark.django_db
def test_pdf_is_deterministic():
    """Mismo input → bytes con el mismo contenido textual (las fechas del pie pueden variar)."""
    match = MatchFactory()
    pdf1 = build_closing_pdf(match)
    pdf2 = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf1)) as d1, pdfplumber.open(io.BytesIO(pdf2)) as d2:
        t1 = "\n".join(p.extract_text() or "" for p in d1.pages)
        t2 = "\n".join(p.extract_text() or "" for p in d2.pages)
    # Quitamos la hora del pie (cambia entre llamadas) y comparamos el resto.
    def strip_footer(t: str) -> str:
        return "\n".join(line for line in t.splitlines() if not line.startswith("Generado el"))
    assert strip_footer(t1) == strip_footer(t2)
```

- [ ] **Step 2: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_closing_report_service.py -v -k "pdf"
```

Expected: 6 FAIL — `ImportError: cannot import name 'build_closing_pdf'`.

- [ ] **Step 3: Implementar `build_closing_pdf`**

Añade al final de `competition/services/closing_report.py`:

```python
import io
from datetime import datetime

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from accounts.models import User
from competition.services.standings import standings

GRADIENT_STOPS = [HexColor("#FF7A00"), HexColor("#00C2FF"), HexColor("#7A5AF8")]


def _draw_header_band(canvas, doc):
    """Dibuja banda de degradado horizontal y título sobre el canvas."""
    canvas.saveState()
    width, height = A4
    band_h = 28 * mm
    y0 = height - band_h
    # Degradado: 60 franjas verticales interpolando entre los 3 stops.
    strips = 60
    for i in range(strips):
        t = i / (strips - 1)
        if t < 0.5:
            local = t / 0.5
            c = colors.linearlyInterpolatedColor(GRADIENT_STOPS[0], GRADIENT_STOPS[1], 0, 1, local)
        else:
            local = (t - 0.5) / 0.5
            c = colors.linearlyInterpolatedColor(GRADIENT_STOPS[1], GRADIENT_STOPS[2], 0, 1, local)
        canvas.setFillColor(c)
        canvas.rect(i * width / strips, y0, width / strips + 0.5, band_h, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(18 * mm, y0 + 16 * mm, "PORRA 26")
    canvas.setFont("Helvetica", 12)
    canvas.drawString(18 * mm, y0 + 8 * mm, "Cierre de apuestas")
    # Pie
    canvas.setFillColor(HexColor("#555555"))
    canvas.setFont("Helvetica", 8)
    footer = f"Generado el {timezone.localtime():%d %b %Y · %H:%M} · porra26.pythonanywhere.com"
    canvas.drawString(18 * mm, 10 * mm, footer)
    canvas.drawRightString(width - 18 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _bullet_paragraphs(stats, styles):
    paras = []
    paras.append(Paragraph(
        f"• {stats.bets_count} de {stats.total_players} jugadores han apostado",
        styles["bullet"],
    ))
    if stats.most_popular:
        items = " · ".join(f"{score} ({n})" for score, n in stats.most_popular)
        label = "Marcador más popular" if len(stats.most_popular) == 1 else "Marcadores más populares (empate)"
        paras.append(Paragraph(f"• {label}: {items}", styles["bullet"]))
    if stats.split_total:
        h = round(100 * stats.split_home / stats.split_total)
        d = round(100 * stats.split_draw / stats.split_total)
        a = 100 - h - d  # asegura que sumen 100
        paras.append(Paragraph(
            f"• Reparto 1 · X · 2: {h} % / {d} % / {a} %",
            styles["bullet"],
        ))
    if stats.absent_names:
        if len(stats.absent_names) <= 10:
            paras.append(Paragraph(
                "• Sin apostar: " + ", ".join(stats.absent_names),
                styles["bullet"],
            ))
        else:
            paras.append(Paragraph(
                f"• Sin apostar: {len(stats.absent_names)} jugadores",
                styles["bullet"],
            ))
    return paras


def _predictions_table(match, styles) -> Table:
    from competition.models import Prediction

    preds = {
        p.player_id: p
        for p in Prediction.objects.filter(match=match).select_related("player")
    }
    jugadores = list(
        User.objects.filter(is_jugador=True, is_active=True).order_by("name")
    )
    data = [["Jugador", "Pronóstico"]]
    for u in jugadores:
        p = preds.get(u.id)
        cell = f"{p.home} - {p.away}" if p else "—"
        data.append([u.name, cell])
    table = Table(data, colWidths=[110 * mm, 40 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#EEEEEE")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F8F8F8")]),
        ("BOX", (0, 0), (-1, -1), 0.4, HexColor("#DDDDDD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, HexColor("#DDDDDD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _standings_table(styles) -> Table:
    rows = standings()
    data = [["Pos", "Jugador", "Pts"]]
    shown = rows[:20]
    for r in shown:
        data.append([str(r.position), r.name, str(r.pts)])
    if len(rows) > 20:
        data.append(["", f"… y {len(rows) - 20} jugadores más", ""])
    table = Table(data, colWidths=[15 * mm, 110 * mm, 25 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#EEEEEE")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F8F8F8")]),
        ("BOX", (0, 0), (-1, -1), 0.4, HexColor("#DDDDDD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, HexColor("#DDDDDD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def build_closing_pdf(match: Match) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=38 * mm,  # deja sitio para la banda de cabecera
        bottomMargin=18 * mm,
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=14, textColor=HexColor("#555555")),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=10, spaceAfter=4),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=14),
    }
    stats = compute_closing_stats(match)

    flow = []
    flow.append(Paragraph(
        f"{match.home.name} <font color='#888888'>vs</font> {match.away.name}",
        styles["title"],
    ))
    from datetime import timedelta as _td
    kickoff_local = timezone.localtime(match.kickoff)
    close_local = timezone.localtime(match.kickoff - _td(hours=2))
    sub = (
        f"{match.round.label} · Grupo {match.group} · "
        f"{kickoff_local:%d %b %Y, %H:%M} · Cierre {close_local:%H:%M}"
    )
    flow.append(Paragraph(sub, styles["sub"]))
    flow.append(Spacer(1, 8 * mm))

    flow.append(Paragraph("Resumen", styles["h2"]))
    flow.extend(_bullet_paragraphs(stats, styles))
    flow.append(Spacer(1, 6 * mm))

    flow.append(Paragraph("Pronósticos", styles["h2"]))
    flow.append(_predictions_table(match, styles))
    flow.append(Spacer(1, 6 * mm))

    flow.append(Paragraph("Clasificación general", styles["h2"]))
    flow.append(_standings_table(styles))

    doc.build(flow, onFirstPage=_draw_header_band, onLaterPages=_draw_header_band)
    return buf.getvalue()
```

- [ ] **Step 4: Ejecutar tests**

```bash
pytest competition/tests/test_closing_report_service.py -v
```

Expected: 12 passed (los 6 de stats + 6 de PDF).

- [ ] **Step 5: Commit**

```bash
git add competition/services/closing_report.py competition/tests/test_closing_report_service.py
git commit -m "feat(teams): build_closing_pdf con cabecera, resumen, pronósticos y clasificación"
```

---

## Task 5: Decorador `require_teams_api_token`

**Files:**
- Create: `competition/api/__init__.py`
- Create: `competition/api/auth.py`
- Create: `competition/tests/test_teams_api_auth.py`

- [ ] **Step 1: Crear paquete `api`**

Crea fichero vacío `competition/api/__init__.py`:

```python
```

- [ ] **Step 2: Crear tests fallidos del decorador**

Crea `competition/tests/test_teams_api_auth.py`:

```python
import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from accounts.tests.factories import GestorFactory, UserFactory
from competition.api.auth import require_teams_api_token


@require_teams_api_token
def fake_view(request, **kwargs):
    return HttpResponse("ok")


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_accepts_correct_bearer_token():
    rf = RequestFactory()
    req = rf.get("/x", HTTP_AUTHORIZATION="Bearer testing-token-1234567890")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 200


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_rejects_wrong_token():
    rf = RequestFactory()
    req = rf.get("/x", HTTP_AUTHORIZATION="Bearer otro")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_rejects_missing_header():
    rf = RequestFactory()
    req = rf.get("/x")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_accepts_gestor_session_without_token():
    rf = RequestFactory()
    req = rf.get("/x")
    req.user = GestorFactory()
    res = fake_view(req)
    assert res.status_code == 200


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="testing-token-1234567890")
def test_rejects_jugador_session_without_token():
    rf = RequestFactory()
    req = rf.get("/x")
    req.user = UserFactory(is_gestor=False)
    res = fake_view(req)
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN="")
def test_empty_setting_rejects_all_bearer():
    rf = RequestFactory()
    req = rf.get("/x", HTTP_AUTHORIZATION="Bearer cualquier-cosa")
    req.user = type("Anon", (), {"is_authenticated": False, "is_gestor": False})()
    res = fake_view(req)
    assert res.status_code == 401
```

- [ ] **Step 3: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_teams_api_auth.py -v
```

Expected: 6 FAIL — `ModuleNotFoundError: No module named 'competition.api.auth'`.

- [ ] **Step 4: Implementar el decorador**

Crea `competition/api/auth.py`:

```python
import logging
import secrets
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def _bearer_token_ok(request) -> bool:
    expected = getattr(settings, "TEAMS_API_TOKEN", "") or ""
    if not expected:
        return False
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return False
    received = header[len("Bearer "):].strip()
    return secrets.compare_digest(received, expected)


def _gestor_session_ok(request) -> bool:
    user = getattr(request, "user", None)
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_gestor", False)
    )


def require_teams_api_token(view):
    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if _bearer_token_ok(request) or _gestor_session_ok(request):
            return view(request, *args, **kwargs)
        logger.warning(
            "teams-api: unauthorized request path=%s ip=%s ua=%s",
            request.path,
            request.META.get("REMOTE_ADDR"),
            request.META.get("HTTP_USER_AGENT", "")[:120],
        )
        return JsonResponse(
            {"detail": "Token inválido o sesión no autorizada"},
            status=401,
        )

    return wrapper
```

- [ ] **Step 5: Ejecutar tests**

```bash
pytest competition/tests/test_teams_api_auth.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add competition/api/__init__.py competition/api/auth.py competition/tests/test_teams_api_auth.py
git commit -m "feat(teams): decorador require_teams_api_token (Bearer + sesión gestor)"
```

---

## Task 6: Endpoint `GET /api/teams/cierres-pendientes`

**Files:**
- Create: `competition/api/views.py`
- Create: `competition/api/urls.py`
- Modify: `competition/urls.py`
- Create: `competition/tests/test_teams_api_endpoints.py`

- [ ] **Step 1: Crear test fallido del endpoint**

Crea `competition/tests/test_teams_api_endpoints.py`:

```python
from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from competition.models import BetsClosingReport
from competition.tests.factories import MatchFactory, TeamFactory

TOKEN = "testing-token-1234567890"
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_returns_only_closed_unsent(client):
    now = timezone.now()
    # Abierto: cierra en 4h → no aparece
    MatchFactory(kickoff=now + timedelta(hours=6))
    # Cerrado y sin envío → aparece
    m_closed = MatchFactory(kickoff=now + timedelta(hours=1))
    # Cerrado y enviado → no aparece
    m_sent = MatchFactory(kickoff=now + timedelta(hours=1))
    BetsClosingReport.objects.create(match=m_sent, sent_at=now)
    # Cerrado, con report pero sin sent_at → aparece
    m_pending = MatchFactory(kickoff=now + timedelta(hours=1))
    BetsClosingReport.objects.create(match=m_pending)

    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    assert res.status_code == 200
    ids = sorted(m["id"] for m in res.json()["matches"])
    assert ids == sorted([m_closed.id, m_pending.id])


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_includes_live_and_done_if_unsent(client):
    now = timezone.now()
    # Live (sin resultado, kickoff pasado)
    m_live = MatchFactory(kickoff=now - timedelta(minutes=5))
    # Done (con resultado)
    m_done = MatchFactory(
        kickoff=now - timedelta(days=1),
        result_home=1,
        result_away=0,
        finished_at=now - timedelta(hours=1),
    )
    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    ids = sorted(m["id"] for m in res.json()["matches"])
    assert m_live.id in ids
    assert m_done.id in ids


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_ordered_by_kickoff_asc(client):
    now = timezone.now()
    m1 = MatchFactory(kickoff=now - timedelta(hours=3))
    m2 = MatchFactory(kickoff=now - timedelta(hours=2))
    m3 = MatchFactory(kickoff=now - timedelta(hours=1))
    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    ids = [m["id"] for m in res.json()["matches"]]
    assert ids == [m1.id, m2.id, m3.id]


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_payload_shape(client):
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    kickoff = timezone.now() - timedelta(minutes=10)
    m = MatchFactory(home=home, away=away, group="D", kickoff=kickoff)
    res = client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    payload = res.json()["matches"][0]
    assert payload["id"] == m.id
    assert payload["slug"] == m.teams_slug
    assert payload["round"] == m.round.label
    assert payload["group"] == "D"
    assert payload["home"] == {"code": "ESP", "name": "España"}
    assert payload["away"] == {"code": "ARG", "name": "Argentina"}
    assert "kickoff" in payload
    assert "closed_at" in payload


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_does_not_create_reports(client):
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    client.get(reverse("competicion:api:cierres_pendientes"), **AUTH)
    assert BetsClosingReport.objects.count() == 0


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pendientes_requires_token(client):
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierres_pendientes"))
    assert res.status_code == 401
```

- [ ] **Step 2: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_teams_api_endpoints.py -v
```

Expected: FAIL — `NoReverseMatch: Reverse for 'cierres_pendientes' not found`.

- [ ] **Step 3: Crear vista del endpoint**

Crea `competition/api/views.py`:

```python
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone

from competition.api.auth import require_teams_api_token
from competition.models import BET_CLOSE_HOURS, Match


def _match_payload(m: Match) -> dict:
    closed_at = m.kickoff - timedelta(hours=BET_CLOSE_HOURS)
    return {
        "id": m.id,
        "slug": m.teams_slug,
        "round": m.round.label,
        "round_id": m.round_id,
        "group": m.group,
        "home": {"code": m.home_id, "name": m.home.name},
        "away": {"code": m.away_id, "name": m.away.name},
        "kickoff": m.kickoff.isoformat(),
        "closed_at": closed_at.isoformat(),
    }


@require_teams_api_token
def cierres_pendientes(request):
    """Devuelve los matches cuyo cierre ya pasó y que aún no se han enviado a Teams.

    El filtro `closing_report__sent_at__isnull=True` no nos vale por sí solo
    porque deja fuera los matches sin BetsClosingReport. Filtramos en Python
    para cubrir ambos casos en una única consulta con prefetch del OneToOne.
    """
    now = timezone.now()
    qs = (
        Match.objects
        .filter(kickoff__lte=now + timedelta(hours=BET_CLOSE_HOURS))
        .select_related("home", "away", "round")
        .order_by("kickoff")
    )
    pendientes = []
    for m in qs:
        report = getattr(m, "closing_report", None)
        if report is None or report.sent_at is None:
            pendientes.append(m)
    return JsonResponse({"matches": [_match_payload(m) for m in pendientes]})
```

- [ ] **Step 4: Crear `competition/api/urls.py`**

```python
from django.urls import path

from competition.api import views

app_name = "api"

urlpatterns = [
    path("cierres-pendientes/", views.cierres_pendientes, name="cierres_pendientes"),
]
```

- [ ] **Step 5: Incluir en `competition/urls.py`**

Reemplaza el contenido de `competition/urls.py` por:

```python
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.CompetitionView.as_view(), name="dashboard"),
    path("pronosticar/<int:match_id>/", views.PredictView.as_view(), name="predict"),
    path("partido/<int:match_id>/", views.MatchDetailView.as_view(), name="detail"),
    path("resultados/", views.ManageResultsView.as_view(), name="manage_results"),
    path("resultados/<int:match_id>/", views.ResultOfficialView.as_view(), name="official"),
    path("api/teams/", include(("competition.api.urls", "api"), namespace="api")),
]
```

- [ ] **Step 6: Ejecutar tests**

```bash
pytest competition/tests/test_teams_api_endpoints.py -v
```

Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add competition/api/views.py competition/api/urls.py competition/urls.py competition/tests/test_teams_api_endpoints.py
git commit -m "feat(teams): endpoint GET /api/teams/cierres-pendientes"
```

---

## Task 7: Endpoint `GET /api/teams/cierres/<id>/pdf`

**Files:**
- Modify: `competition/api/views.py`
- Modify: `competition/api/urls.py`
- Modify: `competition/tests/test_teams_api_endpoints.py`

- [ ] **Step 1: Añadir tests fallidos**

Añade al final de `competition/tests/test_teams_api_endpoints.py`:

```python
import hashlib


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_returns_pdf(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]), **AUTH)
    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert "attachment" in res["Content-Disposition"]
    assert m.teams_slug in res["Content-Disposition"]
    assert bytes(res.content).startswith(b"%PDF-")


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_creates_report_and_updates(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]), **AUTH)
    assert res.status_code == 200
    report = BetsClosingReport.objects.get(match=m)
    assert report.attempts == 1
    assert report.generated_at is not None
    expected_sha = hashlib.sha256(bytes(res.content)).hexdigest()
    assert report.last_sha256 == expected_sha


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_increments_attempts(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    url = reverse("competicion:api:cierre_pdf", args=[m.id])
    client.get(url, **AUTH)
    client.get(url, **AUTH)
    client.get(url, **AUTH)
    assert BetsClosingReport.objects.get(match=m).attempts == 3


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_404_if_not_closed(client):
    m = MatchFactory(kickoff=timezone.now() + timedelta(hours=6))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]), **AUTH)
    assert res.status_code == 404


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_404_unknown_match(client):
    res = client.get(reverse("competicion:api:cierre_pdf", args=[999_999]), **AUTH)
    assert res.status_code == 404


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_requires_token(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]))
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_pdf_endpoint_accepts_gestor_session(client):
    from accounts.tests.factories import GestorFactory

    gestor = GestorFactory()
    client.force_login(gestor)
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.get(reverse("competicion:api:cierre_pdf", args=[m.id]))
    assert res.status_code == 200
```

- [ ] **Step 2: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_teams_api_endpoints.py::test_pdf_endpoint_returns_pdf -v
```

Expected: `NoReverseMatch: Reverse for 'cierre_pdf' not found`.

- [ ] **Step 3: Implementar la vista**

Añade a `competition/api/views.py`:

```python
import hashlib

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone as _tz

from competition.models import BetsClosingReport
from competition.services.closing_report import build_closing_pdf


@require_teams_api_token
def cierre_pdf(request, match_id: int):
    match = get_object_or_404(
        Match.objects.select_related("home", "away", "round"),
        pk=match_id,
    )
    now = _tz.now()
    if match.kickoff - timedelta(hours=BET_CLOSE_HOURS) > now:
        # todavía abierto → no hay PDF de cierre
        return JsonResponse({"detail": "Partido todavía no cerrado"}, status=404)

    pdf_bytes = build_closing_pdf(match)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    with transaction.atomic():
        report, _ = BetsClosingReport.objects.select_for_update().get_or_create(match=match)
        report.attempts += 1
        report.generated_at = now
        report.last_sha256 = sha
        report.save(update_fields=["attempts", "generated_at", "last_sha256"])

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"cierre-{match.teams_slug}.pdf"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
```

- [ ] **Step 4: Añadir ruta a `competition/api/urls.py`**

Reemplaza `urlpatterns` por:

```python
urlpatterns = [
    path("cierres-pendientes/", views.cierres_pendientes, name="cierres_pendientes"),
    path("cierres/<int:match_id>/pdf/", views.cierre_pdf, name="cierre_pdf"),
]
```

- [ ] **Step 5: Ejecutar tests**

```bash
pytest competition/tests/test_teams_api_endpoints.py -v -k "pdf"
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add competition/api/views.py competition/api/urls.py competition/tests/test_teams_api_endpoints.py
git commit -m "feat(teams): endpoint GET /api/teams/cierres/<id>/pdf con persistencia de attempts/sha256"
```

---

## Task 8: Endpoint `POST /api/teams/cierres/<id>/marcar-enviado`

**Files:**
- Modify: `competition/api/views.py`
- Modify: `competition/api/urls.py`
- Modify: `competition/tests/test_teams_api_endpoints.py`

- [ ] **Step 1: Añadir tests fallidos**

Añade al final de `competition/tests/test_teams_api_endpoints.py`:

```python
import json

from accounts.models import AuditLog


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_marcar_enviado_marks_sent_and_creates_audit(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.post(
        reverse("competicion:api:cierre_marcar_enviado", args=[m.id]),
        data=json.dumps({"teams_message_id": "abc-123"}),
        content_type="application/json",
        **AUTH,
    )
    assert res.status_code == 200
    report = BetsClosingReport.objects.get(match=m)
    assert report.sent_at is not None
    payload = res.json()
    assert payload["sent_at"]
    audits = AuditLog.objects.filter(action="bets_pdf_sent")
    assert audits.count() == 1
    assert audits.first().payload == {"teams_message_id": "abc-123"}


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_marcar_enviado_idempotent(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    url = reverse("competicion:api:cierre_marcar_enviado", args=[m.id])
    res1 = client.post(url, data="{}", content_type="application/json", **AUTH)
    res2 = client.post(url, data="{}", content_type="application/json", **AUTH)
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res2.json()["already_sent"] is True
    assert AuditLog.objects.filter(action="bets_pdf_sent").count() == 1


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_marcar_enviado_creates_report_if_missing(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    assert not BetsClosingReport.objects.filter(match=m).exists()
    client.post(
        reverse("competicion:api:cierre_marcar_enviado", args=[m.id]),
        data="{}", content_type="application/json", **AUTH,
    )
    assert BetsClosingReport.objects.filter(match=m, sent_at__isnull=False).exists()


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_marcar_enviado_handles_empty_body(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.post(
        reverse("competicion:api:cierre_marcar_enviado", args=[m.id]),
        data="", content_type="application/json", **AUTH,
    )
    assert res.status_code == 200


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_marcar_enviado_requires_token(client):
    m = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    res = client.post(
        reverse("competicion:api:cierre_marcar_enviado", args=[m.id]),
        data="{}", content_type="application/json",
    )
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_marcar_enviado_404_unknown_match(client):
    res = client.post(
        reverse("competicion:api:cierre_marcar_enviado", args=[999_999]),
        data="{}", content_type="application/json", **AUTH,
    )
    assert res.status_code == 404
```

- [ ] **Step 2: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_teams_api_endpoints.py -v -k "marcar"
```

Expected: 6 FAIL con `NoReverseMatch`.

- [ ] **Step 3: Implementar la vista**

Añade a `competition/api/views.py`:

```python
import json as _json

from django.views.decorators.http import require_POST

from accounts.models import AuditLog


@require_POST
@require_teams_api_token
def cierre_marcar_enviado(request, match_id: int):
    match = get_object_or_404(Match, pk=match_id)
    try:
        body = _json.loads(request.body.decode("utf-8")) if request.body else {}
    except _json.JSONDecodeError:
        body = {}
    teams_message_id = body.get("teams_message_id", "")

    with transaction.atomic():
        report, _ = BetsClosingReport.objects.select_for_update().get_or_create(match=match)
        if report.sent_at is not None:
            return JsonResponse(
                {"already_sent": True, "sent_at": report.sent_at.isoformat()}
            )
        report.sent_at = _tz.now()
        report.save(update_fields=["sent_at"])
        AuditLog.objects.create(
            actor=None,
            action="bets_pdf_sent",
            target_type="match",
            target_id=str(match.id),
            payload={"teams_message_id": teams_message_id} if teams_message_id else {},
        )

    return JsonResponse({"sent_at": report.sent_at.isoformat()})
```

- [ ] **Step 4: Añadir ruta a `competition/api/urls.py`**

Reemplaza `urlpatterns` por:

```python
urlpatterns = [
    path("cierres-pendientes/", views.cierres_pendientes, name="cierres_pendientes"),
    path("cierres/<int:match_id>/pdf/", views.cierre_pdf, name="cierre_pdf"),
    path("cierres/<int:match_id>/marcar-enviado/", views.cierre_marcar_enviado, name="cierre_marcar_enviado"),
]
```

- [ ] **Step 5: Ejecutar tests**

```bash
pytest competition/tests/test_teams_api_endpoints.py -v
```

Expected: 19 passed (6 pendientes + 7 pdf + 6 marcar-enviado).

- [ ] **Step 6: Commit**

```bash
git add competition/api/views.py competition/api/urls.py competition/tests/test_teams_api_endpoints.py
git commit -m "feat(teams): endpoint POST /api/teams/cierres/<id>/marcar-enviado idempotente"
```

---

## Task 9: Registro en Django admin

**Files:**
- Modify: `competition/admin.py`

- [ ] **Step 1: Inspeccionar admin actual**

```bash
cat competition/admin.py
```

- [ ] **Step 2: Registrar `BetsClosingReport`**

Añade al final de `competition/admin.py`:

```python
from competition.models import BetsClosingReport


@admin.register(BetsClosingReport)
class BetsClosingReportAdmin(admin.ModelAdmin):
    list_display = ("match", "generated_at", "sent_at", "attempts")
    list_filter = ("sent_at",)
    search_fields = ("match__home__name", "match__away__name")
    readonly_fields = ("created_at", "last_sha256")
    fields = ("match", "generated_at", "sent_at", "attempts", "last_sha256", "created_at")
```

> Si `admin` no estaba importado en el fichero, añade `from django.contrib import admin` arriba.

- [ ] **Step 3: Verificar que el admin arranca**

```bash
python manage.py check
```

Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add competition/admin.py
git commit -m "feat(teams): registra BetsClosingReport en Django admin"
```

---

## Task 10: UI — Botón "PDF cierre" en página de Resultados

**Files:**
- Modify: `templates/competition/manage_results.html`

- [ ] **Step 1: Añadir botón en sección PENDIENTES**

En `templates/competition/manage_results.html`, dentro del bloque `{% if pending %}`, **antes** del `<a class="btn btn-primary">Finalizar</a>`, ajusta la `grid-template-columns` a `auto 1fr auto auto auto` y añade el botón:

```html
  <div class="glass table-row" style="display:grid;grid-template-columns:auto 1fr auto auto auto;gap:14px;align-items:center;padding:12px 14px;border-radius:14px">
    <span class="mono" style="color:var(--text-faint)">Grupo {{ m.group }}</span>
    <span>{{ m.home.flag }} {{ m.home.name }} vs {{ m.away.flag }} {{ m.away.name }}</span>
    <span class="chip chip-{{ m.status }}">{{ m.status }}</span>
    <a class="btn btn-ghost" href="{% url 'competicion:api:cierre_pdf' m.id %}" style="padding:6px 12px;font-size:12px" title="Descargar PDF de cierre">📄 PDF</a>
    <a class="btn btn-primary" href="{% url 'competicion:official' m.id %}" style="padding:6px 12px;font-size:12px">Finalizar</a>
  </div>
```

- [ ] **Step 2: Repetir en sección FINALIZADOS**

Misma operación: ajustar `grid-template-columns` y añadir el botón antes del `Editar`:

```html
  <div class="glass table-row" style="display:grid;grid-template-columns:auto 1fr auto auto auto;gap:14px;align-items:center;padding:12px 14px;border-radius:14px">
    <span class="mono" style="color:var(--text-faint)">Grupo {{ m.group }}</span>
    <span>{{ m.home.flag }} {{ m.home.name }} {{ m.result_home }}–{{ m.result_away }} {{ m.away.flag }} {{ m.away.name }}</span>
    <span class="chip chip-done">Final</span>
    <a class="btn btn-ghost" href="{% url 'competicion:api:cierre_pdf' m.id %}" style="padding:6px 12px;font-size:12px" title="Descargar PDF de cierre">📄 PDF</a>
    <a class="btn btn-ghost" href="{% url 'competicion:official' m.id %}" style="padding:6px 12px;font-size:12px">Editar</a>
  </div>
```

> En la sección PRÓXIMOS **no** se añade el botón: el match aún no está cerrado y el endpoint devolvería 404.

- [ ] **Step 3: Probar manualmente**

```bash
python manage.py runserver
```

Loguéate como gestor, ve a `/competicion/resultados/`, comprueba que aparece el botón "📄 PDF" en partidos cerrados/finales y que al pulsarlo se descarga un PDF.

- [ ] **Step 4: Commit**

```bash
git add templates/competition/manage_results.html
git commit -m "feat(teams): botón 'PDF cierre' en página de Resultados"
```

---

## Task 11: UI — Sección "Estado de envíos a Teams"

**Files:**
- Modify: `competition/views.py`
- Modify: `templates/competition/manage_results.html`

- [ ] **Step 1: Cargar datos en `ManageResultsView`**

En `competition/views.py`, dentro de `ManageResultsView.get`, **después** de calcular `pending/upcoming/done` y **antes** del `return render(...)`, añade:

```python
        from competition.models import BetsClosingReport

        reports = list(
            BetsClosingReport.objects
            .select_related("match__home", "match__away", "match__round")
            .order_by("-match__kickoff")
        )
```

Y en el diccionario de contexto del `render`, añade `"reports": reports,`. Queda así (extracto):

```python
        return render(
            request,
            "competition/manage_results.html",
            {
                "rounds": rounds,
                "active_round": active_id,
                "matchdays": matchdays,
                "active_matchday": active_md,
                "matchday_state": matchday_state,
                "pending": pending,
                "upcoming": upcoming,
                "done": done,
                "reports": reports,
            },
        )
```

- [ ] **Step 2: Renderizar la sección**

En `templates/competition/manage_results.html`, **antes** del `{% endblock %}` final, añade:

```html
{% if reports %}
<details style="margin-top:24px">
  <summary class="eyebrow" style="cursor:pointer;list-style:none">ESTADO DE ENVÍOS A TEAMS · {{ reports|length }}</summary>
  <div class="table-scroll" style="margin-top:8px;display:flex;flex-direction:column;gap:6px">
    <div style="display:grid;grid-template-columns:1fr auto auto auto auto;gap:14px;padding:6px 14px;color:var(--text-faint);font-size:11px;text-transform:uppercase;letter-spacing:0.6px">
      <span>Partido</span>
      <span>Generado</span>
      <span>Enviado</span>
      <span>Intentos</span>
      <span>Última generación</span>
    </div>
    {% for r in reports %}
    <div class="glass table-row" style="display:grid;grid-template-columns:1fr auto auto auto auto;gap:14px;align-items:center;padding:10px 14px;border-radius:12px">
      <span>{{ r.match.home.flag }} {{ r.match.home.name }} vs {{ r.match.away.flag }} {{ r.match.away.name }}</span>
      <span title="{{ r.generated_at|default:'' }}">{% if r.generated_at %}✓{% else %}—{% endif %}</span>
      <span>
        {% if r.sent_at %}<span style="color:#16a34a">✓</span>
        {% elif r.attempts %}<span style="color:#d97706">⏳</span>
        {% else %}—{% endif %}
      </span>
      <span class="mono">{{ r.attempts }}</span>
      <span class="mono" style="font-size:11px">{{ r.generated_at|date:"d M · H:i"|default:"—" }}</span>
    </div>
    {% endfor %}
  </div>
</details>
{% endif %}
```

- [ ] **Step 3: Verificación manual**

```bash
python manage.py runserver
```

Loguéate como gestor, descarga un PDF, recarga `/competicion/resultados/` y comprueba que aparece la sección colapsable con el partido en estado "Generado ✓, Enviado —".

- [ ] **Step 4: Commit**

```bash
git add competition/views.py templates/competition/manage_results.html
git commit -m "feat(teams): sección 'Estado de envíos a Teams' en página de Resultados"
```

---

## Task 12: Documentación — `docs/TEAMS_FLOW.md`

**Files:**
- Create: `docs/TEAMS_FLOW.md`

- [ ] **Step 1: Crear el documento**

Crea `docs/TEAMS_FLOW.md`:

```markdown
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
- URI: `https://porra26.pythonanywhere.com/api/teams/cierres-pendientes/`
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
- URI: `https://porra26.pythonanywhere.com/api/teams/cierres/@{items('Apply_to_each')?['id']}/pdf/`
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
- URI: `https://porra26.pythonanywhere.com/api/teams/cierres/@{items('Apply_to_each')?['id']}/marcar-enviado/`
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/TEAMS_FLOW.md
git commit -m "docs(teams): guía paso a paso para configurar el flow en Power Automate"
```

---

## Task 13: Documentación — `DEPLOY.md` y `RUNBOOK.md`

**Files:**
- Modify: `docs/DEPLOY.md`
- Modify: `docs/RUNBOOK.md`

- [ ] **Step 1: Inspeccionar fichero**

```bash
cat docs/DEPLOY.md
```

- [ ] **Step 2: Añadir sección a `DEPLOY.md`**

Añade al final de `docs/DEPLOY.md`:

```markdown
## Token de integración con Teams

La aplicación expone endpoints en `/api/teams/` que consume un Flow de Power Automate (ver `docs/TEAMS_FLOW.md`). Protegidos con un token Bearer.

1. Genera un token aleatorio de 64+ caracteres:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. En el `.env` de PythonAnywhere añade:

   ```
   TEAMS_API_TOKEN=<token generado>
   PORRA_BASE_URL=https://porra26.pythonanywhere.com
   ```

3. Recarga la web app desde el panel de PythonAnywhere.

4. Configura el flow siguiendo `docs/TEAMS_FLOW.md` pegando el mismo token en sus tres acciones HTTP.

Si `TEAMS_API_TOKEN` queda vacío, los endpoints siguen respondiendo pero **rechazan toda autenticación Bearer**: nunca se debe arrancar producción sin token configurado.
```

- [ ] **Step 3: Añadir verificación a `RUNBOOK.md`**

Añade al final de `docs/RUNBOOK.md`:

```markdown
## Verificar envíos a Teams

Cada lunes, abre `/competicion/resultados/` como gestor y revisa la sección **"Estado de envíos a Teams"**:

- Todos los partidos cerrados desde la semana pasada deben aparecer con ✓ en Generado y ✓ en Enviado.
- Si algún partido aparece con ⏳ (ámbar) o solo Generado ✓ pero Enviado —, significa que el flow no consiguió publicar:
  1. Abre https://make.powerautomate.com y revisa el historial del flow `PORRA 26 · Cierre apuestas a Teams`.
  2. Si el error es del conector de Teams, reintenta la ejecución desde Power Automate.
  3. Si el error es de autenticación contra la app, comprueba que `TEAMS_API_TOKEN` coincide en ambos sitios (ver `docs/DEPLOY.md`).
  4. Como solución manual de emergencia, descarga el PDF con el botón "📄 PDF" y súbelo a Teams a mano.
```

- [ ] **Step 4: Commit**

```bash
git add docs/DEPLOY.md docs/RUNBOOK.md
git commit -m "docs(teams): añade token al deploy y verificación periódica al runbook"
```

---

## Task 14: Suite completa y verificación final

**Files:** ninguno (verificación)

- [ ] **Step 1: Ejecutar toda la suite**

```bash
pytest -v
```

Expected: todos los tests pasan (los nuevos suman 3 + 12 + 6 + 19 = 40).

- [ ] **Step 2: Lint**

```bash
ruff check competition/
ruff format --check competition/ porra26/
```

Expected: sin errores (si hay, arreglar inline antes del commit final).

- [ ] **Step 3: Verificación manual — flujo completo simulado**

```bash
python manage.py runserver
```

En otro terminal, simula a Power Automate con `curl`:

```bash
TOKEN=$(grep TEAMS_API_TOKEN .env | cut -d= -f2)

curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/competicion/api/teams/cierres-pendientes/ | python -m json.tool

# Toma un match_id del listado y descarga su PDF
curl -s -H "Authorization: Bearer $TOKEN" \
  -o /tmp/cierre.pdf \
  http://localhost:8000/competicion/api/teams/cierres/<ID>/pdf/
file /tmp/cierre.pdf
# Expected: PDF document, version 1.4

# Marca como enviado
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"teams_message_id":"manual-test"}' \
  http://localhost:8000/competicion/api/teams/cierres/<ID>/marcar-enviado/

# Verifica idempotencia
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:8000/competicion/api/teams/cierres/<ID>/marcar-enviado/
# Expected: {"already_sent": true, ...}
```

- [ ] **Step 4: Verificación manual — UI**

Como gestor:
1. `/competicion/resultados/` → ver botón "📄 PDF" en pendientes/finalizados.
2. Pulsar el botón → descarga PDF con cabecera, resumen, tabla de pronósticos y clasificación.
3. La sección "Estado de envíos a Teams" muestra el partido marcado por curl.

Como jugador (no gestor):
1. `/competicion/resultados/` → redirección, sin acceso.
2. Acceso directo a `/competicion/api/teams/cierres/<ID>/pdf/` sin token → 401.

- [ ] **Step 5: Commit final**

Si quedó algún cambio del lint:

```bash
git add -A
git commit -m "chore(teams): ajustes de lint tras la implementación"
```

Si no, no se hace commit.

---

## Resumen

Implementación TDD en 14 tasks. Cada task deja la suite verde y un commit. Al final:

- 3 endpoints HTTP autenticados con Bearer (y aceptando sesión de gestor para descarga manual).
- 1 nueva tabla `BetsClosingReport` con estado por partido.
- 1 service `closing_report` (stats + PDF).
- 1 botón de descarga en UI de gestor.
- 1 sección de auditoría de envíos en UI de gestor.
- 1 guía completa para configurar Power Automate.
- 40+ tests nuevos verdes.
