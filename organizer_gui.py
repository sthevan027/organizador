#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
from pathlib import Path
import json
from typing import List, Optional

from organizer import organize, load_map, DEFAULT_MAP

# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------
_BG       = "#f4f4f4"
_HEADER   = "#2c3e50"
_GREEN    = "#27ae60"
_BLUE     = "#3498db"
_ORANGE   = "#e67e22"
_RED      = "#e74c3c"
_PURPLE   = "#9b59b6"
_GRAY     = "#7f8c8d"

_LOG_BG   = "#1e2a38"
_LOG_FG   = "#ecf0f1"
_LOG_OK   = "#2ecc71"
_LOG_ERR  = "#e74c3c"
_LOG_WARN = "#f39c12"
_LOG_DRY  = "#74b9ff"
_LOG_HEAD = "#ffffff"
_LOG_INFO = "#95a5a6"

MAX_RECENT = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _btn(parent: tk.Widget, text: str, cmd, bg: str, **kw) -> tk.Button:
    """Botão flat com cursor de mão."""
    return tk.Button(parent, text=text, command=cmd,
                     bg=bg, fg="white", relief="flat", cursor="hand2", **kw)


class _Tooltip:
    """Tooltip simples que aparece ao passar o mouse sobre um widget."""

    def __init__(self, widget: tk.Widget, text: str):
        self._win: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", lambda _: self._show(widget, text))
        widget.bind("<Leave>", lambda _: self._hide())

    def _show(self, widget: tk.Widget, text: str):
        x = widget.winfo_rootx() + 16
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        self._win = tk.Toplevel(widget)
        self._win.wm_overrideredirect(True)
        self._win.wm_geometry(f"+{x}+{y}")
        tk.Label(self._win, text=text, background="#ffffcc",
                 relief="solid", borderwidth=1,
                 font=("Arial", 8), padx=5, pady=3).pack()

    def _hide(self):
        if self._win:
            self._win.destroy()
            self._win = None


