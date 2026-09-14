#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Limpeza de disco: temporários, cache de navegadores, lixeira, downloads
parados e cache de desenvolvimento (node_modules órfãos, npm/pip, Docker).

Segue o mesmo padrão de segurança do organizer.py: toda operação tem um
modo de simulação (dry-run) que só relata o que seria removido, sem tocar
em nada, até que o chamador confirme explicitamente.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

CATEGORIES: Dict[str, str] = {
    "temp":           "Arquivos temporários (Windows + Prefetch)",
    "browser_cache":  "Cache de navegadores",
    "recycle_bin":    "Lixeira",
    "old_downloads":  "Downloads parados",
    "dev_cache":      "Cache de desenvolvimento",
}

# Removidos automaticamente sem apagar o arquivo/pasta original de verdade —
# apenas o conteúdo interno (a pasta em si permanece, o navegador recria).
_CONTENTS_ONLY = "dir_contents"


@dataclass
class CleanItem:
    """Um item candidato à remoção."""
    category: str
    label: str
    path: Path
    size_bytes: int
    kind: str = "dir"  # "dir" | "file" | "dir_contents" | "recycle_bin" | "docker_prune"
    detail: str = ""


def human_bytes(n: int) -> str:
    """Formata bytes em unidade legível (KB/MB/GB), pt-BR."""
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{value:.1f} TB"  # pragma: no cover - inalcançável


def _dir_size(path: Path) -> int:
    """Soma o tamanho de todos os arquivos dentro de path, ignorando erros."""
    total = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(path, onerror=lambda e: None):
            for name in filenames:
                try:
                    total += (Path(dirpath) / name).stat().st_size
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        return 0
    return total


def _entry_size(path: Path) -> int:
    try:
        if path.is_dir():
            return _dir_size(path)
        return path.stat().st_size
    except (OSError, PermissionError):
        return 0


# ---------------------------------------------------------------------------
# Localização de diretórios padrão
# ---------------------------------------------------------------------------


def _default_temp_dirs() -> List[Tuple[str, Path]]:
    dirs: List[Tuple[str, Path]] = []
    user_temp = os.environ.get("TEMP") or os.environ.get("TMP")
    dirs.append((
        "Temporários do usuário",
        Path(user_temp) if user_temp else (Path.home() / "AppData" / "Local" / "Temp"),
    ))
    if platform.system() == "Windows":
        windir = Path(os.environ.get("WINDIR", "C:/Windows"))
        dirs.append(("Temporários do Windows", windir / "Temp"))
        dirs.append(("Prefetch", windir / "Prefetch"))
    return dirs


