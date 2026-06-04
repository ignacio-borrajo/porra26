#!/usr/bin/env python
"""
Genera los iconos PWA a partir de `static/img/logo.png`.

Idempotente: se puede reejecutar cada vez que cambie el logo fuente.
Escribe en `static/img/pwa/`.

Uso:
    python bin/generate_pwa_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static" / "img" / "logo.png"
OUT_DIR = ROOT / "static" / "img" / "pwa"

# Color de fondo (= --bg-0 del tema oscuro, oklch(0.16 0.02 275) ≈ #1a1530).
BG = (26, 21, 48, 255)

# (filename, canvas_size, logo_ratio)
TARGETS = [
    ("icon-192.png", 192, 0.80),
    ("icon-512.png", 512, 0.80),
    ("icon-192-maskable.png", 192, 0.60),
    ("icon-512-maskable.png", 512, 0.60),
    ("apple-touch-icon.png", 180, 0.80),
]


def render_icon(source: Image.Image, size: int, logo_ratio: float) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), BG)
    # Escalar el logo manteniendo aspecto para que su lado largo ocupe
    # `size * logo_ratio` del lienzo cuadrado.
    target = int(size * logo_ratio)
    scale = target / max(source.width, source.height)
    new_w = max(1, round(source.width * scale))
    new_h = max(1, round(source.height * scale))
    logo = source.resize((new_w, new_h), Image.Resampling.LANCZOS)
    x = (size - new_w) // 2
    y = (size - new_h) // 2
    canvas.alpha_composite(logo, dest=(x, y))
    return canvas


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"No existe el logo fuente: {SOURCE}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    for filename, size, ratio in TARGETS:
        out_path = OUT_DIR / filename
        icon = render_icon(source, size, ratio)
        icon.save(out_path, format="PNG", optimize=True)
        print(f"✔ {out_path.relative_to(ROOT)} ({size}×{size}, logo {int(ratio*100)}%)")


if __name__ == "__main__":
    main()
