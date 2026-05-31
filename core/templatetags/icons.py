from functools import lru_cache
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@lru_cache(maxsize=64)
def _read(name: str) -> str:
    p = Path(settings.BASE_DIR) / "static" / "icons" / f"{name}.svg"
    return p.read_text(encoding="utf-8") if p.exists() else ""


@register.simple_tag
def icon(name: str, width=18, height=18, **kw):
    raw = _read(name)
    if not raw:
        return ""
    attrs = f'width="{width}" height="{height}"'
    extra = " ".join(f'{k}="{v}"' for k, v in kw.items())
    out = raw.replace("<svg", f'<svg {attrs} {extra}', 1)
    return mark_safe(out)