def _default_browser_cache_dirs() -> List[Tuple[str, Path]]:
    if platform.system() != "Windows":
        return []
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    dirs: List[Tuple[str, Path]] = [
        ("Chrome", local / "Google" / "Chrome" / "User Data" / "Default" / "Cache"),
        ("Chrome (Code Cache)", local / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache"),
        ("Edge", local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"),
        ("Edge (Code Cache)", local / "Microsoft" / "Edge" / "User Data" / "Default" / "Code Cache"),
    ]
    ff_root = local / "Mozilla" / "Firefox" / "Profiles"
    if ff_root.exists():
        try:
            for profile in ff_root.iterdir():
                cache2 = profile / "cache2"
                if cache2.exists():
                    dirs.append((f"Firefox ({profile.name})", cache2))
        except (OSError, PermissionError):
            pass
    return dirs


def _npm_cache_dir() -> Optional[Path]:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "npm-cache"
    return Path.home() / ".npm"


def _pip_cache_dir() -> Optional[Path]:
    try:
        result = subprocess.run(
            ["pip", "cache", "dir"], capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        return Path(localappdata) / "pip" / "Cache"
    return None


def _docker_reclaimable_bytes() -> int:
    """Consulta `docker system df` e soma o espaço reclamável reportado."""
    if not shutil.which("docker"):
        return 0
    try:
        result = subprocess.run(
            ["docker", "system", "df", "--format", "{{.Reclaimable}}"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    if result.returncode != 0:
        return 0
    total = 0
    for line in result.stdout.splitlines():
        total += _parse_docker_size(line)
    return total


def _parse_docker_size(text: str) -> int:
    """Converte algo como '1.2GB (80%)' no número de bytes reclamáveis."""
    text = text.strip().split("(")[0].strip()
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    for unit in sorted(units, key=len, reverse=True):
        if text.endswith(unit):
            number = text[: -len(unit)].strip()
            try:
                return int(float(number) * units[unit])
            except ValueError:
                return 0
    return 0


def _empty_recycle_bin() -> None:
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI = 0x00000002
    SHERB_NOSOUND = 0x00000004
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    hr = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    # 0 = sucesso; -2147418113 (0x8000FFFF)/0x8000FFFF costuma significar "já vazia"
    if hr not in (0, -2147418113):
        raise OSError(f"SHEmptyRecycleBinW retornou código {hr}")


# ---------------------------------------------------------------------------
# Scanners — cada um retorna List[CleanItem], sem apagar nada
# ---------------------------------------------------------------------------


def scan_temp(temp_dirs: Optional[List[Tuple[str, Path]]] = None) -> List[CleanItem]:
    """Lista o conteúdo de %TEMP%, C:\\Windows\\Temp e Prefetch."""
    temp_dirs = temp_dirs if temp_dirs is not None else _default_temp_dirs()
    items: List[CleanItem] = []
    for label, d in temp_dirs:
        if not d.exists():
            continue
        try:
            entries = list(d.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            size = _entry_size(entry)
            items.append(CleanItem(
                category="temp",
                label=f"{label}: {entry.name}",
                path=entry,
                size_bytes=size,
                kind="dir" if entry.is_dir() else "file",
            ))
    return items


def scan_browser_cache(
    cache_dirs: Optional[List[Tuple[str, Path]]] = None,
) -> List[CleanItem]:
    """Lista pastas de cache de Chrome/Edge/Firefox (nunca cookies/histórico/senhas)."""
    cache_dirs = cache_dirs if cache_dirs is not None else _default_browser_cache_dirs()
    items: List[CleanItem] = []
    for label, d in cache_dirs:
        if not d.exists():
            continue
        size = _dir_size(d)
        if size > 0:
            items.append(CleanItem(
                category="browser_cache",
                label=f"Cache do {label}",
                path=d,
                size_bytes=size,
                kind=_CONTENTS_ONLY,
            ))
    return items


def scan_recycle_bin() -> List[CleanItem]:
    """Consulta o tamanho atual da Lixeira (Windows apenas)."""
    if platform.system() != "Windows":
        return []
    try:
        class _SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint32),
                ("i64Size", ctypes.c_int64),
                ("i64NumItems", ctypes.c_int64),
            ]

        info = _SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
        hr = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if hr != 0 or info.i64Size <= 0:
            return []
        return [CleanItem(
            category="recycle_bin",
            label=f"Lixeira ({human(info.i64NumItems)} item(ns))",
            path=Path("(Lixeira)"),
            size_bytes=info.i64Size,
            kind="recycle_bin",
        )]
    except Exception:
        return []


def scan_old_downloads(
    downloads_dir: Optional[Path] = None, days: int = 30,
) -> List[CleanItem]:
    """Lista itens em Downloads sem modificação há mais de `days` dias.

    Somente lista — a decisão de apagar downloads é sempre do usuário,
    nunca automática.
    """
    if downloads_dir is None:
        import known_folders
        downloads_dir = known_folders.downloads_folder()
    if not downloads_dir.exists():
        return []
    cutoff = time.time() - days * 86400
    items: List[CleanItem] = []
    try:
        entries = list(downloads_dir.iterdir())
    except (OSError, PermissionError):
        return []
    for entry in entries:
        try:
            mtime = entry.stat().st_mtime
        except (OSError, PermissionError):
            continue
        if mtime < cutoff:
            age_days = int((time.time() - mtime) / 86400)
            items.append(CleanItem(
                category="old_downloads",
                label=entry.name,
                path=entry,
                size_bytes=_entry_size(entry),
                kind="dir" if entry.is_dir() else "file",
                detail=f"{human(age_days)} dias sem uso",
            ))
    return items


def scan_dev_cache(
    search_roots: List[Path], stale_days: int = 60,
) -> List[CleanItem]:
    """Procura node_modules órfãos em search_roots + cache de npm/pip/Docker.

    Um node_modules é considerado "órfão" quando nenhum outro arquivo do
    projeto (irmão dele) foi modificado nos últimos `stale_days` dias —
    sinal de que o projeto está parado.
    """
    items: List[CleanItem] = []
    cutoff = time.time() - stale_days * 86400

    for root in search_roots:
        if not root.exists():
            continue
        for dirpath, dirnames, _filenames in os.walk(root, onerror=lambda e: None):
            if "node_modules" in dirnames:
                dirnames.remove("node_modules")  # não descer para dentro dele
                nm_path = Path(dirpath) / "node_modules"
                newest = _newest_sibling_mtime(Path(dirpath), exclude=nm_path)
                if newest is not None and newest < cutoff:
                    age_days = int((time.time() - newest) / 86400)
                    items.append(CleanItem(
                        category="dev_cache",
                        label=f"node_modules em {Path(dirpath).name}",
                        path=nm_path,
                        size_bytes=_dir_size(nm_path),
                        kind="dir",
                        detail=f"projeto parado há {human(age_days)} dias",
                    ))

    npm_cache = _npm_cache_dir()
    if npm_cache and npm_cache.exists():
        size = _dir_size(npm_cache)
        if size > 0:
            items.append(CleanItem(
                "dev_cache", "Cache do npm", npm_cache, size, "dir",
            ))

    pip_cache = _pip_cache_dir()
    if pip_cache and pip_cache.exists():
        size = _dir_size(pip_cache)
        if size > 0:
            items.append(CleanItem(
                "dev_cache", "Cache do pip", pip_cache, size, "dir",
            ))

    docker_bytes = _docker_reclaimable_bytes()
    if docker_bytes > 0:
        items.append(CleanItem(
            "dev_cache", "Docker (imagens/containers não usados)",
            Path("docker"), docker_bytes, "docker_prune",
        ))

    return items


def _newest_sibling_mtime(folder: Path, exclude: Path) -> Optional[float]:
    """mtime mais recente entre os itens de `folder`, exceto `exclude`."""
    newest: Optional[float] = None
    try:
        entries = list(folder.iterdir())
    except (OSError, PermissionError):
        return None
    for entry in entries:
        if entry == exclude:
            continue
        try:
            mtime = entry.stat().st_mtime
        except (OSError, PermissionError):
            continue
        if newest is None or mtime > newest:
            newest = mtime
    return newest


def human(n: int) -> str:
    """Formata número com separadores de milhares (pt-BR)."""
    return f"{n:,}".replace(",", ".")


def scan_all(
    categories: Optional[List[str]] = None,
    *,
    old_downloads_days: int = 30,
    dev_search_roots: Optional[List[Path]] = None,
    dev_stale_days: int = 60,
) -> List[CleanItem]:
    """Executa os scanners selecionados e retorna todos os CleanItem juntos."""
    categories = categories if categories is not None else list(CATEGORIES)
    items: List[CleanItem] = []
    if "temp" in categories:
        items += scan_temp()
    if "browser_cache" in categories:
        items += scan_browser_cache()
    if "recycle_bin" in categories:
        items += scan_recycle_bin()
    if "old_downloads" in categories:
        items += scan_old_downloads(days=old_downloads_days)
    if "dev_cache" in categories:
        items += scan_dev_cache(dev_search_roots or [], stale_days=dev_stale_days)
    return items


# ---------------------------------------------------------------------------
# Remoção
# ---------------------------------------------------------------------------


def clean(
    items: List[CleanItem],
    dry_run: bool,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[str, int, int, int]:
    """Remove (ou simula a remoção de) cada item.

    Returns
    -------
    Tuple (relatório, bytes_liberados, itens_removidos, erros)
    """
    logs: List[str] = []
    freed = 0
    removed = 0
    errors = 0
    total = len(items)

    for idx, item in enumerate(items):
        if progress_cb:
            progress_cb(idx + 1, total)
        try:
            if dry_run:
                logs.append(f"[DRY-RUN] REMOVER: {item.label} ({human_bytes(item.size_bytes)})")
                continue

            if item.kind == "dir":
                shutil.rmtree(item.path)
            elif item.kind == "file":
                item.path.unlink()
            elif item.kind == _CONTENTS_ONLY:
                _clear_dir_contents(item.path)
            elif item.kind == "recycle_bin":
                _empty_recycle_bin()
            elif item.kind == "docker_prune":
                subprocess.run(
                    ["docker", "system", "prune", "-f"],
                    check=True, capture_output=True, timeout=120,
                )
            else:
                raise ValueError(f"tipo de item desconhecido: {item.kind}")

            logs.append(f"[OK] REMOVIDO: {item.label} ({human_bytes(item.size_bytes)})")
            freed += item.size_bytes
            removed += 1
        except Exception as e:
            logs.append(f"[ERRO] {item.label}: {e}")
            errors += 1

    summary = (
        f"Itens processados: {human(total)} | removidos: {human(removed)} | "
        f"erros: {human(errors)} | espaço liberado: {human_bytes(freed)}"
    )
    logs.append("")
    logs.append(summary)
    return "\n".join(logs), freed, removed, errors


def _clear_dir_contents(folder: Path) -> None:
    """Apaga o conteúdo de uma pasta de cache, mantendo a pasta em si
    (o navegador espera que ela continue existindo)."""
    errors: List[str] = []
    try:
        children = list(folder.iterdir())
    except (OSError, PermissionError) as e:
        raise OSError(f"não foi possível listar {folder}: {e}") from e
    for child in children:
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except (OSError, PermissionError):
            # arquivo em uso pelo navegador — segue para o próximo
            errors.append(child.name)
    if errors and len(errors) == len(children):
        raise OSError("todos os arquivos estavam em uso (feche o navegador e tente de novo)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(
        description="Limpeza de disco: temporários, cache de navegadores, "
                     "lixeira, downloads parados e cache de desenvolvimento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:

  # Analisar tudo, sem apagar nada (padrão)
  python cleaner.py

  # Analisar só temporários e cache de navegador
  python cleaner.py --categories temp,browser_cache

  # Aplicar de verdade (pede confirmação, a menos que --yes seja usado)
  python cleaner.py --apply

  # Incluir cache de dev, procurando node_modules órfãos em D:/Projetos
  python cleaner.py --categories dev_cache --dev-search-root D:/Projetos --apply
        """,
    )
    ap.add_argument("--categories", default=",".join(CATEGORIES),
                     help=f"Categorias separadas por vírgula (padrão: todas). "
                          f"Opções: {', '.join(CATEGORIES)}")
    ap.add_argument("--apply", action="store_true",
                     help="Remove de verdade. Sem essa flag, só simula (dry-run).")
    ap.add_argument("--yes", action="store_true",
                     help="Não pede confirmação antes de aplicar")
    ap.add_argument("--old-downloads-days", type=int, default=30,
                     help="Idade mínima (dias) para listar em Downloads parados")
    ap.add_argument("--dev-search-root", action="append", default=[],
                     help="Pasta onde procurar node_modules órfãos (repetível)")
    ap.add_argument("--dev-stale-days", type=int, default=60,
                     help="Dias sem atividade para considerar node_modules órfão")

    args = ap.parse_args()
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    unknown = set(categories) - set(CATEGORIES)
    if unknown:
        print(f"[ERRO] Categoria(s) desconhecida(s): {', '.join(sorted(unknown))}")
        sys.exit(1)

    dev_roots = [Path(p).expanduser().resolve() for p in args.dev_search_root]
    if "dev_cache" in categories and not dev_roots:
        print("[AVISO] dev_cache selecionado sem --dev-search-root — "
              "só o cache de npm/pip/Docker será analisado (sem busca de node_modules).")

    print("Analisando...")
    items = scan_all(
        categories,
        old_downloads_days=args.old_downloads_days,
        dev_search_roots=dev_roots,
        dev_stale_days=args.dev_stale_days,
    )

    if not items:
        print("Nada encontrado para limpar. :)")
        return

    total_size = sum(i.size_bytes for i in items)
    print("-" * 60)
    for item in items:
        detail = f"  [{item.detail}]" if item.detail else ""
        print(f"{CATEGORIES[item.category]:<28} {human_bytes(item.size_bytes):>10}  {item.label}{detail}")
    print("-" * 60)
    print(f"Total: {len(items)} item(ns), {human_bytes(total_size)}")

    if not args.apply:
        print("\n*** MODO ANÁLISE — nada foi removido. Use --apply para remover. ***")
        return

    if not args.yes:
        resp = input(f"\nConfirma remover {human_bytes(total_size)}? [s/N] ").strip().lower()
        if resp not in ("s", "sim", "y", "yes"):
            print("Cancelado.")
            return

    report, freed, removed, errors = clean(items, dry_run=False)
    print(report)
    sys.exit(2 if errors else 0)


if __name__ == "__main__":  # pragma: no cover
    main()
