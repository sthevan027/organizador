#!/usr/bin/env python3
"""Gera o ícone do Organizador de Arquivos.

Desenha uma pasta estilizada com gradiente indigo -> violeta, aba superior
mais clara e cantos arredondados, exportando o resultado em múltiplas
resoluções dentro de ``assets/organizer.ico``.

Uso:
    python scripts/gen_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover - orientação ao usuário
    print("Pillow não está instalado. Rode: pip install -r requirements.txt")
    sys.exit(1)

Color = Tuple[int, int, int, int]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ICO_PATH = ASSETS_DIR / "organizer.ico"
PNG_PATH = ASSETS_DIR / "organizer.png"

BASE_SIZE = 512
SIZES: Sequence[int] = (16, 24, 32, 48, 64, 128, 256)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1: Color, c2: Color, t: float) -> Color:
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
        int(_lerp(c1[3], c2[3], t)),
    )


def _vertical_gradient(
    size: Tuple[int, int], top: Color, bottom: Color
) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        color = _mix(top, bottom, t)
        for x in range(w):
            px[x, y] = color
    return img


def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


def _place_with_mask(
    canvas: Image.Image,
    layer: Image.Image,
    position: Tuple[int, int],
    mask: Image.Image,
) -> None:
    """Aplica `layer` em `canvas` respeitando uma máscara (compondo em alpha)."""
    full = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    full.paste(layer, position, mask)
    canvas.alpha_composite(full)


def _make_folder(size: int) -> Image.Image:
    """Desenha a pasta no tamanho pedido em RGBA."""
    S = size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Margens e geometria
    pad = int(S * 0.08)
    body_x0, body_y0 = pad, int(S * 0.30)
    body_x1, body_y1 = S - pad, S - pad
    tab_x0, tab_y0 = pad, int(S * 0.18)
    tab_x1, tab_y1 = int(S * 0.55), int(S * 0.36)
    radius = max(int(S * 0.10), 4)

    # --- Sombra suave por trás da pasta
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(body_x0 + 4, body_y0 + 8), (body_x1 + 4, body_y1 + 8)],
        radius=radius,
        fill=(0, 0, 0, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(S // 60, 2)))
    img.alpha_composite(shadow)

    # --- Aba superior (mais clara)
    tab_size = (tab_x1 - tab_x0, tab_y1 - tab_y0)
    tab_grad = _vertical_gradient(
        tab_size, (167, 139, 250, 255), (129, 140, 248, 255)  # violet-400 -> indigo-400
    )
    tab_mask = _rounded_mask(tab_size, radius)
    _place_with_mask(img, tab_grad, (tab_x0, tab_y0), tab_mask)

    # Pequena "orelha" à direita da aba (triangulo arredondado simulado)
    ear = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ed = ImageDraw.Draw(ear)
    ear_points = [
        (tab_x1 - radius, tab_y0),
        (tab_x1 + int(S * 0.07), tab_y0),
        (tab_x1 + int(S * 0.14), tab_y1),
        (tab_x1 - radius, tab_y1),
    ]
    ed.polygon(ear_points, fill=(139, 115, 240, 255))
    img.alpha_composite(ear)

    # --- Corpo da pasta com gradiente principal indigo -> violet
    body_size = (body_x1 - body_x0, body_y1 - body_y0)
    body_grad = _vertical_gradient(
        body_size, (99, 102, 241, 255), (124, 58, 237, 255)  # indigo-500 -> violet-600
    )
    body_mask = _rounded_mask(body_size, radius)
    _place_with_mask(img, body_grad, (body_x0, body_y0), body_mask)

    # --- Brilho superior sutil sobre o corpo (compondo em alpha)
    gloss = Image.new("RGBA", body_size, (0, 0, 0, 0))
    ImageDraw.Draw(gloss).rounded_rectangle(
        [(0, 0), (body_size[0] - 1, int(body_size[1] * 0.22))],
        radius=radius,
        fill=(255, 255, 255, 60),
    )
    gloss = gloss.filter(ImageFilter.GaussianBlur(max(S // 100, 1)))
    _place_with_mask(img, gloss, (body_x0, body_y0), body_mask)

    # --- Ícone interno: duas "folhas" pequenas dentro da pasta, sugerindo
    #     organização sem cobrir o gradiente do corpo
    if S >= 48:
        sheet_w = int(body_size[0] * 0.44)
        sheet_h = int(body_size[1] * 0.30)
        center_x = body_x0 + body_size[0] // 2
        center_y = body_y0 + int(body_size[1] * 0.62)
        sr = max(int(S * 0.045), 2)

        # Folha de trás (inclinada à esquerda)
        back_x0 = center_x - sheet_w // 2 - int(S * 0.04)
        back_y0 = center_y - sheet_h // 2 - int(S * 0.015)
        back = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        ImageDraw.Draw(back).rounded_rectangle(
            [(0, 0), (sheet_w - 1, sheet_h - 1)],
            radius=sr,
            fill=(255, 255, 255, 235),
        )
        back = back.rotate(-8, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(back, (back_x0, back_y0))

        # Folha da frente (centralizada)
        front_x0 = center_x - sheet_w // 2 + int(S * 0.02)
        front_y0 = center_y - sheet_h // 2 + int(S * 0.01)
        front = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
        fd = ImageDraw.Draw(front)
        fd.rounded_rectangle(
            [(0, 0), (sheet_w - 1, sheet_h - 1)],
            radius=sr,
            fill=(255, 255, 255, 255),
        )
        # Três linhas indicando conteúdo
        line_color = (129, 140, 248, 220)
        lh = max(int(sheet_h * 0.08), 2)
        margin = int(sheet_w * 0.16)
        for i, wfrac in enumerate((0.68, 0.80, 0.52)):
            y = int(sheet_h * (0.26 + i * 0.22))
            fd.rounded_rectangle(
                [(margin, y), (margin + int(sheet_w * wfrac), y + lh)],
                radius=lh // 2,
                fill=line_color,
            )
        img.alpha_composite(front, (front_x0, front_y0))

    return img


def generate() -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    base = _make_folder(BASE_SIZE)
    base.save(PNG_PATH, format="PNG")

    frames = []
    for s in SIZES:
        frames.append(base.resize((s, s), Image.LANCZOS))

    frames[0].save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[1:],
    )
    return ICO_PATH


def main() -> int:
    path = generate()
    print(f"Ícone gerado em: {path}")
    print(f"Preview PNG:     {PNG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
