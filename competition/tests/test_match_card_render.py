from datetime import timedelta

import pytest
from django.template import Context, Template
from django.utils import timezone

from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_pending_teams_card_shows_por_definir_not_slot_label():
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    m = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="WM73",
        bracket_code="M89",
        kickoff=timezone.now() + timedelta(days=10),
    )
    tpl = Template('{% include "competition/_match_card.html" with match=match %}')
    html = tpl.render(Context({"match": m, "request": None}))

    assert html.count("Por definir") >= 2
    assert "Ganador" not in html
    assert "Grupo A" not in html
