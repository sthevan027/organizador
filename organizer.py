#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import shutil
import sys
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

DEFAULT_MAP = {
    "Imagens":     [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic"],
    "Documentos":  [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".csv", ".xls", ".xlsx", ".ppt", ".pptx", ".md"],
    "Compactados": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "Vídeos":      [".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm"],
    "Áudio":       [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Programas":   [".exe", ".msi", ".dmg", ".pkg", ".apk"],
    "Código":      [".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".php", ".go", ".rb", ".rs", ".sh", ".ps1"],
    "Design":      [".psd", ".ai", ".xd", ".fig", ".sketch", ".eps"],
    "Fontes":      [".ttf", ".otf", ".woff", ".woff2"],
}

FOLDER_KEYWORDS = {
    "Imagens":     ["foto", "image", "img", "picture", "screenshot", "print", "captura"],
    "Documentos":  ["doc", "document", "texto", "pdf", "word", "excel", "powerpoint"],
    "Vídeos":      ["video", "movie", "film", "mp4", "avi", "mkv", "youtube"],
    "Áudio":       ["audio", "music", "song", "mp3", "sound", "música"],
    "Programas":   ["program", "software", "app", "install", "setup", "exe"],
    "Compactados": ["zip", "rar", "7z", "compact", "archive", "backup"],
    "Código":      ["code", "programming", "dev", "project", "source", "github"],
    "Design":      ["design", "art", "creative", "photoshop", "illustrator"],
}

_config_cache: Dict[str, Dict[str, List[str]]] = {}


def load_map(config_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """Carrega o mapa de extensões do arquivo de configuração ou usa o padrão."""
    if config_path is None:
        return DEFAULT_MAP

    config_key = str(config_path)
    if config_key in _config_cache:
        return _config_cache[config_key]

    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            normalized = {
                k: [e.lower() if e.startswith(".") else f".{e.lower()}" for e in v]
                for k, v in data.items()
            }
            _config_cache[config_key] = normalized
            return normalized
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar configuração: {e}")
            return DEFAULT_MAP

    return DEFAULT_MAP


def guess_folder(ext: str, ext_map: Dict[str, List[str]], unknown_name: str) -> str:
    """Determina em qual pasta o arquivo deve ser colocado baseado na extensão."""
    ext = ext.lower()
    for folder, exts in ext_map.items():
        if ext in exts:
            return folder
    return unknown_name


def guess_folder_type(folder_name: str, unknown_name: str) -> str:
    """Determina o tipo de pasta baseado em palavras-chave no nome."""
    folder_lower = folder_name.lower()
    for category, keywords in FOLDER_KEYWORDS.items():
        for keyword in keywords:
            if keyword in folder_lower:
                return category
    return unknown_name


def analyze_folder_content(folder_path: Path, ext_map: Dict[str, List[str]], max_files: int = 50) -> str:
    """Analisa o conteúdo de uma pasta para determinar sua categoria predominante."""
    file_types: Dict[str, int] = {}
    file_count = 0

    try:
        for item_name in os.listdir(folder_path):
            if file_count >= max_files:
                break
            item_path = folder_path / item_name
            if item_path.is_file():
                category = guess_folder(item_path.suffix.lower(), ext_map, "Outros")
                file_types[category] = file_types.get(category, 0) + 1
                file_count += 1
    except (PermissionError, OSError):
        return "Outros"

    if not file_types:
        return "Outros"

    return max(file_types, key=file_types.get)


def human(n: int) -> str:
    """Formata número com separadores de milhares (pt-BR)."""
    return f"{n:,}".replace(",", ".")


def organize(
    source: Path,
    dest_root: Path,
    mode: str,
    dry_run: bool,
    delete_empty: bool,
    unknown_name: str,
    ext_map: Dict[str, List[str]],
    log_path: Optional[Path] = None,
) -> Tuple[str, int, int, int]:
    """
    Organiza arquivos da pasta source para dest_root baseado nas extensões.

    Returns:
        Tuple (relatório, itens_organizados, itens_pulados, erros)
    """
    moved = skipped = errors = 0
    logs: List[str] = []

    # Rastreia (original, destino_real) para verificação antes de deletar
    files_to_remove: List[Tuple[Path, Path]] = []
    folders_to_remove: List[Tuple[Path, Path]] = []

    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"Pasta de origem inválida: {source}")

    dest_root.mkdir(parents=True, exist_ok=True)

    # Snapshot dos itens antes de criar subpastas de destino
    source_items = list(source.iterdir())
    category_names = set(ext_map.keys()) | {unknown_name}

    # --- Primeira passada: copia tudo ---
    for p in source_items:
        if p.is_dir():
            if p.name in category_names:
                continue  # não mover pastas de categoria para dentro de si mesmas

            try:
                target_folder = guess_folder_type(p.name, unknown_name)
                if target_folder == unknown_name:
                    target_folder = analyze_folder_content(p, ext_map)

                target_dir = dest_root / target_folder
                target_dir.mkdir(parents=True, exist_ok=True)

                target_path = target_dir / p.name
                counter = 1
                while target_path.exists() and target_path.resolve() != p.resolve():
                    target_path = target_dir / f"{p.name} ({counter})"
                    counter += 1

                if dry_run:
                    action = "COPIAR" if mode == "copy" else "MOVER"
                    logs.append(f"[DRY-RUN] {action} PASTA: {p.name} -> {target_path}")
                else:
                    shutil.copytree(p, target_path, dirs_exist_ok=True)
                    logs.append(f"[OK] COPIAR PASTA: {p.name} -> {target_path}")
                    moved += 1
                    if mode == "move":
                        folders_to_remove.append((p, target_path))

            except Exception as e:
                logs.append(f"[ERRO] PASTA {p.name}: {e}")
                errors += 1
            continue

        if p.name.startswith(".") and p.suffix == "":  # arquivos ocultos sem extensão
            skipped += 1
            continue

        target_folder = guess_folder(p.suffix, ext_map, unknown_name)
        target_dir = dest_root / target_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / p.name
        counter = 1
        while target_path.exists() and target_path.resolve() != p.resolve():
            target_path = target_dir / f"{p.stem} ({counter}){p.suffix}"
            counter += 1

        try:
            if dry_run:
                action = "COPIAR" if mode == "copy" else "MOVER"
                logs.append(f"[DRY-RUN] {action}: {p.name} -> {target_path}")
            else:
                shutil.copy2(p, target_path)
                logs.append(f"[OK] COPIAR: {p.name} -> {target_path}")
                moved += 1
                if mode == "move":
                    files_to_remove.append((p, target_path))
        except Exception as e:
            logs.append(f"[ERRO] {p.name}: {e}")
            errors += 1

    # --- Segunda passada: verifica e remove originais (modo move) ---
    if mode == "move" and not dry_run and (files_to_remove or folders_to_remove):
        if errors > 0:
            logs.append("")
            logs.append("[AVISO] Houve erros na organização. Originais mantidos por segurança.")
        else:
            logs.append("")
            logs.append("Verificando organização...")
            all_verified = True

            for original, target in files_to_remove:
                if not target.exists():
                    logs.append(f"[ERRO] Arquivo não encontrado no destino: {target}")
                    all_verified = False
                elif original.stat().st_size != target.stat().st_size:
                    logs.append(f"[ERRO] Tamanhos divergem: {original.name}")
                    all_verified = False

            for original, target in folders_to_remove:
                if not target.exists():
                    logs.append(f"[ERRO] Pasta não encontrada no destino: {target}")
                    all_verified = False

            if all_verified:
                logs.append("Verificação OK. Removendo originais...")
                for original, _ in files_to_remove:
                    try:
                        original.unlink()
                        logs.append(f"[OK] REMOVER: {original.name}")
                    except Exception as e:
                        logs.append(f"[ERRO] Falha ao remover {original.name}: {e}")
                        errors += 1

                for original, _ in folders_to_remove:
                    try:
                        shutil.rmtree(original)
                        logs.append(f"[OK] REMOVER PASTA: {original.name}")
                    except Exception as e:
                        logs.append(f"[ERRO] Falha ao remover pasta {original.name}: {e}")
                        errors += 1
            else:
                logs.append("[AVISO] Verificação falhou. Originais mantidos por segurança.")
                errors += 1

    # Remove subpastas vazias se solicitado
    if delete_empty and not dry_run:
        for d in source.iterdir():
            if d.is_dir():
                try:
                    next(d.iterdir())
                except StopIteration:
                    d.rmdir()

    summary = (
        f"Processados: {human(moved + skipped + errors)} | "
        f"organizados: {human(moved)} | "
        f"pulados: {human(skipped)} | "
        f"erros: {human(errors)}"
    )
    logs.append("")
    logs.append(summary)

    output = "\n".join(logs)

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d_%H-%M-%S")
        log_file = log_path.parent / f"{log_path.stem}_{ts}{log_path.suffix}"
        with log_file.open("w", encoding="utf-8") as f:
            f.write(output)
        output += f"\nLog salvo em: {log_file}"

    return output, moved, skipped, errors


def main():
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(
        description="Organizador automático de arquivos por extensão",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:

  # Organizar Downloads movendo arquivos
  python organizer.py --source ~/Downloads --mode move

  # Testar sem alterar nada (recomendado primeiro)
  python organizer.py --source ~/Downloads --dry-run

  # Copiar para pasta separada
  python organizer.py --source ~/Downloads --dest ~/Downloads/Organizado

  # Usar configuração personalizada de extensões
  python organizer.py --source ~/Downloads --config config_extensoes.json
        """,
    )
    ap.add_argument("--source", "-s", required=True,
                    help="Pasta a organizar (ex.: ~/Downloads)")
    ap.add_argument("--dest", "-d",
                    help="Pasta de destino (padrão: a própria --source)")
    ap.add_argument("--mode", choices=["move", "copy"], default="move",
                    help="mover (remove originais) ou copiar (padrão: move)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Simula as operações sem alterar nenhum arquivo")
    ap.add_argument("--delete-empty", action="store_true",
                    help="Remove subpastas vazias após organizar")
    ap.add_argument("--unknown-name", default="Outros",
                    help="Nome da pasta para extensões não mapeadas (padrão: Outros)")
    ap.add_argument("--config",
                    help="Arquivo JSON com mapeamento extensão -> pasta")
    ap.add_argument("--log",
                    help="Caminho do arquivo de log (ex.: logs/organizer.log)")

    args = ap.parse_args()

    source = Path(args.source).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve() if args.dest else source
    config_path = Path(args.config).expanduser() if args.config else None
    log_path = Path(args.log).expanduser() if args.log else None

    try:
        ext_map = load_map(config_path)

        print(f"Organizando: {source}")
        print(f"Destino:     {dest}")
        print(f"Modo:        {'Cópia' if args.mode == 'copy' else 'Mover'}")
        if args.dry_run:
            print("*** MODO TESTE — nenhum arquivo será alterado ***")
        print("-" * 50)

        report, moved, skipped, errors = organize(
            source, dest, args.mode, args.dry_run, args.delete_empty,
            args.unknown_name, ext_map, log_path
        )

        print(report)

        if errors > 0:
            print(f"\n[AVISO] {errors} erro(s) encontrado(s).")
            sys.exit(2)
        elif moved > 0:
            print(f"\n[SUCESSO] {moved} item(ns) organizados.")
        else:
            print("\n[INFO] Nenhum item foi processado.")

    except Exception as e:
        print(f"[ERRO] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
