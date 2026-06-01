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
