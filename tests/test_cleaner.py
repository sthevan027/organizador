"""Testes automatizados da limpeza de disco."""
import os
import time
from pathlib import Path

import pytest

from cleaner import (
    CleanItem,
    clean,
    human_bytes,
    scan_browser_cache,
    scan_dev_cache,
    scan_old_downloads,
    scan_temp,
    _parse_docker_size,
)


# ------------------------------------------------------------------ human_bytes

class TestHumanBytes:
    def test_bytes(self):
        assert human_bytes(500) == "500 B"

    def test_kilobytes(self):
        assert human_bytes(2048) == "2,0 KB"

    def test_megabytes(self):
        assert human_bytes(5 * 1024 * 1024) == "5,0 MB"

    def test_gigabytes(self):
        assert human_bytes(3 * 1024 ** 3) == "3,0 GB"

    def test_zero(self):
        assert human_bytes(0) == "0 B"


# ------------------------------------------------------------------ scan_temp

class TestScanTemp:
    def test_lists_files_and_dirs(self, tmp_path):
        temp_dir = tmp_path / "Temp"
        temp_dir.mkdir()
        (temp_dir / "arquivo.tmp").write_bytes(b"x" * 100)
        sub = temp_dir / "subpasta"
        sub.mkdir()
        (sub / "outro.log").write_bytes(b"y" * 50)

        items = scan_temp([("Temporários de teste", temp_dir)])

        assert len(items) == 2
        names = {i.path.name for i in items}
        assert names == {"arquivo.tmp", "subpasta"}
        assert all(i.category == "temp" for i in items)

    def test_missing_dir_is_ignored(self, tmp_path):
        items = scan_temp([("Não existe", tmp_path / "nao_existe")])
        assert items == []

    def test_empty_dir_returns_no_items(self, tmp_path):
        empty = tmp_path / "vazio"
        empty.mkdir()
        assert scan_temp([("Vazio", empty)]) == []


# ------------------------------------------------------------------ scan_browser_cache

class TestScanBrowserCache:
    def test_cache_with_content_is_listed(self, tmp_path):
        cache = tmp_path / "Cache"
        cache.mkdir()
        (cache / "data_0").write_bytes(b"x" * 200)

        items = scan_browser_cache([("Chrome", cache)])

        assert len(items) == 1
        assert items[0].kind == "dir_contents"
        assert items[0].size_bytes == 200
        assert items[0].path == cache

    def test_empty_cache_is_not_listed(self, tmp_path):
        cache = tmp_path / "Cache"
        cache.mkdir()
        assert scan_browser_cache([("Chrome", cache)]) == []

    def test_missing_cache_is_ignored(self, tmp_path):
        assert scan_browser_cache([("Chrome", tmp_path / "nao_existe")]) == []


# ------------------------------------------------------------------ scan_old_downloads

class TestScanOldDownloads:
    def _touch_with_age(self, path: Path, days_old: int):
        path.write_bytes(b"x" * 10)
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))

    def test_old_file_is_listed(self, tmp_path):
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        old_file = downloads / "instalador.exe"
        self._touch_with_age(old_file, days_old=45)

        items = scan_old_downloads(downloads, days=30)

        assert len(items) == 1
        assert items[0].category == "old_downloads"
        assert "dias sem uso" in items[0].detail

    def test_recent_file_is_not_listed(self, tmp_path):
        downloads = tmp_path / "Downloads"
        downloads.mkdir()
        recent_file = downloads / "novo.zip"
        recent_file.write_bytes(b"x")

        assert scan_old_downloads(downloads, days=30) == []

    def test_missing_downloads_dir_returns_empty(self, tmp_path):
        assert scan_old_downloads(tmp_path / "nao_existe", days=30) == []


# ------------------------------------------------------------------ scan_dev_cache

