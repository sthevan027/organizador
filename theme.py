"""Tokens de design do Organizador de Arquivos.

Centraliza cores, espaçamentos, raios e fontes usados pela GUI para que a
aparência possa ser ajustada em um único lugar e trocada em runtime entre
tema claro e escuro.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Literal

ThemeName = Literal["light", "dark"]

FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"

FONT = {
    "title": (FONT_FAMILY, 20, "bold"),
    "subtitle": (FONT_FAMILY, 11),
    "header_title": (FONT_FAMILY, 16, "bold"),
    "header_subtitle": (FONT_FAMILY, 10),
    "section": (FONT_FAMILY, 12, "bold"),
    "label": (FONT_FAMILY, 11),
    "small": (FONT_FAMILY, 10),
    "button": (FONT_FAMILY, 11, "bold"),
    "button_hero": (FONT_FAMILY, 13, "bold"),
    "stat_value": (FONT_FAMILY, 20, "bold"),
    "stat_label": (FONT_FAMILY, 10),
    "log": ("Consolas", 10) if sys.platform == "win32" else ("Menlo", 10),
}

RADIUS = {
    "card": 14,
    "button": 10,
    "input": 8,
    "pill": 999,
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 14,
    "lg": 20,
    "xl": 28,
}

# Altura fixa do topo (barra de título visual interna)
HEADER_BAR_HEIGHT = 56

# Identidade: laranja como único acento comprometido, sobre neutros
# grafite (escuro) / off-white quente (claro) — estratégia "Restrained"
# (neutros + 1 acento), modo Operate. A barra de cabeçalho fica grafite
# quase-preto nos dois temas (âncora de identidade que não muda com o
# tema — só o corpo troca claro/escuro).
_HEADER_BAR = "#100e0c"
_HEADER_CHIP = "#252220"

LIGHT: Dict[str, str] = {
    "bg": "#faf7f2",
    "bg_alt": "#f1ece3",
    "card": "#ffffff",
    "card_border": "#e7e0d4",
    "header_from": _HEADER_BAR,
    "header_chip": _HEADER_CHIP,
    "header_chip_hover": "#ea580c",
    "text": "#221d16",
    "text_muted": "#7c7364",
    "primary": "#ea580c",
    "primary_hover": "#c2410c",
    "success": "#16a34a",
    "success_hover": "#15803d",
    "warning": "#d97706",
    "warning_hover": "#b45309",
    "danger": "#dc2626",
    "danger_hover": "#b91c1c",
    "neutral": "#8a8172",
    "neutral_hover": "#6b6355",
    "accent": "#ca8a04",
    "accent_hover": "#a16207",
    "log_bg": "#18140f",
    "log_fg": "#f2ede4",
    "log_ok": "#4ade80",
    "log_error": "#f87171",
    "log_warning": "#fbbf24",
    "log_dryrun": "#60a5fa",
    "log_header": "#ffffff",
    "log_info": "#a8a29e",
    "input_bg": "#ffffff",
    "input_border": "#ddd4c4",
    "divider": "#e7e0d4",
    "progress_trough": "#e7e0d4",
    "progress_fill": "#ea580c",
}

DARK: Dict[str, str] = {
    "bg": "#131316",
    "bg_alt": "#1b1b1f",
    "card": "#1f1f24",
    "card_border": "#302f36",
    "header_from": _HEADER_BAR,
    "header_chip": _HEADER_CHIP,
    "header_chip_hover": "#ea580c",
    "text": "#f4f4f5",
    "text_muted": "#a1a1aa",
    "primary": "#fb923c",
    "primary_hover": "#f97316",
    "success": "#22c55e",
    "success_hover": "#16a34a",
    "warning": "#f59e0b",
    "warning_hover": "#d97706",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "neutral": "#52525b",
    "neutral_hover": "#3f3f46",
    "accent": "#eab308",
    "accent_hover": "#ca8a04",
    "log_bg": "#0f0d0a",
    "log_fg": "#f2ede4",
    "log_ok": "#4ade80",
    "log_error": "#f87171",
    "log_warning": "#fbbf24",
    "log_dryrun": "#60a5fa",
    "log_header": "#ffffff",
    "log_info": "#a1a1aa",
    "input_bg": "#1b1b1f",
    "input_border": "#302f36",
    "divider": "#302f36",
    "progress_trough": "#302f36",
    "progress_fill": "#fb923c",
}


def palette(name: ThemeName) -> Dict[str, str]:
    """Retorna a paleta do tema solicitado."""
    return DARK if name == "dark" else LIGHT


def ctk_pair(light_key: str, dark_key: str | None = None) -> tuple[str, str]:
    """Tupla (light, dark) pronta para passar em parâmetros do CustomTkinter."""
    dk = dark_key or light_key
    return (LIGHT[light_key], DARK[dk])


# ---------------------------------------------------------------------------
# Persistência de preferências do usuário (tema etc.)
# ---------------------------------------------------------------------------


def _config_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "organizador"


def _config_file() -> Path:
    return _config_dir() / "config.json"


def load_preferences() -> dict:
    """Carrega preferências persistidas (tema etc.). Retorna {} se não houver."""
    path = _config_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_preferences(prefs: dict) -> None:
    """Salva preferências no diretório de config do usuário."""
    path = _config_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def load_theme(default: ThemeName = "dark") -> ThemeName:
    value = load_preferences().get("theme", default)
    return "dark" if value == "dark" else "light"


def save_theme(name: ThemeName) -> None:
    prefs = load_preferences()
    prefs["theme"] = name
    save_preferences(prefs)
