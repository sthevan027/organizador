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

LIGHT: Dict[str, str] = {
    "bg": "#f3f4f6",
    "bg_alt": "#e5e7eb",
    "card": "#ffffff",
    "card_border": "#e5e7eb",
    "header_from": "#6366f1",
    "header_to": "#8b5cf6",
    "text": "#111827",
    "text_muted": "#6b7280",
    "text_on_primary": "#ffffff",
    "primary": "#6366f1",
    "primary_hover": "#4f46e5",
    "success": "#10b981",
    "success_hover": "#059669",
    "warning": "#f59e0b",
    "warning_hover": "#d97706",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "neutral": "#6b7280",
    "neutral_hover": "#4b5563",
    "accent": "#8b5cf6",
    "accent_hover": "#7c3aed",
    "log_bg": "#0f172a",
    "log_fg": "#e2e8f0",
    "log_ok": "#34d399",
    "log_error": "#f87171",
    "log_warning": "#fbbf24",
    "log_dryrun": "#60a5fa",
    "log_header": "#ffffff",
    "log_info": "#94a3b8",
    "input_bg": "#ffffff",
    "input_border": "#d1d5db",
    "input_focus": "#6366f1",
    "divider": "#e5e7eb",
    "progress_trough": "#e5e7eb",
    "progress_fill": "#6366f1",
}

DARK: Dict[str, str] = {
    "bg": "#0f1117",
    "bg_alt": "#161923",
    "card": "#1f2430",
    "card_border": "#2a2f3d",
    "header_from": "#4f46e5",
    "header_to": "#7c3aed",
    "text": "#f3f4f6",
    "text_muted": "#9ca3af",
    "text_on_primary": "#ffffff",
    "primary": "#818cf8",
    "primary_hover": "#6366f1",
    "success": "#10b981",
    "success_hover": "#059669",
    "warning": "#f59e0b",
    "warning_hover": "#d97706",
    "danger": "#ef4444",
    "danger_hover": "#dc2626",
    "neutral": "#4b5563",
    "neutral_hover": "#374151",
    "accent": "#a78bfa",
    "accent_hover": "#8b5cf6",
    "log_bg": "#0b0e15",
    "log_fg": "#e2e8f0",
    "log_ok": "#34d399",
    "log_error": "#f87171",
    "log_warning": "#fbbf24",
    "log_dryrun": "#60a5fa",
    "log_header": "#ffffff",
    "log_info": "#94a3b8",
    "input_bg": "#161923",
    "input_border": "#2a2f3d",
    "input_focus": "#818cf8",
    "divider": "#2a2f3d",
    "progress_trough": "#2a2f3d",
    "progress_fill": "#818cf8",
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
