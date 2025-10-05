#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import shutil
import sys
import json
import time
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional

DEFAULT_MAP = {
    "Imagens": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic"],
    "Documentos": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".csv", ".xls", ".xlsx", ".ppt", ".pptx", ".md"],
    "Compactados": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "Vídeos": [".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm"],
    "Áudio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Programas": [".exe", ".msi", ".dmg", ".pkg", ".apk"],
    "Código": [".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".php", ".go", ".rb", ".rs", ".sh", ".ps1"],
    "Design": [".psd", ".ai", ".xd", ".fig", ".sketch", ".eps"],
    "Fontes": [".ttf", ".otf", ".woff", ".woff2"]
}

# Mapeamento de palavras-chave para categorias de pastas
FOLDER_KEYWORDS = {
    "Imagens": ["foto", "image", "img", "picture", "screenshot", "print", "captura"],
    "Documentos": ["doc", "document", "texto", "pdf", "word", "excel", "powerpoint"],
    "Vídeos": ["video", "movie", "film", "mp4", "avi", "mkv", "youtube"],
    "Áudio": ["audio", "music", "song", "mp3", "sound", "música"],
    "Programas": ["program", "software", "app", "install", "setup", "exe"],
    "Compactados": ["zip", "rar", "7z", "compact", "archive", "backup"],
    "Código": ["code", "programming", "dev", "project", "source", "github"],
    "Design": ["design", "art", "creative", "photoshop", "illustrator"]
}

# Cache para configurações
_config_cache: Dict[str, Dict[str, List[str]]] = {}


