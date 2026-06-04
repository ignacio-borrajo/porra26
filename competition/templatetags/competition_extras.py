from __future__ import annotations

import re

from django import template

register = template.Library()

GROUP_RE = re.compile(r"^([123])([A-L])$")
WINNER_RE = re.compile(r"^W(M\d+)$")
THIRD_RE = re.compile(r"^3WG_(S\d+)$")


@register.filter(name="slot_label")
def slot_label(code: str) -> str:
    """Etiqueta legible para un código de slot. 'Por definir' si no se reconoce."""
    if not code:
        return "Por definir"
    if m := GROUP_RE.match(code):
        pos, group = m.group(1), m.group(2)
        return f"{pos}º Grupo {group}"
    if m := WINNER_RE.match(code):
        return f"Ganador {m.group(1)}"
    if m := THIRD_RE.match(code):
        return f"Mejor tercero ({m.group(1)})"
    return "Por definir"
