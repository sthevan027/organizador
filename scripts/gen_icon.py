#!/usr/bin/env python3
"""Gera o ícone do Organizador de Arquivos.

Dois trilhos de renderização:
  - Tamanhos grandes (>= 48): pasta com gradiente indigo/violeta, aba, sombra suave
    e folhas internas detalhadas.
  - Tamanhos pequenos (< 48): versão simplificada sem detalhes finos nem blur,
    garantindo nitidez nos atalhos de área de trabalho e barra de título.

Uso:
    python scripts/gen_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    print("Pillow não está instalado. Rode: pip install -r requirements.txt")
    sys.exit(1)

Color = Tuple[int, int, int, int]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ICO_PATH = ASSETS_DIR / "organizer.ico"
PNG_PATH = ASSETS_DIR / "organizer.png"

BASE_SIZE = 512
# Tamanhos incluídos no .ico; 256 é o máximo que o Windows usa para ícones padrão.
SIZES: Sequence[int] = (16, 24, 32, 48, 64, 128, 256)
# Limiar abaixo do qual se usa o render simplificado
SMALL_THRESHOLD = 48


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1: Color, c2: Color, t: float) -> Color:
    return (
        int(_lerp(c1[0], c2[0], t)),
        int(_lerp(c1[1], c2[1], t)),
        int(_lerp(c1[2], c2[2], t)),
        int(_lerp(c1[3], c2[3], t)),
    )


def _vertical_gradient(size: Tuple[int, int], top: Color, bottom: Color) -> Image.Image:
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
    full = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    full.paste(layer, position, mask)
    canvas.alpha_composite(full)


# ---------------------------------------------------------------------------
# Render detalhado (>= SMALL_THRESHOLD)
# ---------------------------------------------------------------------------

def _make_folder_detailed(size: int) -> Image.Image:
    """Pasta com gradiente, sombra e folhas internas (tamanhos >= 48)."""
    S = size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    pad = int(S * 0.08)
    body_x0, body_y0 = pad, int(S * 0.30)
    body_x1, body_y1 = S - pad, S - pad
    tab_x0, tab_y0 = pad, int(S * 0.18)
    tab_x1, tab_y1 = int(S * 0.55), int(S * 0.36)
    radius = max(int(S * 0.10), 4)

    # Sombra suave
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [(body_x0 + 4, body_y0 + 8), (body_x1 + 4, body_y1 + 8)],
        radius=radius,
        fill=(0, 0, 0, 110),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(S // 60, 2)))
    img.alpha_composite(shadow)

    # Aba superior
    tab_size = (tab_x1 - tab_x0, tab_y1 - tab_y0)
    tab_grad = _vertical_gradient(
        tab_size, (167, 139, 250, 255), (129, 140, 248, 255)
    )
    tab_mask = _rounded_mask(tab_size, radius)
    _place_with_mask(img, tab_grad, (tab_x0, tab_y0), tab_mask)

    # "Orelha" da aba
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

    # Corpo com gradiente
    body_size = (body_x1 - body_x0, body_y1 - body_y0)
    body_grad = _vertical_gradient(
        body_size, (99, 102, 241, 255), (124, 58, 237, 255)
    )
    body_mask = _rounded_mask(body_size, radius)
    _place_with_mask(img, body_grad, (body_x0, body_y0), body_mask)

    # Brilho sutil no topo do corpo
    gloss = Image.new("RGBA", body_size, (0, 0, 0, 0))
    ImageDraw.Draw(gloss).rounded_rectangle(
        [(0, 0), (body_size[0] - 1, int(body_size[1] * 0.22))],
        radius=radius,
        fill=(255, 255, 255, 60),
    )
    gloss = gloss.filter(ImageFilter.GaussianBlur(max(S // 100, 1)))
    _place_with_mask(img, gloss, (body_x0, body_y0), body_mask)

    # Folhas internas
    sheet_w = int(body_size[0] * 0.44)
    sheet_h = int(body_size[1] * 0.30)
    center_x = body_x0 + body_size[0] // 2
    center_y = body_y0 + int(body_size[1] * 0.62)
    sr = max(int(S * 0.045), 2)

    back_x0 = center_x - sheet_w // 2 - int(S * 0.04)
    back_y0 = center_y - sheet_h // 2 - int(S * 0.015)
    back = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    ImageDraw.Draw(back).rounded_rectangle(
        [(0, 0), (sheet_w - 1, sheet_h - 1)], radius=sr, fill=(255, 255, 255, 235)
    )
    back = back.rotate(-8, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(back, (back_x0, back_y0))

    front_x0 = center_x - sheet_w // 2 + int(S * 0.02)
    front_y0 = center_y - sheet_h // 2 + int(S * 0.01)
    front = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(front)
    fd.rounded_rectangle(
        [(0, 0), (sheet_w - 1, sheet_h - 1)], radius=sr, fill=(255, 255, 255, 255)
    )
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


# ---------------------------------------------------------------------------
# Render simplificado (< SMALL_THRESHOLD)
# ---------------------------------------------------------------------------

def _make_folder_simple(size: int) -> Image.Image:
    """Pasta limpa e nítida para tamanhos pequenos — sem blur, sem detalhes finos."""
    S = size
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = max(int(S * 0.06), 1)
    body_x0, body_y0 = pad, int(S * 0.30)
    body_x1, body_y1 = S - pad, S - pad
    tab_x0, tab_y0 = pad, int(S * 0.17)
    tab_x1, tab_y1 = int(S * 0.56), int(S * 0.35)
    radius = max(int(S * 0.12), 2)

    # Sombra sem blur: meio pixel de deslocamento sólido
    shadow_alpha = 60
    d.rounded_rectangle(
        [(body_x0 + 1, body_y0 + 2), (body_x1 + 1, body_y1 + 2)],
        radius=radius,
        fill=(0, 0, 0, shadow_alpha),
    )

    # Aba
    d.rounded_rectangle(
        [(tab_x0, tab_y0), (tab_x1, tab_y1)],
        radius=radius,
        fill=(148, 131, 241, 255),
    )

    # "Orelha" da aba (triângulo simples)
    ear_pts = [
        (tab_x1 - radius, tab_y0),
        (tab_x1 + max(int(S * 0.10), 1), tab_y0),
        (tab_x1 + max(int(S * 0.16), 1), tab_y1),
        (tab_x1 - radius, tab_y1),
    ]
    d.polygon(ear_pts, fill=(128, 110, 230, 255))

    # Corpo — gradiente feito com dois retângulos sobrepostos e alpha blending simples
    body_rect = [(body_x0, body_y0), (body_x1, body_y1)]
    d.rounded_rectangle(body_rect, radius=radius, fill=(99, 102, 241, 255))

    # Camada escura na metade inferior para simular gradiente
    mid_y = body_y0 + (body_y1 - body_y0) // 2
    bottom_overlay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    do = ImageDraw.Draw(bottom_overlay)
    do.rounded_rectangle(
        [(body_x0, mid_y), (body_x1, body_y1)],
        radius=radius,
        fill=(50, 20, 120, 70),
    )
    img.alpha_composite(bottom_overlay)

    # Brilho sutil no topo do corpo (sem blur — apenas retângulo semitransparente)
    gloss_h = max((body_y1 - body_y0) // 5, 2)
    gloss_overlay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    go = ImageDraw.Draw(gloss_overlay)
    go.rounded_rectangle(
        [(body_x0, body_y0), (body_x1, body_y0 + gloss_h)],
        radius=radius,
        fill=(255, 255, 255, 45),
    )
    img.alpha_composite(gloss_overlay)

    return img


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def _make_folder(size: int) -> Image.Image:
    """Escolhe o render adequado ao tamanho."""
    if size < SMALL_THRESHOLD:
        return _make_folder_simple(size)
    return _make_folder_detailed(size)


def generate() -> Path:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # PNG de preview usa o render detalhado em alta resolução
    base = _make_folder_detailed(BASE_SIZE)
    base.save(PNG_PATH, format="PNG")

    # Monta dict size → frame para controle preciso
    size_frames: dict[int, Image.Image] = {}
    for s in SIZES:
        if s < SMALL_THRESHOLD:
            size_frames[s] = _make_folder_simple(s)
        else:
            size_frames[s] = base.resize((s, s), Image.LANCZOS)

    # Pillow 12+: a primeira imagem passada define o limite máximo de tamanho
    # que é incluído. Passamos do maior para o menor para garantir que todos
    # os frames sejam escritos no .ico.
    sorted_sizes = sorted(size_frames.keys(), reverse=True)
    first = size_frames[sorted_sizes[0]]
    rest = [size_frames[s] for s in sorted_sizes[1:]]

    first.save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in sorted_sizes],
        append_images=rest,
    )
    return ICO_PATH


def main() -> int:
    path = generate()
    print(f"Ícone gerado em: {path}")
    print(f"Preview PNG:     {PNG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