def load_map(config_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """Carrega o mapa de extensões do arquivo de configuração ou usa o padrão com cache."""
    if config_path is None:
        return DEFAULT_MAP
    
    config_key = str(config_path)
    
    # Verifica cache primeiro
    if config_key in _config_cache:
        return _config_cache[config_key]
    
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # normaliza extensões para minúsculas e com ponto
            normalized_data = {k: [e.lower() if e.startswith(".") else f".{e.lower()}" for e in v] for k, v in data.items()}
            # Armazena no cache
            _config_cache[config_key] = normalized_data
            return normalized_data
        except (json.JSONDecodeError, IOError) as e:
            print(f"Erro ao carregar configuração: {e}")
            return DEFAULT_MAP
    
    return DEFAULT_MAP


def guess_folder(ext: str, ext_map: dict[str, list[str]], unknown_name: str):
    """Determina em qual pasta o arquivo deve ser colocado baseado na extensão."""
    ext = ext.lower()
    for folder, exts in ext_map.items():
        if ext in exts:
            return folder
    return unknown_name


def guess_folder_type(folder_name: str, unknown_name: str):
    """Determina o tipo de pasta baseado no nome."""
    folder_lower = folder_name.lower()
    
    # Verifica palavras-chave no nome da pasta
    for category, keywords in FOLDER_KEYWORDS.items():
        for keyword in keywords:
            if keyword in folder_lower:
                return category
    
    return unknown_name


def analyze_folder_content(folder_path: Path, ext_map: Dict[str, List[str]], max_files: int = 50) -> str:
    """Analisa o conteúdo de uma pasta para determinar sua categoria (otimizado)."""
    file_types = {}
    file_count = 0
    
    try:
        # Usa os.listdir() que é mais rápido que Path.iterdir() para muitos arquivos
        items = os.listdir(folder_path)
        
        for item_name in items:
            if file_count >= max_files:  # Limita análise para performance
                break
                
            item_path = folder_path / item_name
            if item_path.is_file():
                ext = item_path.suffix.lower()
                category = guess_folder(ext, ext_map, "Outros")
                file_types[category] = file_types.get(category, 0) + 1
                file_count += 1
                
    except (PermissionError, OSError):
        return "Outros"
    
    if not file_types:
        return "Outros"
    
    # Retorna a categoria com mais arquivos
    return max(file_types, key=file_types.get)


def human(n: int) -> str:
    """Formata números com separadores de milhares."""
    return f"{n:,}".replace(",", ".")


def process_file(file_path: Path, target_path: Path, mode: str, dry_run: bool) -> Tuple[bool, str]:
    """Processa um arquivo individual (para uso em threads)."""
    try:
        if dry_run:
            action = "COPIAR" if mode == "copy" else "MOVER"
            return True, f"[DRY-RUN] {action}: {file_path.name} -> {target_path}"
        else:
            # Sempre copia primeiro
            shutil.copy2(file_path, target_path)
            return True, f"[OK] COPIAR: {file_path.name} -> {target_path}"
    except Exception as e:
        return False, f"[ERRO] {file_path.name}: {e}"


def process_folder(folder_path: Path, target_path: Path, mode: str, dry_run: bool) -> Tuple[bool, str]:
    """Processa uma pasta individual (para uso em threads)."""
    try:
        if dry_run:
            action = "COPIAR" if mode == "copy" else "MOVER"
            return True, f"[DRY-RUN] {action} PASTA: {folder_path.name} -> {target_path}"
        else:
            # Sempre copia primeiro
            shutil.copytree(folder_path, target_path, dirs_exist_ok=True)
            return True, f"[OK] COPIAR PASTA: {folder_path.name} -> {target_path}"
    except Exception as e:
        return False, f"[ERRO] PASTA {folder_path.name}: {e}"


def organize(
    source: Path,
    dest_root: Path,
    mode: str,
    dry_run: bool,
    delete_empty: bool,
    unknown_name: str,
    ext_map: Dict[str, List[str]],
    log_path: Optional[Path] = None,
    max_workers: int = 4
) -> Tuple[str, int, int, int]:
    """
    Organiza arquivos da pasta source para dest_root baseado nas extensões.
    
    Args:
        source: Pasta de origem
        dest_root: Pasta de destino
        mode: 'move' ou 'copy'
        dry_run: Se True, apenas simula as operações
        delete_empty: Se True, remove subpastas vazias
        unknown_name: Nome da pasta para extensões não mapeadas
        ext_map: Mapa de extensões para pastas
        log_path: Caminho para salvar o log
    
    Returns:
        Tuple com (relatório, arquivos_movidos, arquivos_pulados, erros)
    """
    moved = skipped = errors = 0
    logs = []
    files_to_remove = []  # Lista de arquivos que serão removidos após verificação
    folders_to_remove = []  # Lista de pastas que serão removidas após verificação

    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"Pasta de origem inválida: {source}")

    dest_root.mkdir(parents=True, exist_ok=True)

    # Cria um snapshot dos itens da pasta de origem para não incluir
    # diretórios de destino que forem criados durante a execução
    source_items = list(source.iterdir())

    # Nomes de pastas de categorias (e desconhecidos) para ignorar
    category_names = set(ext_map.keys()) | {unknown_name}

    # Primeira passada: organiza (copia) todos os arquivos
    for p in source_items:
        if p.is_dir():
            # Pula pastas que já são categorias de destino (evita recursão)
            if p.name in category_names:
                continue
                
            # Processa pastas
            try:
                # Tenta determinar categoria pelo nome primeiro
                target_folder = guess_folder_type(p.name, unknown_name)
                
                # Se não conseguiu pelo nome, analisa o conteúdo
                if target_folder == unknown_name:
                    target_folder = analyze_folder_content(p, ext_map)
                
                target_dir = dest_root / target_folder
                target_dir.mkdir(parents=True, exist_ok=True)

                target_path = target_dir / p.name
                # evita sobrescrever: acrescenta contador
                counter = 1
                while target_path.exists() and target_path.resolve() != p.resolve():
                    target_path = target_dir / f"{p.name} ({counter})"
                    counter += 1

                if dry_run:
                    action = "COPIAR" if mode == "copy" else "MOVER"
                    logs.append(f"[DRY-RUN] {action} PASTA: {p.name} -> {target_path}")
                else:
                    # Sempre copia primeiro
                    shutil.copytree(p, target_path, dirs_exist_ok=True)
                    logs.append(f"[OK] COPIAR PASTA: {p.name} -> {target_path}")
                    moved += 1
                    
                    # Se for modo move, adiciona à lista para remoção posterior
                    if mode == "move":
                        folders_to_remove.append(p)
                        
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
        # evita sobrescrever: acrescenta contador
        counter = 1
        while target_path.exists() and target_path.resolve() != p.resolve():
            target_path = target_dir / f"{p.stem} ({counter}){p.suffix}"
            counter += 1

        try:
            if dry_run:
                action = "COPIAR" if mode == "copy" else "MOVER"
                logs.append(f"[DRY-RUN] {action}: {p.name} -> {target_path}")
            else:
                # Sempre copia primeiro
                shutil.copy2(p, target_path)
                logs.append(f"[OK] COPIAR: {p.name} -> {target_path}")
                moved += 1
                
                # Se for modo move, adiciona à lista para remoção posterior
                if mode == "move":
                    files_to_remove.append(p)
                    
        except Exception as e:
            logs.append(f"[ERRO] {p.name}: {e}")
            errors += 1

    # Segunda passada: verifica se tudo foi organizado com sucesso e remove originais
    if mode == "move" and not dry_run and (files_to_remove or folders_to_remove) and errors == 0:
        logs.append("")
        logs.append("Verificando organização...")
        
        # Verifica se todos os arquivos foram copiados corretamente
        all_verified = True
        
        # Verifica arquivos
        for original_file in files_to_remove:
            target_folder = guess_folder(original_file.suffix, ext_map, unknown_name)
            target_dir = dest_root / target_folder
            target_path = target_dir / original_file.name
            
            # Verifica se o arquivo existe no destino
            if not target_path.exists():
                logs.append(f"[ERRO] Arquivo não encontrado no destino: {target_path}")
                all_verified = False
                continue
                
            # Verifica se os tamanhos são iguais
            if original_file.stat().st_size != target_path.stat().st_size:
                logs.append(f"[ERRO] Tamanhos diferentes: {original_file.name}")
                all_verified = False
                continue
        
        # Verifica pastas
        for original_folder in folders_to_remove:
            target_folder = guess_folder_type(original_folder.name, unknown_name)
            if target_folder == unknown_name:
                target_folder = analyze_folder_content(original_folder, ext_map)
            
            target_dir = dest_root / target_folder
            target_path = target_dir / original_folder.name
            
            # Verifica se a pasta existe no destino
            if not target_path.exists():
                logs.append(f"[ERRO] Pasta não encontrada no destino: {target_path}")
                all_verified = False
                continue
        
        if all_verified:
            logs.append("Verificação concluída com sucesso. Removendo originais...")
            
            # Remove os arquivos originais
            for original_file in files_to_remove:
                try:
                    original_file.unlink()
                    logs.append(f"[OK] REMOVER: {original_file.name}")
                except Exception as e:
                    logs.append(f"[ERRO] Falha ao remover {original_file.name}: {e}")
                    errors += 1
            
            # Remove as pastas originais
            for original_folder in folders_to_remove:
                try:
                    shutil.rmtree(original_folder)
                    logs.append(f"[OK] REMOVER PASTA: {original_folder.name}")
                except Exception as e:
                    logs.append(f"[ERRO] Falha ao remover pasta {original_folder.name}: {e}")
                    errors += 1
        else:
            logs.append("[AVISO] Verificação falhou. Originais mantidos por segurança.")
            errors += 1

    # Remove subpastas vazias se solicitado
    if delete_empty:
        for d in source.iterdir():
            if d.is_dir():
                try:
                    next(d.iterdir())
                except StopIteration:
                    if not dry_run:
                        d.rmdir()

    # Gera relatório
    summary = f"Arquivos processados: {human(moved + skipped + errors)} | organizados: {human(moved)} | pulados: {human(skipped)} | erros: {human(errors)}"
    logs.append("")
    logs.append(summary)

    output = "\n".join(logs)
    
    # Salva log se especificado
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d_%H-%M-%S")
        log_file = log_path.parent / f"{log_path.stem}_{ts}{log_path.suffix}"
        with log_file.open("w", encoding="utf-8") as f:
            f.write(output)
        logs.append(f"Log salvo em: {log_file}")
    
    return output, moved, skipped, errors


