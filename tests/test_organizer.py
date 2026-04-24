"""Testes automatizados do organizador de arquivos."""
import json
import pytest
from pathlib import Path

from organizer import (
    DEFAULT_MAP,
    analyze_folder_content,
    guess_folder,
    guess_folder_type,
    load_map,
    organize,
)


# ------------------------------------------------------------------ guess_folder

class TestGuessFolder:
    def test_image_extensions(self):
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
            assert guess_folder(ext, DEFAULT_MAP, "Outros") == "Imagens"

    def test_document_extensions(self):
        for ext in (".pdf", ".doc", ".docx", ".txt", ".xlsx", ".pptx"):
            assert guess_folder(ext, DEFAULT_MAP, "Outros") == "Documentos"

    def test_video_extensions(self):
        for ext in (".mp4", ".mkv", ".avi", ".mov"):
            assert guess_folder(ext, DEFAULT_MAP, "Outros") == "Vídeos"

    def test_audio_extensions(self):
        for ext in (".mp3", ".wav", ".flac", ".ogg"):
            assert guess_folder(ext, DEFAULT_MAP, "Outros") == "Áudio"

    def test_compressed_extensions(self):
        for ext in (".zip", ".rar", ".7z", ".tar", ".gz"):
            assert guess_folder(ext, DEFAULT_MAP, "Outros") == "Compactados"

    def test_unknown_extension_returns_unknown_name(self):
        assert guess_folder(".xyz123", DEFAULT_MAP, "Outros") == "Outros"
        assert guess_folder(".xyz123", DEFAULT_MAP, "Desconhecido") == "Desconhecido"

    def test_case_insensitive(self):
        assert guess_folder(".JPG", DEFAULT_MAP, "Outros") == "Imagens"
        assert guess_folder(".PDF", DEFAULT_MAP, "Outros") == "Documentos"

    def test_no_extension(self):
        assert guess_folder("", DEFAULT_MAP, "Outros") == "Outros"


# ------------------------------------------------------------------ guess_folder_type

class TestGuessFolderType:
    def test_image_keywords(self):
        assert guess_folder_type("fotos_ferias", "Outros") == "Imagens"
        assert guess_folder_type("screenshots", "Outros") == "Imagens"

    def test_document_keywords(self):
        assert guess_folder_type("documentos_2024", "Outros") == "Documentos"
        assert guess_folder_type("word_files", "Outros") == "Documentos"

    def test_video_keywords(self):
        assert guess_folder_type("videos_youtube", "Outros") == "Vídeos"

    def test_unknown_name_fallback(self):
        assert guess_folder_type("alguma_pasta_aleatoria", "Outros") == "Outros"


# ------------------------------------------------------------------ load_map

