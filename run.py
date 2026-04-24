#!/usr/bin/env python3
"""Abre a interface gráfica do Organizador de Arquivos."""
import sys

try:
    import tkinter  # noqa: F401 — verifica disponibilidade antes de importar a GUI
    from organizer_gui import main
    main()
except ImportError:
    print("Interface gráfica não disponível (tkinter ausente).")
    print("Use a linha de comando:")
    print("  python organizer.py --help")
    sys.exit(1)
