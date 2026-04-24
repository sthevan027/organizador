#!/usr/bin/env python3
"""Abre a interface gráfica do Organizador de Arquivos.

Garante que o ícone do aplicativo exista antes de abrir a GUI (gera
automaticamente na primeira execução).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ICON_PATH = PROJECT_ROOT / "assets" / "organizer.ico"


def _ensure_icon() -> None:
    if ICON_PATH.exists():
        return
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.gen_icon import generate
        generate()
    except Exception:
        # Falha silenciosa: a GUI roda sem ícone se algo der errado.
        pass


def main() -> int:
    try:
        import tkinter  # noqa: F401 — verifica disponibilidade
    except ImportError:
        print("Interface gráfica não disponível (tkinter ausente).")
        print("Use a linha de comando:  python organizer.py --help")
        return 1

    _ensure_icon()

    try:
        from organizer_gui import main as gui_main
    except SystemExit as e:
        print(str(e))
        return 1
    except ImportError as e:
        print(f"Erro ao carregar a GUI: {e}")
        print("Tente:  pip install -r requirements.txt")
        return 1

    gui_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