class TestLoadMap:
    def test_default_map_when_none(self):
        assert load_map(None) is DEFAULT_MAP

    def test_default_map_when_file_missing(self, tmp_path):
        assert load_map(tmp_path / "nao_existe.json") is DEFAULT_MAP

    def test_custom_json_loaded(self, tmp_path):
        config = {"Planilhas": [".csv", ".xlsx"]}
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps(config), encoding="utf-8")

        result = load_map(cfg_file)
        assert "Planilhas" in result
        assert ".csv" in result["Planilhas"]
        assert ".xlsx" in result["Planilhas"]

    def test_extension_normalized_without_dot(self, tmp_path):
        config = {"Imagens": ["jpg", "PNG"]}
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps(config), encoding="utf-8")

        result = load_map(cfg_file)
        assert ".jpg" in result["Imagens"]
        assert ".png" in result["Imagens"]

    def test_invalid_json_falls_back_to_default(self, tmp_path):
        cfg_file = tmp_path / "bad.json"
        cfg_file.write_text("{ isso não é json válido", encoding="utf-8")

        result = load_map(cfg_file)
        assert result is DEFAULT_MAP

    def test_caching(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text(json.dumps({"X": [".abc"]}), encoding="utf-8")

        r1 = load_map(cfg_file)
        r2 = load_map(cfg_file)
        assert r1 is r2  # mesmo objeto em memória → cache funcionando


# ------------------------------------------------------------------ analyze_folder_content

class TestAnalyzeFolderContent:
    def test_majority_images(self, tmp_path):
        for name in ("a.jpg", "b.png", "c.jpg", "d.txt"):
            (tmp_path / name).write_bytes(b"x")
        result = analyze_folder_content(tmp_path, DEFAULT_MAP)
        assert result == "Imagens"

    def test_empty_folder_returns_outros(self, tmp_path):
        assert analyze_folder_content(tmp_path, DEFAULT_MAP) == "Outros"

    def test_permission_error_returns_outros(self, tmp_path):
        # Passa um caminho inexistente para forçar OSError
        result = analyze_folder_content(tmp_path / "nao_existe", DEFAULT_MAP)
        assert result == "Outros"


# ------------------------------------------------------------------ organize — cópia

class TestOrganizeCopy:
    def _run(self, src, **kwargs):
        defaults = dict(
            source=src, dest_root=src, mode="copy", dry_run=False,
            delete_empty=False, unknown_name="Outros", ext_map=DEFAULT_MAP
        )
        defaults.update(kwargs)
        return organize(**defaults)

    def test_image_sorted(self, tmp_path):
        (tmp_path / "foto.jpg").write_bytes(b"img")
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0 and moved == 1
        assert (tmp_path / "Imagens" / "foto.jpg").exists()
        assert (tmp_path / "foto.jpg").exists()  # original mantido em modo copy

    def test_multiple_types(self, tmp_path):
        files = {"doc.pdf": b"pdf", "video.mp4": b"vid", "song.mp3": b"mp3", "arch.zip": b"zip"}
        for name, data in files.items():
            (tmp_path / name).write_bytes(data)
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0 and moved == 4
        assert (tmp_path / "Documentos" / "doc.pdf").exists()
        assert (tmp_path / "Vídeos" / "video.mp4").exists()
        assert (tmp_path / "Áudio" / "song.mp3").exists()
        assert (tmp_path / "Compactados" / "arch.zip").exists()

    def test_unknown_extension_goes_to_outros(self, tmp_path):
        (tmp_path / "arquivo.xyz99").write_bytes(b"?")
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0
        assert (tmp_path / "Outros" / "arquivo.xyz99").exists()

    def test_hidden_file_skipped(self, tmp_path):
        (tmp_path / ".DS_Store").write_bytes(b"hidden")
        _, moved, skipped, errors = self._run(tmp_path)
        assert errors == 0 and moved == 0 and skipped == 1

    def test_category_folder_not_moved_recursively(self, tmp_path):
        imagens = tmp_path / "Imagens"
        imagens.mkdir()
        (imagens / "ja_existente.jpg").write_bytes(b"img")
        (tmp_path / "nova.jpg").write_bytes(b"new")
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0
        assert (imagens / "ja_existente.jpg").exists()
        assert (imagens / "nova.jpg").exists()
        # pasta "Imagens" não deve ter sido aninhada dentro de si mesma
        assert not (imagens / "Imagens").exists()

    def test_duplicate_renamed_with_counter(self, tmp_path):
        imagens = tmp_path / "Imagens"
        imagens.mkdir()
        (imagens / "foto.jpg").write_bytes(b"old")
        (tmp_path / "foto.jpg").write_bytes(b"new")
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0
        assert (imagens / "foto.jpg").exists()
        assert (imagens / "foto (1).jpg").exists()

    def test_dest_root_different_from_source(self, tmp_path):
        src = tmp_path / "origem"
        dst = tmp_path / "destino"
        src.mkdir()
        (src / "foto.jpg").write_bytes(b"img")
        organize(src, dst, "copy", False, False, "Outros", DEFAULT_MAP)
        assert (dst / "Imagens" / "foto.jpg").exists()
        assert (src / "foto.jpg").exists()


# ------------------------------------------------------------------ organize — mover

class TestOrganizeMove:
    def _run(self, src, **kwargs):
        defaults = dict(
            source=src, dest_root=src, mode="move", dry_run=False,
            delete_empty=False, unknown_name="Outros", ext_map=DEFAULT_MAP
        )
        defaults.update(kwargs)
        return organize(**defaults)

    def test_original_removed_after_move(self, tmp_path):
        (tmp_path / "foto.jpg").write_bytes(b"img")
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0 and moved == 1
        assert (tmp_path / "Imagens" / "foto.jpg").exists()
        assert not (tmp_path / "foto.jpg").exists()

    def test_multiple_files_moved(self, tmp_path):
        for name in ("a.jpg", "b.pdf", "c.mp4"):
            (tmp_path / name).write_bytes(b"data")
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0 and moved == 3
        assert not (tmp_path / "a.jpg").exists()
        assert not (tmp_path / "b.pdf").exists()
        assert not (tmp_path / "c.mp4").exists()

    def test_move_with_duplicate_also_removes_original(self, tmp_path):
        imagens = tmp_path / "Imagens"
        imagens.mkdir()
        (imagens / "foto.jpg").write_bytes(b"existing")
        (tmp_path / "foto.jpg").write_bytes(b"new")
        _, moved, _, errors = self._run(tmp_path)
        assert errors == 0
        assert (imagens / "foto.jpg").exists()
        assert (imagens / "foto (1).jpg").exists()
        assert not (tmp_path / "foto.jpg").exists()  # original removido

    def test_delete_empty_removes_empty_subdir(self, tmp_path):
        empty = tmp_path / "pasta_vazia"
        empty.mkdir()
        organize(tmp_path, tmp_path, "move", False, True, "Outros", DEFAULT_MAP)
        assert not empty.exists()


# ------------------------------------------------------------------ organize — dry-run

class TestOrganizeDryRun:
    def test_no_files_created(self, tmp_path):
        (tmp_path / "foto.jpg").write_bytes(b"img")
        organize(tmp_path, tmp_path, "move", True, False, "Outros", DEFAULT_MAP)
        assert not (tmp_path / "Imagens" / "foto.jpg").exists()
        assert (tmp_path / "foto.jpg").exists()

    def test_report_contains_dry_run_marker(self, tmp_path):
        (tmp_path / "foto.jpg").write_bytes(b"img")
        report, _, _, _ = organize(tmp_path, tmp_path, "move", True, False, "Outros", DEFAULT_MAP)
        assert "[DRY-RUN]" in report

    def test_moved_count_is_zero(self, tmp_path):
        (tmp_path / "foto.jpg").write_bytes(b"img")
        _, moved, _, errors = organize(tmp_path, tmp_path, "move", True, False, "Outros", DEFAULT_MAP)
        assert moved == 0 and errors == 0


# ------------------------------------------------------------------ organize — log

class TestOrganizeLog:
    def test_log_file_created(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "foto.jpg").write_bytes(b"img")
        log_path = tmp_path / "logs" / "organizer.log"
        organize(src, src, "copy", False, False, "Outros", DEFAULT_MAP, log_path)
        log_files = list((tmp_path / "logs").glob("organizer_*.log"))
        assert len(log_files) == 1
        assert log_files[0].read_text(encoding="utf-8").strip()
