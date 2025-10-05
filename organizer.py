#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import shutil
import sys
import json
import time
from pathlib import Path

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


def load_map(config_path: Path | None):
    """Carrega o mapa de extensões do arquivo de configuração ou usa o padrão."""
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # normaliza extensões para minúsculas e com ponto
        return {k: [e.lower() if e.startswith(".") else f".{e.lower()}" for e in v] for k, v in data.items()}
    return DEFAULT_MAP


def guess_folder(ext: str, ext_map: dict[str, list[str]], unknown_name: str):
    """Determina em qual pasta o arquivo deve ser colocado baseado na extensão."""
    ext = ext.lower()
    for folder, exts in ext_map.items():
        if ext in exts:
            return folder
    return unknown_name


def human(n: int) -> str:
    """Formata números com separadores de milhares."""
    return f"{n:,}".replace(",", ".")


def organize(
    source: Path,
    dest_root: Path,
    mode: str,
    dry_run: bool,
    delete_empty: bool,
    unknown_name: str,
    ext_map: dict[str, list[str]],
    log_path: Path | None
):
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

    if not source.exists() or not source.is_dir():
        raise RuntimeError(f"Pasta de origem inválida: {source}")

    dest_root.mkdir(parents=True, exist_ok=True)

    # Primeira passada: organiza (copia) todos os arquivos
    for p in source.iterdir():
        if p.is_dir():
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
    if mode == "move" and not dry_run and files_to_remove and errors == 0:
        logs.append("")
        logs.append("Verificando organização...")
        
        # Verifica se todos os arquivos foram copiados corretamente
        all_verified = True
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
        
        if all_verified:
            logs.append("Verificação concluída com sucesso. Removendo arquivos originais...")
            # Remove os arquivos originais
            for original_file in files_to_remove:
                try:
                    original_file.unlink()
                    logs.append(f"[OK] REMOVER: {original_file.name}")
                except Exception as e:
                    logs.append(f"[ERRO] Falha ao remover {original_file.name}: {e}")
                    errors += 1
        else:
            logs.append("[AVISO] Verificação falhou. Arquivos originais mantidos por segurança.")
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
