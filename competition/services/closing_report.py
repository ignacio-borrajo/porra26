import io
from dataclasses import dataclass, field
from datetime import timedelta

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
from competition.models import Match, Prediction
from competition.services.standings import StandingRow, standings


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
    active_jugadores = list(User.objects.filter(is_jugador=True, is_active=True).order_by("name"))
    preds = list(Prediction.objects.filter(match=match).select_related("player"))
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
    paras.append(
        Paragraph(
            f"• {stats.bets_count} de {stats.total_players} jugadores han apostado",
            styles["bullet"],
        )
    )
    if stats.most_popular:
        items = " · ".join(f"{score} ({n})" for score, n in stats.most_popular)
        label = (
            "Marcador más popular"
            if len(stats.most_popular) == 1
            else "Marcadores más populares (empate)"
        )
        paras.append(Paragraph(f"• {label}: {items}", styles["bullet"]))
    if stats.split_total:
        h = round(100 * stats.split_home / stats.split_total)
        d = round(100 * stats.split_draw / stats.split_total)
        a = 100 - h - d  # asegura que sumen 100
        paras.append(
            Paragraph(
                f"• Reparto 1 · X · 2: {h} % / {d} % / {a} %",
                styles["bullet"],
            )
        )
    if stats.absent_names:
        if len(stats.absent_names) <= 10:
            paras.append(
                Paragraph(
                    "• Sin apostar: " + ", ".join(stats.absent_names),
                    styles["bullet"],
                )
            )
        else:
            paras.append(
                Paragraph(
                    f"• Sin apostar: {len(stats.absent_names)} jugadores",
                    styles["bullet"],
                )
            )
    return paras


def _predictions_table(match, styles) -> Table:
    preds = {
        p.player_id: p for p in Prediction.objects.filter(match=match).select_related("player")
    }
    jugadores = list(User.objects.filter(is_jugador=True, is_active=True).order_by("name"))
    data = [["Jugador", "Pronóstico", "Pts"]]
    for u in jugadores:
        p = preds.get(u.id)
        if p is None:
            pred_cell = "—"
            pts_cell = "—"
        else:
            pred_cell = f"{p.home} - {p.away}"
            pts_cell = "—" if p.earned is None else str(p.earned)
        data.append([u.name, pred_cell, pts_cell])
    # Ancho útil A4 con márgenes 18 mm = 174 mm: 90 + 54 + 30.
    table = Table(data, colWidths=[90 * mm, 54 * mm, 30 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#EEEEEE")),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F8F8F8")]),
                ("BOX", (0, 0), (-1, -1), 0.4, HexColor("#DDDDDD")),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, HexColor("#DDDDDD")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _matchday_scope_label(match: Match) -> str:
    """Etiqueta de la sección de clasificación local al partido."""
    if match.matchday is not None:
        return f"Jornada {match.matchday}"
    return match.round.label


def _format_delta(matchday_pos: int, general_pos: int | None) -> str:
    """Diferencia de posición entre la jornada y la general.

    Positivo = mejor en la jornada que en la general.
    """
    if general_pos is None:
        return "—"
    diff = general_pos - matchday_pos
    if diff > 0:
        return f"+{diff}"
    if diff < 0:
        return str(diff)
    return "="


def _classification_table(
    title: str,
    rows: list[StandingRow],
    *,
    delta_against: dict[int, int] | None = None,
    max_rows: int = 20,
) -> Table:
    """Tabla compacta de clasificación para layout a dos columnas.

    Cuando `delta_against` se proporciona, añade una columna 'Dif' con la
    diferencia de posición respecto a esa clasificación (positivo = mejor aquí).
    """
    has_delta = delta_against is not None
    headers = ["Pos", "Jugador", "Pts"] + (["Dif"] if has_delta else [])
    data = [headers]
    shown = rows[:max_rows]
    for r in shown:
        row = [str(r.position), r.name, str(r.pts)]
        if has_delta:
            row.append(_format_delta(r.position, delta_against.get(r.player_id)))
        data.append(row)
    if len(rows) > max_rows:
        extra = ["", f"… y {len(rows) - max_rows} más", ""]
        if has_delta:
            extra.append("")
        data.append(extra)

    # Ancho objetivo ≈ 82 mm.
    if has_delta:
        col_widths = [9 * mm, 45 * mm, 14 * mm, 14 * mm]
    else:
        col_widths = [10 * mm, 56 * mm, 16 * mm]

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#EEEEEE")),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, HexColor("#F8F8F8")]),
        ("BOX", (0, 0), (-1, -1), 0.4, HexColor("#DDDDDD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, HexColor("#DDDDDD")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if has_delta:
        style_cmds.append(("ALIGN", (3, 0), (3, -1), "CENTER"))

    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))

    block_title = Paragraph(
        f"<b>{title}</b>",
        ParagraphStyle(
            "clf-title",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            spaceAfter=3,
            textColor=HexColor("#333333"),
        ),
    )
    block = Table([[block_title], [table]], colWidths=[sum(col_widths)])
    block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return block


def _classification_block(match: Match, styles) -> Table:
    general_rows = standings()
    matchday_rows = standings(round_id=match.round_id, matchday=match.matchday)
    general_pos = {r.player_id: r.position for r in general_rows}

    matchday_played = any(r.pts > 0 for r in matchday_rows)
    matchday_table = _classification_table(
        _matchday_scope_label(match),
        matchday_rows,
        delta_against=general_pos if matchday_played else None,
    )
    general_table = _classification_table("General", general_rows)

    wrap = Table(
        [[matchday_table, "", general_table]],
        colWidths=[82 * mm, 10 * mm, 82 * mm],
    )
    wrap.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return wrap


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
        "title": ParagraphStyle(
            "title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20
        ),
        "sub": ParagraphStyle(
            "sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=HexColor("#555555"),
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Helvetica", fontSize=10, leading=14
        ),
    }
    stats = compute_closing_stats(match)

    flow = []
    flow.append(
        Paragraph(
            f"{match.home.name} <font color='#888888'>vs</font> {match.away.name}",
            styles["title"],
        )
    )
    kickoff_local = timezone.localtime(match.kickoff)
    close_local = timezone.localtime(match.kickoff - timedelta(hours=2))
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

    flow.append(Paragraph("Clasificación", styles["h2"]))
    flow.append(_classification_block(match, styles))

    doc.build(flow, onFirstPage=_draw_header_band, onLaterPages=_draw_header_band)
    return buf.getvalue()