def _tip(widget: tk.Widget, text: str) -> None:
    _Tooltip(widget, text)


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class OrganizerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Organizador de Arquivos")
        self.root.geometry("820x700")
        self.root.configure(bg=_BG)
        self.root.resizable(True, True)
        self.root.minsize(680, 560)

        self.source_path  = tk.StringVar()
        self.dest_path    = tk.StringVar()
        self.mode         = tk.StringVar(value="move")
        self.dry_run      = tk.BooleanVar(value=True)
        self.delete_empty = tk.BooleanVar(value=False)
        self.unknown_name = tk.StringVar(value="Outros")
        self.config_path  = tk.StringVar()

        self._recent_src: List[str] = []
        self._recent_dst: List[str] = []

        self.log_queue: queue.Queue = queue.Queue()
        self.is_organizing = False
        self._stop_event = threading.Event()

        self._build_ui()
        self._bind_shortcuts()
        self._poll_log_queue()

    # ------------------------------------------------------------------ build

    def _build_ui(self):
        self._build_header()
        main = tk.Frame(self.root, bg=_BG)
        main.pack(fill="both", expand=True, padx=10, pady=6)
        self._build_paths(main)
        self._build_options(main)
        self._build_buttons(main)
        self._build_progress(main)
        self._build_log(main)

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=_HEADER, height=52)
        hdr.pack(fill="x", padx=8, pady=(8, 0))
        hdr.pack_propagate(False)
        inner = tk.Frame(hdr, bg=_HEADER)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(inner, text="Organizador de Arquivos",
                 font=("Arial", 15, "bold"), fg="white",
                 bg=_HEADER).pack(side="left")
        tk.Label(inner, text="  —  ordene seus arquivos em segundos",
                 font=("Arial", 9), fg="#95a5a6",
                 bg=_HEADER).pack(side="left", pady=(4, 0))

    def _build_paths(self, parent: tk.Widget):
        frm = tk.LabelFrame(parent, text=" Pastas ",
                            font=("Arial", 10, "bold"), bg=_BG)
        frm.pack(fill="x", pady=(0, 4))
        frm.columnconfigure(1, weight=1)

        def _path_row(row: int, label: str, var: tk.StringVar,
                      recents: List[str], cmd, tip_text: str) -> ttk.Combobox:
            tk.Label(frm, text=label, bg=_BG, width=12, anchor="w",
                     font=("Arial", 9)).grid(row=row, column=0,
                                             padx=(10, 4), pady=5, sticky="w")
            combo = ttk.Combobox(frm, textvariable=var,
                                 values=recents, font=("Arial", 9))
            combo.grid(row=row, column=1, padx=4, pady=5, sticky="ew")
            b = _btn(frm, "Procurar", cmd, _BLUE, padx=6, pady=2)
            b.grid(row=row, column=2, padx=(4, 10), pady=5)
            _tip(b, tip_text)
            return combo

        self._src_combo = _path_row(0, "Origem:", self.source_path,
                                    self._recent_src, self._browse_source,
                                    "Pasta a ser organizada")
        self._dst_combo = _path_row(1, "Destino:", self.dest_path,
                                    self._recent_dst, self._browse_dest,
                                    "Onde os arquivos serão colocados")

        tk.Label(frm, text="Config JSON:", bg=_BG, width=12, anchor="w",
                 font=("Arial", 9)).grid(row=2, column=0,
                                         padx=(10, 4), pady=5, sticky="w")
        tk.Entry(frm, textvariable=self.config_path,
                 font=("Arial", 9)).grid(row=2, column=1,
                                          padx=4, pady=5, sticky="ew")
        b_cfg = _btn(frm, "Procurar", self._browse_config, _ORANGE, padx=6, pady=2)
        b_cfg.grid(row=2, column=2, padx=(4, 10), pady=5)
        _tip(b_cfg, "Mapeamento personalizado de extensões (opcional)")

    def _build_options(self, parent: tk.Widget):
        frm = tk.LabelFrame(parent, text=" Opções ",
                            font=("Arial", 10, "bold"), bg=_BG)
        frm.pack(fill="x", pady=4)

        # Modo de operação
        mode_row = tk.Frame(frm, bg=_BG)
        mode_row.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(mode_row, text="Modo:", bg=_BG,
                 font=("Arial", 9, "bold")).pack(side="left")

        r_move = tk.Radiobutton(mode_row, text="Mover  (remove originais)",
                                variable=self.mode, value="move",
                                bg=_BG, font=("Arial", 9), cursor="hand2")
        r_move.pack(side="left", padx=12)
        _tip(r_move, "Move arquivos para o destino e remove os originais")

        r_copy = tk.Radiobutton(mode_row, text="Copiar  (mantém originais)",
                                variable=self.mode, value="copy",
                                bg=_BG, font=("Arial", 9), cursor="hand2")
        r_copy.pack(side="left")
        _tip(r_copy, "Copia arquivos para o destino, mantendo os originais intactos")

        # Checkboxes
        chk_row = tk.Frame(frm, bg=_BG)
        chk_row.pack(fill="x", padx=10, pady=2)

        cb_dry = tk.Checkbutton(
            chk_row,
            text="Modo Teste  (simula sem modificar arquivos)",
            variable=self.dry_run, bg=_BG, font=("Arial", 9),
            cursor="hand2", fg="#c0392b", selectcolor=_BG,
        )
        cb_dry.pack(side="left", padx=(0, 20))
        _tip(cb_dry, "Recomendado na primeira vez: mostra o que seria feito sem alterar nada")

        cb_empty = tk.Checkbutton(
            chk_row, text="Remover subpastas vazias",
            variable=self.delete_empty, bg=_BG,
            font=("Arial", 9), cursor="hand2", selectcolor=_BG,
        )
        cb_empty.pack(side="left")
        _tip(cb_empty, "Remove subpastas que ficaram vazias após a organização")

        # Pasta para desconhecidos
        unk_row = tk.Frame(frm, bg=_BG)
        unk_row.pack(fill="x", padx=10, pady=(2, 8))
        tk.Label(unk_row, text="Pasta para tipos não reconhecidos:",
                 bg=_BG, font=("Arial", 9)).pack(side="left")
        unk_ent = tk.Entry(unk_row, textvariable=self.unknown_name,
                           width=14, font=("Arial", 9))
        unk_ent.pack(side="left", padx=6)
        _tip(unk_ent, "Arquivos com extensão desconhecida irão para esta pasta")

    def _build_buttons(self, parent: tk.Widget):
        row = tk.Frame(parent, bg=_BG)
        row.pack(fill="x", pady=4)

        self.organize_btn = _btn(row, "▶  ORGANIZAR", self._start_organize, _GREEN,
                                 font=("Arial", 11, "bold"), padx=16, pady=5)
        self.organize_btn.pack(side="left", padx=(0, 4))
        _tip(self.organize_btn, "Iniciar organização  [F5]")

        self.cancel_btn = _btn(row, "Cancelar", self._cancel, _RED,
                               state="disabled", padx=10, pady=5)
        self.cancel_btn.pack(side="left", padx=4)
        _tip(self.cancel_btn, "Cancelar operação em curso  [Esc]")

        tk.Frame(row, bg="#cccccc", width=1, height=30).pack(side="left", padx=10)

        b_clear = _btn(row, "Limpar log", self._clear_log, _GRAY, padx=8, pady=5)
        b_clear.pack(side="left", padx=2)
        _tip(b_clear, "Limpar conteúdo do log  [Ctrl+L]")

        b_save = _btn(row, "Salvar log", self._save_log, _BLUE, padx=8, pady=5)
        b_save.pack(side="left", padx=2)
        _tip(b_save, "Salvar log em arquivo  [Ctrl+S]")

        b_cfg = _btn(row, "Ver config padrão", self._show_default_config,
                     _PURPLE, padx=8, pady=5)
        b_cfg.pack(side="left", padx=2)
        _tip(b_cfg, "Exibe o mapeamento padrão de extensões por categoria")

    def _build_progress(self, parent: tk.Widget):
        frm = tk.LabelFrame(parent, text=" Progresso ",
                            font=("Arial", 10, "bold"), bg=_BG)
        frm.pack(fill="x", pady=4)

        self.progress_var = tk.DoubleVar()
        style = ttk.Style()
        style.configure("Green.Horizontal.TProgressbar",
                        troughcolor="#d5d8dc", background=_GREEN, thickness=14)
        ttk.Progressbar(frm, variable=self.progress_var, maximum=100,
                        style="Green.Horizontal.TProgressbar").pack(
            fill="x", padx=10, pady=(6, 2))

        self.status_label = tk.Label(frm, text="Pronto.", bg=_BG,
                                     font=("Arial", 9), fg="#555555")
        self.status_label.pack(pady=(0, 4))

        # Contadores de resultado
        stats_row = tk.Frame(frm, bg=_BG)
        stats_row.pack(fill="x", padx=10, pady=(0, 6))
        self._stat_labels: dict = {}
        for key, label, color in [
            ("total",   "Total: —",       _BLUE),
            ("moved",   "Organizados: —", _GREEN),
            ("skipped", "Pulados: —",     _ORANGE),
            ("errors",  "Erros: —",       _RED),
        ]:
            lbl = tk.Label(stats_row, text=label, bg=_BG,
                           font=("Arial", 9, "bold"), fg=color)
            lbl.pack(side="left", padx=(0, 18))
            self._stat_labels[key] = lbl

    def _build_log(self, parent: tk.Widget):
        frm = tk.LabelFrame(parent, text=" Log de Operações ",
                            font=("Arial", 10, "bold"), bg=_BG)
        frm.pack(fill="both", expand=True, pady=(4, 0))

        self.log_text = scrolledtext.ScrolledText(
            frm, height=10, font=("Consolas", 9),
            bg=_LOG_BG, fg=_LOG_FG, wrap="none",
            insertbackground="white", selectbackground=_BLUE,
        )
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

        for tag, color, bold in [
            ("ok",      _LOG_OK,   False),
            ("error",   _LOG_ERR,  False),
            ("warning", _LOG_WARN, False),
            ("dryrun",  _LOG_DRY,  False),
            ("header",  _LOG_HEAD, True),
            ("info",    _LOG_INFO, False),
        ]:
            kw: dict = {"foreground": color}
            if bold:
                kw["font"] = ("Consolas", 9, "bold")
            self.log_text.tag_configure(tag, **kw)

    # ------------------------------------------------------------------ atalhos e helpers

    def _bind_shortcuts(self):
        self.root.bind("<F5>",        lambda _: self._start_organize())
        self.root.bind("<Escape>",    lambda _: self._cancel())
        self.root.bind("<Control-l>", lambda _: self._clear_log())
        self.root.bind("<Control-s>", lambda _: self._save_log())

    def _push_recent(self, path: str, lst: List[str], combo: ttk.Combobox):
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        del lst[MAX_RECENT:]
        combo["values"] = lst

    def _log(self, message: str):
        tag = self._tag_for(message)
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)

    def _tag_for(self, line: str) -> str:
        if line.startswith("[OK]") or "✅" in line:
            return "ok"
        if line.startswith("[ERRO]") or "❌" in line:
            return "error"
        if line.startswith("[AVISO]") or "⚠️" in line:
            return "warning"
        if line.startswith("[DRY-RUN]") or "MODO TESTE" in line:
            return "dryrun"
        if line.startswith("=") or line.startswith("Processados"):
            return "header"
        if line.startswith("ℹ️"):
            return "info"
        return ""

    def _poll_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and len(item) == 3 and item[0] == "_progress":
                    _, current, total = item
                    pct = (current / total * 100) if total else 100
                    self.progress_var.set(pct)
                    self.status_label.config(text=f"Processando {current} de {total}...")
                else:
                    self._log(str(item))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------ ações

    def _browse_source(self):
        folder = filedialog.askdirectory(title="Selecionar pasta de origem")
        if folder:
            self.source_path.set(folder)
            self._push_recent(folder, self._recent_src, self._src_combo)
            if not self.dest_path.get():
                self.dest_path.set(folder)
                self._push_recent(folder, self._recent_dst, self._dst_combo)

    def _browse_dest(self):
        folder = filedialog.askdirectory(title="Selecionar pasta de destino")
        if folder:
            self.dest_path.set(folder)
            self._push_recent(folder, self._recent_dst, self._dst_combo)

    def _browse_config(self):
        path = filedialog.askopenfilename(
            title="Selecionar arquivo de configuração JSON",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if path:
            self.config_path.set(path)

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def _save_log(self):
        content = self.log_text.get("1.0", tk.END)
        if not content.strip():
            messagebox.showwarning("Aviso", "O log está vazio!")
            return
        path = filedialog.asksaveasfilename(
            title="Salvar log", defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if path:
            try:
                Path(path).write_text(content, encoding="utf-8")
                messagebox.showinfo("Sucesso", f"Log salvo em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    def _show_default_config(self):
        win = tk.Toplevel(self.root)
        win.title("Configuração padrão de extensões")
        win.geometry("640x460")
        win.configure(bg=_BG)
        config_json = json.dumps(DEFAULT_MAP, indent=2, ensure_ascii=False)
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10),
                                        bg=_LOG_BG, fg=_LOG_FG)
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", config_json)
        txt.config(state="disabled")
        _btn(win, "Salvar como...",
             lambda: self._save_config_file(config_json),
             _GREEN, padx=10, pady=4).pack(pady=(0, 10))

    def _save_config_file(self, config_json: str):
        path = filedialog.asksaveasfilename(
            title="Salvar configuração", defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if path:
            try:
                Path(path).write_text(config_json, encoding="utf-8")
                messagebox.showinfo("Sucesso", f"Configuração salva em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    def _cancel(self):
        if self.is_organizing:
            self._stop_event.set()
            self.log_queue.put("⚠️  Operação cancelada pelo usuário.")
            self._set_ui_state(organizing=False)

    def _set_ui_state(self, organizing: bool):
        self.is_organizing = organizing
        if organizing:
            self.organize_btn.config(state="disabled", text="Organizando...")
            self.cancel_btn.config(state="normal")
            self.progress_var.set(0)
            self.status_label.config(text="Iniciando...")
        else:
            self.organize_btn.config(state="normal", text="▶  ORGANIZAR")
            self.cancel_btn.config(state="disabled")
            self.status_label.config(text="Pronto.")

    def _update_stats(self, total: int, moved: int, skipped: int, errors: int):
        self._stat_labels["total"].config(text=f"Total: {total}")
        self._stat_labels["moved"].config(text=f"Organizados: {moved}")
        self._stat_labels["skipped"].config(text=f"Pulados: {skipped}")
        self._stat_labels["errors"].config(text=f"Erros: {errors}")

    def _start_organize(self):
        if self.is_organizing:
            return
        if not self.source_path.get():
            messagebox.showerror("Erro", "Selecione a pasta de origem.")
            return
        if not self.dest_path.get():
            messagebox.showerror("Erro", "Selecione a pasta de destino.")
            return
        self._stop_event.clear()
        self._set_ui_state(organizing=True)
        threading.Thread(target=self._organize_worker, daemon=True).start()

    def _organize_worker(self):
        try:
            source  = Path(self.source_path.get())
            dest    = Path(self.dest_path.get())
            cfgp    = Path(self.config_path.get()) if self.config_path.get() else None
            ext_map = load_map(cfgp)

            sep = "=" * 55
            self.log_queue.put(sep)
            self.log_queue.put("Iniciando organização...")
            self.log_queue.put(f"Origem:  {source}")
            self.log_queue.put(f"Destino: {dest}")
            self.log_queue.put(f"Modo:    {'Mover' if self.mode.get() == 'move' else 'Copiar'}")
            if self.dry_run.get():
                self.log_queue.put("*** MODO TESTE — nenhum arquivo será alterado ***")
            self.log_queue.put(sep)

            def progress_cb(current: int, total: int):
                self.log_queue.put(("_progress", current, total))

            report, moved, skipped, errors = organize(
                source=source,
                dest_root=dest,
                mode=self.mode.get(),
                dry_run=self.dry_run.get(),
                delete_empty=self.delete_empty.get(),
                unknown_name=self.unknown_name.get(),
                ext_map=ext_map,
                progress_cb=progress_cb,
            )

            for line in report.split("\n"):
                if line.strip():
                    self.log_queue.put(line)

            total_count = moved + skipped + errors
            self.root.after(0, lambda: self._update_stats(
                total_count, moved, skipped, errors))

            if errors > 0:
                self.log_queue.put(f"⚠️  Concluído com {errors} erro(s).")
            elif moved > 0:
                self.log_queue.put(f"✅  {moved} item(ns) organizados com sucesso!")
            else:
                self.log_queue.put("ℹ️  Nenhum item foi processado.")

        except Exception as e:
            self.log_queue.put(f"❌  Erro: {e}")
        finally:
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self._set_ui_state(organizing=False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    app = OrganizerGUI(root)

    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        src = str(downloads)
        app.source_path.set(src)
        app.dest_path.set(src)
        app._push_recent(src, app._recent_src, app._src_combo)
        app._push_recent(src, app._recent_dst, app._dst_combo)

    root.mainloop()


if __name__ == "__main__":
    main()