def main():
    """Função principal que processa argumentos da linha de comando."""
    ap = argparse.ArgumentParser(
        description="Organizador automático de arquivos por extensão",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Organizar pasta Downloads movendo arquivos
  python organizer.py --source "C:/Users/SEU_USUARIO/Downloads" --mode move --log logs/organizer.log

  # Testar sem alterar nada (dry-run)
  python organizer.py --source "~/Downloads" --dry-run

  # Usar destino diferente e apagar subpastas vazias
  python organizer.py --source "~/Downloads" --dest "~/Downloads/Organizado" --delete-empty

  # Usar configuração personalizada
  python organizer.py --source "~/Downloads" --config config_extensoes.json
        """
    )
    
    ap.add_argument("--source", "-s", required=True, 
                   help="Pasta a organizar (ex.: C:/Users/Voce/Downloads)")
    ap.add_argument("--dest", "-d", 
                   help="Raiz de destino (default: a própria pasta source)")
    ap.add_argument("--mode", choices=["move", "copy"], default="move", 
                   help="Mover ou copiar arquivos (default: move)")
    ap.add_argument("--dry-run", action="store_true", 
                   help="Não altera nada, só mostra o que faria")
    ap.add_argument("--delete-empty", action="store_true", 
                   help="Apaga subpastas vazias diretas em --source")
    ap.add_argument("--unknown-name", default="Outros", 
                   help="Nome da pasta para extensões não mapeadas (default: Outros)")
    ap.add_argument("--config", 
                   help="Arquivo JSON com mapa de extensões -> pastas")
    ap.add_argument("--log", 
                   help="Arquivo de log (ex.: logs/organizer.log)")
    
    args = ap.parse_args()

    # Processa argumentos
    source = Path(args.source).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve() if args.dest else source
    config_path = Path(args.config).expanduser() if args.config else None
    log_path = Path(args.log).expanduser() if args.log else None

    try:
        ext_map = load_map(config_path)
        
        print(f"Organizando arquivos de: {source}")
        print(f"Destino: {dest}")
        print(f"Modo: {'Cópia' if args.mode == 'copy' else 'Movimento'}")
        print(f"Dry-run: {'Sim' if args.dry_run else 'Não'}")
        print("-" * 50)

        report, moved, skipped, errors = organize(
            source, dest, args.mode, args.dry_run, args.delete_empty,
            args.unknown_name, ext_map, log_path
        )
        
        print(report)
        
        if errors > 0:
            print(f"\n[AVISO] {errors} erro(s) encontrado(s). Verifique o log para detalhes.")
            sys.exit(2)
        elif moved > 0:
            print(f"\n[SUCESSO] Organização concluída! {moved} arquivo(s) processado(s).")
        else:
            print(f"\n[INFO] Nenhum arquivo foi processado.")
            
    except Exception as e:
        print(f"[ERRO] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