class TestScanDevCache:
    def _touch_with_age(self, path: Path, days_old: int):
        old_time = time.time() - days_old * 86400
        os.utime(path, (old_time, old_time))

    def test_stale_node_modules_is_listed(self, tmp_path):
        project = tmp_path / "projeto-antigo"
        project.mkdir()
        pkg = project / "package.json"
        pkg.write_text("{}")
        self._touch_with_age(pkg, days_old=90)

        nm = project / "node_modules"
        nm.mkdir()
        (nm / "lib.js").write_bytes(b"x" * 100)

        items = scan_dev_cache([tmp_path], stale_days=60)

        node_modules_items = [i for i in items if i.path == nm]
        assert len(node_modules_items) == 1
        assert node_modules_items[0].category == "dev_cache"

    def test_active_node_modules_is_not_listed(self, tmp_path):
        project = tmp_path / "projeto-ativo"
        project.mkdir()
        (project / "package.json").write_text("{}")  # mtime recente

        nm = project / "node_modules"
        nm.mkdir()
        (nm / "lib.js").write_bytes(b"x")

        items = scan_dev_cache([tmp_path], stale_days=60)

        assert [i for i in items if i.path == nm] == []

    def test_does_not_descend_into_node_modules(self, tmp_path):
        project = tmp_path / "projeto"
        project.mkdir()
        pkg = project / "package.json"
        pkg.write_text("{}")
        self._touch_with_age(pkg, days_old=90)

        nm = project / "node_modules"
        nested = nm / "alguma_lib" / "node_modules"
        nested.mkdir(parents=True)
        (nested / "x.js").write_bytes(b"x")

        items = scan_dev_cache([tmp_path], stale_days=60)

        # só o node_modules de topo deve aparecer, nunca o aninhado
        paths = {i.path for i in items if i.category == "dev_cache" and i.path.name == "node_modules"}
        assert paths == {nm}


# ------------------------------------------------------------------ _parse_docker_size

class TestParseDockerSize:
    def test_gb(self):
        assert _parse_docker_size("1.2GB (80%)") == int(1.2 * 1024 ** 3)

    def test_mb(self):
        assert _parse_docker_size("500MB") == 500 * 1024 ** 2

    def test_zero_bytes(self):
        assert _parse_docker_size("0B") == 0

    def test_unparseable_returns_zero(self):
        assert _parse_docker_size("N/A") == 0


# ------------------------------------------------------------------ clean

class TestClean:
    def test_dry_run_does_not_delete(self, tmp_path):
        f = tmp_path / "arquivo.tmp"
        f.write_bytes(b"x" * 100)
        item = CleanItem("temp", "arquivo.tmp", f, 100, "file")

        report, freed, removed, errors = clean([item], dry_run=True)

        assert f.exists()
        assert freed == 0
        assert removed == 0
        assert "[DRY-RUN]" in report

    def test_real_run_deletes_file(self, tmp_path):
        f = tmp_path / "arquivo.tmp"
        f.write_bytes(b"x" * 100)
        item = CleanItem("temp", "arquivo.tmp", f, 100, "file")

        report, freed, removed, errors = clean([item], dry_run=False)

        assert not f.exists()
        assert freed == 100
        assert removed == 1
        assert errors == 0

    def test_real_run_deletes_dir(self, tmp_path):
        d = tmp_path / "pasta"
        d.mkdir()
        (d / "x.txt").write_bytes(b"x" * 50)
        item = CleanItem("temp", "pasta", d, 50, "dir")

        report, freed, removed, errors = clean([item], dry_run=False)

        assert not d.exists()
        assert freed == 50
        assert removed == 1

    def test_dir_contents_keeps_folder(self, tmp_path):
        cache = tmp_path / "Cache"
        cache.mkdir()
        (cache / "data_0").write_bytes(b"x" * 200)
        item = CleanItem("browser_cache", "Cache do Chrome", cache, 200, "dir_contents")

        report, freed, removed, errors = clean([item], dry_run=False)

        assert cache.exists()
        assert list(cache.iterdir()) == []
        assert freed == 200
        assert removed == 1

    def test_missing_path_counts_as_error(self, tmp_path):
        item = CleanItem("temp", "sumiu.tmp", tmp_path / "sumiu.tmp", 10, "file")

        report, freed, removed, errors = clean([item], dry_run=False)

        assert errors == 1
        assert removed == 0
        assert "[ERRO]" in report
