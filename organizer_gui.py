#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import queue
import sys
from pathlib import Path
import json
import time
from typing import Optional

from organizer import organize, load_map, DEFAULT_MAP


class OrganizerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Organizador de Arquivos")
        self.root.geometry("780x620")
        self.root.configure(bg="#f0f0f0")
        self.root.resizable(True, True)

        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.mode = tk.StringVar(value="move")
        self.dry_run = tk.BooleanVar(value=True)
        self.delete_empty = tk.BooleanVar(value=False)
        self.unknown_name = tk.StringVar(value="Outros")
        self.config_path = tk.StringVar()

        self.log_queue: queue.Queue = queue.Queue()
        self.is_organizing = False

        self._build_ui()
        self._poll_log_queue()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # Cabeçalho
        header = tk.Frame(self.root, bg="#2c3e50", height=55)
        header.pack(fill="x", padx=8, pady=(8, 0))
        header.pack_propagate(False)
        tk.Label(header, text="Organizador de Arquivos",
                 font=("Arial", 15, "bold"), fg="white", bg="#2c3e50").pack(expand=True)

        main = tk.Frame(self.root, bg="#f0f0f0")
        main.pack(fill="both", expand=True, padx=8, pady=6)

        self._build_paths(main)
        self._build_options(main)
        self._build_buttons(main)
        self._build_progress(main)
        self._build_log(main)

    def _build_paths(self, parent):
        frame = tk.LabelFrame(parent, text=" Pastas ", font=("Arial", 10, "bold"), bg="#f0f0f0")
        frame.pack(fill="x", pady=4)
        frame.columnconfigure(1, weight=1)

        # Origem
        tk.Label(frame, text="Origem:", bg="#f0f0f0", width=10, anchor="w").grid(
            row=0, column=0, padx=(8, 4), pady=6, sticky="w")
        tk.Entry(frame, textvariable=self.source_path).grid(
            row=0, column=1, padx=4, pady=6, sticky="ew")
        tk.Button(frame, text="Procurar", command=self._browse_source,
                  bg="#3498db", fg="white", width=8).grid(row=0, column=2, padx=(4, 8), pady=6)

        # Destino
        tk.Label(frame, text="Destino:", bg="#f0f0f0", width=10, anchor="w").grid(
            row=1, column=0, padx=(8, 4), pady=6, sticky="w")
        tk.Entry(frame, textvariable=self.dest_path).grid(
            row=1, column=1, padx=4, pady=6, sticky="ew")
        tk.Button(frame, text="Procurar", command=self._browse_dest,
                  bg="#3498db", fg="white", width=8).grid(row=1, column=2, padx=(4, 8), pady=6)

        # Config JSON (opcional)
        tk.Label(frame, text="Config JSON:", bg="#f0f0f0", width=10, anchor="w").grid(
            row=2, column=0, padx=(8, 4), pady=6, sticky="w")
        tk.Entry(frame, textvariable=self.config_path).grid(
            row=2, column=1, padx=4, pady=6, sticky="ew")
        tk.Button(frame, text="Procurar", command=self._browse_config,
                  bg="#e67e22", fg="white", width=8).grid(row=2, column=2, padx=(4, 8), pady=6)

    def _build_options(self, parent):
        frame = tk.LabelFrame(parent, text=" Opções ", font=("Arial", 10, "bold"), bg="#f0f0f0")
        frame.pack(fill="x", pady=4)

        # Modo de operação
        mode_row = tk.Frame(frame, bg="#f0f0f0")
        mode_row.pack(fill="x", padx=8, pady=4)
        tk.Label(mode_row, text="Modo:", bg="#f0f0f0").pack(side="left")
        tk.Radiobutton(mode_row, text="Mover arquivos (remove os originais)",
                       variable=self.mode, value="move", bg="#f0f0f0").pack(side="left", padx=10)
        tk.Radiobutton(mode_row, text="Copiar arquivos (mantém os originais)",
                       variable=self.mode, value="copy", bg="#f0f0f0").pack(side="left")

        # Checkboxes
        check_row = tk.Frame(frame, bg="#f0f0f0")
        check_row.pack(fill="x", padx=8, pady=4)
        tk.Checkbutton(check_row,
                       text="Modo Teste — apenas simula, não modifica nada  (recomendado na primeira vez)",
                       variable=self.dry_run, bg="#f0f0f0").pack(side="left", padx=(0, 20))
        tk.Checkbutton(check_row, text="Remover subpastas vazias",
                       variable=self.delete_empty, bg="#f0f0f0").pack(side="left")

        # Pasta para arquivos desconhecidos
        unknown_row = tk.Frame(frame, bg="#f0f0f0")
        unknown_row.pack(fill="x", padx=8, pady=(4, 8))
        tk.Label(unknown_row, text="Pasta para tipos não reconhecidos:", bg="#f0f0f0").pack(side="left")
        tk.Entry(unknown_row, textvariable=self.unknown_name, width=14).pack(side="left", padx=6)

    def _build_buttons(self, parent):
        row = tk.Frame(parent, bg="#f0f0f0")
        row.pack(fill="x", pady=6)

        self.organize_btn = tk.Button(
            row, text="ORGANIZAR", command=self._start_organize,
            font=("Arial", 12, "bold"), bg="#27ae60", fg="white",
            height=2, width=14)
        self.organize_btn.pack(side="left", padx=4)

        self.cancel_btn = tk.Button(
            row, text="Cancelar", command=self._cancel,
            bg="#e74c3c", fg="white", state="disabled")
        self.cancel_btn.pack(side="left", padx=4)

        tk.Button(row, text="Limpar log", command=self._clear_log,
                  bg="#95a5a6", fg="white").pack(side="left", padx=4)
        tk.Button(row, text="Salvar log", command=self._save_log,
                  bg="#3498db", fg="white").pack(side="left", padx=4)
        tk.Button(row, text="Ver config padrão", command=self._show_default_config,
                  bg="#9b59b6", fg="white").pack(side="left", padx=4)

    def _build_progress(self, parent):
        frame = tk.LabelFrame(parent, text=" Progresso ", font=("Arial", 10, "bold"), bg="#f0f0f0")
        frame.pack(fill="x", pady=4)

        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(frame, variable=self.progress_var, maximum=100).pack(
            fill="x", padx=8, pady=(6, 2))
        self.status_label = tk.Label(frame, text="Pronto.", bg="#f0f0f0", font=("Arial", 9))
        self.status_label.pack(pady=(0, 6))

    def _build_log(self, parent):
        frame = tk.LabelFrame(parent, text=" Log de Operações ", font=("Arial", 10, "bold"), bg="#f0f0f0")
        frame.pack(fill="both", expand=True, pady=4)

        self.log_text = scrolledtext.ScrolledText(
            frame, height=12, font=("Consolas", 9),
            bg="#2c3e50", fg="#ecf0f1", wrap="none")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)

    # ------------------------------------------------------------------ Ações

    def _browse_source(self):
        folder = filedialog.askdirectory(title="Selecionar pasta de origem")
        if folder:
            self.source_path.set(folder)
            if not self.dest_path.get():
                self.dest_path.set(folder)

    def _browse_dest(self):
        folder = filedialog.askdirectory(title="Selecionar pasta de destino")
        if folder:
            self.dest_path.set(folder)

    def _browse_config(self):
        path = filedialog.askopenfilename(
            title="Selecionar arquivo de configuração JSON",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
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
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")])
        if path:
            try:
                Path(path).write_text(content, encoding="utf-8")
                messagebox.showinfo("Sucesso", f"Log salvo em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    def _show_default_config(self):
        win = tk.Toplevel(self.root)
        win.title("Configuração padrão de extensões")
        win.geometry("620x420")
        win.configure(bg="#f0f0f0")

        config_json = json.dumps(DEFAULT_MAP, indent=2, ensure_ascii=False)
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", config_json)
        txt.config(state="disabled")

        tk.Button(win, text="Salvar como...",
                  command=lambda: self._save_config_file(config_json),
                  bg="#27ae60", fg="white").pack(pady=8)

    def _save_config_file(self, config_json: str):
        path = filedialog.asksaveasfilename(
            title="Salvar configuração", defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if path:
            try:
                Path(path).write_text(config_json, encoding="utf-8")
                messagebox.showinfo("Sucesso", f"Configuração salva em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    def _log(self, message: str):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def _poll_log_queue(self):
        try:
            while True:
                self._log(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _cancel(self):
        if self.is_organizing:
            self.is_organizing = False
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
            self.organize_btn.config(state="normal", text="ORGANIZAR")
            self.cancel_btn.config(state="disabled")
            self.status_label.config(text="Pronto.")

    def _start_organize(self):
        if not self.source_path.get():
            messagebox.showerror("Erro", "Selecione a pasta de origem.")
            return
        if not self.dest_path.get():
            messagebox.showerror("Erro", "Selecione a pasta de destino.")
            return

        self._set_ui_state(organizing=True)
        threading.Thread(target=self._organize_worker, daemon=True).start()

    def _organize_worker(self):
        try:
            source = Path(self.source_path.get())
            dest = Path(self.dest_path.get())
            config_path = Path(self.config_path.get()) if self.config_path.get() else None
            ext_map = load_map(config_path)

            sep = "=" * 55
            self.log_queue.put(sep)
            self.log_queue.put(f"Iniciando organização...")
            self.log_queue.put(f"Origem:  {source}")
            self.log_queue.put(f"Destino: {dest}")
            self.log_queue.put(f"Modo:    {'Mover' if self.mode.get() == 'move' else 'Copiar'}")
            if self.dry_run.get():
                self.log_queue.put("*** MODO TESTE — nenhum arquivo será alterado ***")
            self.log_queue.put(sep)

            self.root.after(0, lambda: self.status_label.config(text="Organizando arquivos..."))

            report, moved, skipped, errors = organize(
                source=source,
                dest_root=dest,
                mode=self.mode.get(),
                dry_run=self.dry_run.get(),
                delete_empty=self.delete_empty.get(),
                unknown_name=self.unknown_name.get(),
                ext_map=ext_map,
            )

            for line in report.split("\n"):
                if line.strip():
                    self.log_queue.put(line)

            if errors > 0:
                self.log_queue.put(f"\n⚠️  Concluído com {errors} erro(s).")
            elif moved > 0:
                self.log_queue.put(f"\n✅  {moved} item(ns) organizados com sucesso!")
            else:
                self.log_queue.put("\nℹ️  Nenhum item foi processado.")

        except Exception as e:
            self.log_queue.put(f"\n❌  Erro: {e}")
        finally:
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self._set_ui_state(organizing=False))


def main():
    root = tk.Tk()
    app = OrganizerGUI(root)

    # Pré-carrega a pasta Downloads como padrão
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        app.source_path.set(str(downloads))
        app.dest_path.set(str(downloads))

    root.mainloop()


if __name__ == "__main__":
    main()
