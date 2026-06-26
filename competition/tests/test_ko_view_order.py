import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.fixture(autouse=True)
def _rounds(db):
    for rid, order, label in [
        ("groups", 1, "Fase de grupos"),
        ("r32", 2, "Dieciseisavos"),
        ("r16", 3, "Octavos"),
        ("qf", 4, "Cuartos"),
        ("sf", 5, "Semifinales"),
        ("final", 6, "Final"),
    ]:
        RoundFactory(id=rid, order=order, label=label, short=rid.upper())


@pytest.mark.django_db
def test_r32_ordered_by_bracket_order(client):
    user = UserFactory()
    for code, order in [("M73", 3), ("M74", 1), ("M77", 2), ("M75", 4)]:
        MatchFactory(
            round_id="r32",
            group="Dieciseisavos",
            matchday=None,
            home=None,
            away=None,
            home_slot="1A",
            away_slot="2A",
            bracket_code=code,
            bracket_order=order,
        )
    client.force_login(user)
    resp = client.get(reverse("competicion:dashboard") + "?round=r32")
    ko = {e["round"].id: e for e in resp.context["ko_rounds"]}["r32"]
    codes = [m.bracket_code for m in ko["matches"]]
    assert codes == ["M74", "M77", "M73", "M75"]
    # parejas por posición: [M74, M77], [M73, M75]
    pair_codes = [[m.bracket_code for m in pair] for pair in ko["pairs"]]
    assert pair_codes == [["M74", "M77"], ["M73", "M75"]]
