import io
from datetime import timedelta

import pdfplumber
import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import Match
from competition.services.closing_report import build_closing_pdf, compute_closing_stats
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
    TeamFactory,
)


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
    UserFactory(is_jugador=True, is_active=True, name="Carla")
    PredictionFactory(match=match, player=p1, home=2, away=1)
    PredictionFactory(match=match, player=p2, home=2, away=1)
    stats = compute_closing_stats(match)
    assert stats.total_players == 3
    assert stats.bets_count == 2
    assert stats.absent_names == ["Carla"]


@pytest.mark.django_db
def test_stats_most_popular_score():
    match = MatchFactory()
    for _ in range(3):
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
def test_pdf_predictions_table_includes_points_column():
    """La tabla de pronósticos muestra los puntos ganados por cada jugador."""
    match = MatchFactory(home=TeamFactory(code="ESP"), away=TeamFactory(code="ARG"))
    ganador = UserFactory(is_jugador=True, is_active=True, name="Ana Acierto")
    fallon = UserFactory(is_jugador=True, is_active=True, name="Beto Fallo")
    PredictionFactory(match=match, player=ganador, home=2, away=1, earned=3)
    PredictionFactory(match=match, player=fallon, home=0, away=0, earned=0)

    pdf = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        # La primera página contiene la tabla de pronósticos.
        rows = doc.pages[0].extract_tables()
    # Aplanamos cabeceras de todas las tablas para encontrar la de pronósticos.
    pred_table = next(t for t in rows if t and "Pronóstico" in t[0])
    assert pred_table[0] == ["Jugador", "Pronóstico", "Pts"]
    by_name = {row[0]: row for row in pred_table[1:]}
    assert by_name["Ana Acierto"][2] == "3"
    assert by_name["Beto Fallo"][2] == "0"


@pytest.mark.django_db
def test_pdf_predictions_pts_dash_when_not_scored():
    """Antes de introducir el resultado oficial, la columna Pts muestra '—'."""
    match = MatchFactory()
    p = UserFactory(is_jugador=True, is_active=True, name="Sin Puntuar")
    PredictionFactory(match=match, player=p, home=1, away=1, earned=None)
    pdf = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        tables = doc.pages[0].extract_tables()
    pred_table = next(t for t in tables if t and "Pronóstico" in t[0])
    by_name = {row[0]: row for row in pred_table[1:]}
    assert by_name["Sin Puntuar"][1] == "1 - 1"
    assert by_name["Sin Puntuar"][2] == "—"


@pytest.mark.django_db
def test_pdf_includes_matchday_and_general_classification():
    """El PDF muestra clasificación de jornada y general lado a lado."""
    match = MatchFactory(matchday=2)
    UserFactory(is_jugador=True, is_active=True, name="Solo General")
    pdf = build_closing_pdf(match)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(page.extract_text() or "" for page in doc.pages)
    assert "Jornada 2" in text
    assert "General" in text


@pytest.mark.django_db
def test_pdf_matchday_delta_against_general():
    """En la clasificación de jornada, Δ refleja la diferencia vs la general."""
    rnd = RoundFactory(points=3)
    now = timezone.now()
    # Partido finalizado de la jornada 1 que da puntos a Ana.
    j1 = Match.objects.create(
        round=rnd,
        group="A",
        matchday=1,
        home=TeamFactory(code="AA1"),
        away=TeamFactory(code="BB1"),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
        finished_at=now,
    )
    # Partido de jornada 2 sobre el que se genera el PDF, finalizado.
    j2 = Match.objects.create(
        round=rnd,
        group="A",
        matchday=2,
        home=TeamFactory(code="AA2"),
        away=TeamFactory(code="BB2"),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )
    ana = UserFactory(is_jugador=True, is_active=True, name="Ana")
    beto = UserFactory(is_jugador=True, is_active=True, name="Beto")
    # En la general Ana lleva 6 puntos (3+3), Beto 0.
    PredictionFactory(match=j1, player=ana, home=1, away=0, earned=3)
    PredictionFactory(match=j1, player=beto, home=0, away=2, earned=0)
    # En la jornada 2 solo puntúa Beto, así que pasa de #2 a #1 de la jornada.
    PredictionFactory(match=j2, player=ana, home=0, away=0, earned=0)
    PredictionFactory(match=j2, player=beto, home=2, away=1, earned=3)

    pdf = build_closing_pdf(j2)
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        tables = []
        for page in doc.pages:
            tables.extend(page.extract_tables())
    # Buscamos la tabla con cabecera ['Pos', 'Jugador', 'Pts', 'Dif'].
    matchday_table = next(t for t in tables if t and t[0] == ["Pos", "Jugador", "Pts", "Dif"])
    rows_by_name = {row[1]: row for row in matchday_table[1:]}
    # Beto: pos jornada 1, pos general 2 → +1.
    assert rows_by_name["Beto"][3] == "+1"
    # Ana: pos jornada 2, pos general 1 → -1.
    assert rows_by_name["Ana"][3] == "-1"


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
