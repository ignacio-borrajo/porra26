import pytest

from competition.templatetags.competition_extras import slot_label


@pytest.mark.parametrize(
    "code,expected",
    [
        ("1A", "1º Grupo A"),
        ("2B", "2º Grupo B"),
        ("3L", "3º Grupo L"),
        ("WM49", "Ganador M49"),
        ("WM104", "Ganador M104"),
        ("LM101", "Perdedor M101"),
        ("LM102", "Perdedor M102"),
        ("3WG_S1", "Mejor tercero (S1)"),
        ("", "Por definir"),
        ("X9", "Por definir"),
        ("4A", "Por definir"),
        ("1Z", "Por definir"),
    ],
)
def test_slot_label(code, expected):
    assert slot_label(code) == expected
