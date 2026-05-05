#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resolução de pastas conhecidas do sistema operacional.

Em Windows obtém os caminhos reais via SHGetKnownFolderPath (ctypes),
respeitando redirecionamentos do OneDrive e perfis personalizados.
Em outros sistemas usa fallback por Path.home().
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, FrozenSet, Optional


# ---------------------------------------------------------------------------
# FOLDERIDs do Windows Shell
# ---------------------------------------------------------------------------

_FOLDERID: Dict[str, str] = {
    "Documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "Pictures":  "33E28130-4E1E-4676-835A-98395C3BC3BB",
    "Videos":    "18989B1D-99B5-455B-841C-AB7C74E4DDFC",
    "Music":     "4BD8D571-6D19-48D3-BE97-422220080E43",
}

# Nomes em inglês usados como fallback (Path.home() / nome)
_ENGLISH_FALLBACKS: Dict[str, str] = {
    "Documents": "Documents",
    "Pictures":  "Pictures",
    "Videos":    "Videos",
    "Music":     "Music",
}

# Nomes em português como segundo fallback (quando não existe a pasta em inglês)
_PTBR_FALLBACKS: Dict[str, str] = {
    "Documents": "Documentos",
    "Pictures":  "Imagens",
    "Videos":    "Vídeos",
    "Music":     "Música",
}


def _win_known_folder(folder_key: str) -> Optional[Path]:
    """Chama SHGetKnownFolderPath e retorna o Path real ou None."""
    if sys.platform != "win32":
        return None
    guid_str = _FOLDERID.get(folder_key)
    if not guid_str:
        return None
    try:
        import ctypes
        import ctypes.wintypes

        parts = guid_str.split("-")

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        guid = _GUID()
        guid.Data1 = int(parts[0], 16)
        guid.Data2 = int(parts[1], 16)
        guid.Data3 = int(parts[2], 16)
        data4 = bytes.fromhex(parts[3] + parts[4])
        guid.Data4 = (ctypes.c_ubyte * 8)(*data4)

        buf = ctypes.c_wchar_p()
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(buf)
        )
        if hr == 0:
            result = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return result
    except Exception:
        pass
    return None


def _get_system_folder(folder_key: str) -> Path:
    """Retorna o Path do sistema para um folder_key, criando se necessário."""
    win_path = _win_known_folder(folder_key)
    if win_path and win_path.exists():
        return win_path

    # Fallback em inglês
    en_name = _ENGLISH_FALLBACKS.get(folder_key, folder_key)
    candidate = Path.home() / en_name
    if candidate.exists():
        return candidate

    # Fallback em português
    ptbr_name = _PTBR_FALLBACKS.get(folder_key, folder_key)
    candidate_ptbr = Path.home() / ptbr_name
    if candidate_ptbr.exists():
        return candidate_ptbr

    # Cria a pasta em inglês como caminho definitivo
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


# ---------------------------------------------------------------------------
# Tabela de mapeamento categoria → folder_key do sistema
# ---------------------------------------------------------------------------

# Categorias mapeadas diretamente para uma biblioteca do sistema
_DIRECT_MAP: Dict[str, str] = {
    "Imagens":    "Pictures",
    "Documentos": "Documents",
    "Vídeos":     "Videos",
    "Áudio":      "Music",
    "Compactados": "Documents",   # raiz de Documentos
}

# Categorias que ficam como subpasta dentro da origem (não vão para sistema)
PROGRAMAS_IN_SOURCE: FrozenSet[str] = frozenset({"Programas"})


def is_available() -> bool:
    """Retorna True se a plataforma suporta o modo bibliotecas."""
    return sys.platform == "win32"


def resolve_category_path(
    category: str,
    source: Path,
    dest_root: Path,
    _overrides: Optional[Dict[str, Path]] = None,
) -> Path:
    """Resolve o diretório de destino de uma categoria no modo bibliotecas.

    Parameters
    ----------
    category:   Nome da categoria (ex.: "Imagens", "Programas")
    source:     Pasta de origem — usada para a categoria Programas
    dest_root:  Pasta raiz do modo normal — fallback para categorias sem mapeamento
    _overrides: Dict categoria → Path exclusivo para testes automatizados
    """
    if _overrides and category in _overrides:
        return _overrides[category]

    if category in PROGRAMAS_IN_SOURCE:
        return source / "Programas"

    if category in _DIRECT_MAP:
        return _get_system_folder(_DIRECT_MAP[category])

    # Categoria personalizada (JSON) ou desconhecida → Documentos/<categoria>
    documents = _get_system_folder("Documents")
    return documents / category
