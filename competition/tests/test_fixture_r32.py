import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "world_cup_2026.json"

EXPECTED = {
    "M74": ("2026-06-29T20:30:00Z", 1),
    "M77": ("2026-06-30T21:00:00Z", 2),
    "M73": ("2026-06-28T19:00:00Z", 3),
    "M75": ("2026-06-30T01:00:00Z", 4),
    "M83": ("2026-07-02T23:00:00Z", 5),
    "M84": ("2026-07-02T19:00:00Z", 6),
    "M81": ("2026-07-02T00:00:00Z", 7),
    "M82": ("2026-07-01T20:00:00Z", 8),
    "M76": ("2026-06-29T17:00:00Z", 9),
    "M78": ("2026-06-30T17:00:00Z", 10),
    "M79": ("2026-07-01T01:00:00Z", 11),
    "M80": ("2026-07-01T16:00:00Z", 12),
    "M86": ("2026-07-03T22:00:00Z", 13),
    "M88": ("2026-07-03T18:00:00Z", 14),
    "M85": ("2026-07-03T03:00:00Z", 15),
    "M87": ("2026-07-04T01:30:00Z", 16),
}


def test_r32_fixture_kickoffs_and_order():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_code = {
        e["fields"]["bracket_code"]: e["fields"]
        for e in data
        if e["fields"].get("bracket_code") in EXPECTED
    }
    assert set(by_code) == set(EXPECTED)
    for code, (kickoff, order) in EXPECTED.items():
        assert by_code[code]["kickoff"] == kickoff, code
        assert by_code[code]["bracket_order"] == order, code
