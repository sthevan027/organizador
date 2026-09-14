#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Painel de Limpeza de Disco (CustomTkinter).

Embutido na mesma janela do Organizador de Arquivos (troca de view, sem
abrir janela nova), reaproveitando os tokens de tema em theme.py. Fluxo:
Analisar (sempre seguro, só lista e soma tamanhos) -> revisar o relatório
-> Limpar selecionadas (pede confirmação quando "Modo Teste" está
desligado).
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from cleaner import CATEGORIES, CleanItem, clean, human_bytes, scan_all
from theme import FONT, RADIUS, SPACING, palette

_CATEGORY_TIPS: Dict[str, str] = {
    "temp": "%TEMP% do usuário, C:\\Windows\\Temp e Prefetch.",
    "browser_cache": "Cache de Chrome, Edge e Firefox — nunca senhas, histórico ou cookies.",
    "recycle_bin": "Esvazia a Lixeira do Windows.",
    "old_downloads": "Lista (não apaga sozinho) arquivos parados na pasta Downloads.",
    "dev_cache": "node_modules de projetos parados + cache do npm/pip/Docker.",
    "crash_dumps": "Dumps de erro do Windows (WER) e CrashDumps — sobras de apps que travaram.",
}


class _Tooltip:
    def __init__(self, widget, text: str, palette_ref: dict):
        self._win: Optional[tk.Toplevel] = None
        self._widget = widget
        self._text = text
        self._palette_ref = palette_ref
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, _event=None):
        if self._win or not self._text:
            return
        x = self._widget.winfo_rootx() + 14
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        self._win = tk.Toplevel(self._widget)
        self._win.wm_overrideredirect(True)
        self._win.wm_geometry(f"+{x}+{y}")
        bg = self._palette_ref.get("bg", "#1f2430")
        fg = self._palette_ref.get("text", "#f3f4f6")
        frame = tk.Frame(self._win, bg=bg, bd=0, highlightthickness=1,
                         highlightbackground=self._palette_ref.get("card_border", "#2a2f3d"))
        frame.pack()
        tk.Label(
            frame, text=self._text, bg=bg, fg=fg,
            font=FONT["small"], padx=8, pady=4, justify="left",
        ).pack()

    def _hide(self, _event=None):
        if self._win:
            self._win.destroy()
            self._win = None


class CleanerPanel(ctk.CTkFrame):
    """View de Limpeza de Disco, embutida na janela do Organizador."""

    def __init__(
        self,
        master,
        theme_name: str = "dark",
        on_back: Optional[Callable[[], None]] = None,
    ):
        self.theme_name = theme_name
        super().__init__(master, fg_color=self._c("bg"), corner_radius=0)
        self._on_back = on_back

        self.cat_vars: Dict[str, tk.BooleanVar] = {
            key: tk.BooleanVar(value=True) for key in CATEGORIES
        }
        self.dry_run = tk.BooleanVar(value=True)
        self.old_downloads_days = tk.StringVar(value="30")
        self.dev_search_root = tk.StringVar(value="")
        self.dev_stale_days = tk.StringVar(value="60")

        self.log_queue: queue.Queue = queue.Queue()
        self.scanned_items: List[CleanItem] = []
        self.is_running = False

        self._build_ui()
        self._poll_log_queue()

    # ------------------------------------------------------------------ infra

    def _c(self, key: str) -> str:
        return palette(self.theme_name)[key]

    def _back(self) -> None:
        if self.is_running:
            messagebox.showwarning("Aguarde", "Espere a operação atual terminar antes de voltar.")
            return
        if self._on_back:
            self._on_back()

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["lg"], 0))

        back_btn = ctk.CTkButton(
            header_row, text="← Voltar", command=self._back,
            font=FONT["button"], height=32, width=100,
            corner_radius=RADIUS["button"],
            fg_color=self._c("neutral"), hover_color=self._c("neutral_hover"),
            text_color="#ffffff",
        )
        back_btn.pack(side="left", padx=(0, SPACING["md"]))

        header = ctk.CTkLabel(
            header_row, text="🧹  Limpeza de Disco",
            font=FONT["title"], text_color=self._c("text"), anchor="w",
        )
        header.pack(side="left")

        subtitle = ctk.CTkLabel(
            self,
            text="Analise antes de limpar — nada é removido sem revisão.",
            font=FONT["subtitle"], text_color=self._c("text_muted"), anchor="w",
        )
        subtitle.pack(fill="x", padx=SPACING["lg"], pady=(0, SPACING["sm"]))

        main = ctk.CTkScrollableFrame(self, fg_color=self._c("bg"), corner_radius=0)
        main.pack(fill="both", expand=True, padx=SPACING["lg"], pady=(0, SPACING["md"]))

        self._build_categories_card(main)
        self._build_options_card(main)
        self._build_actions(main)
        self._build_progress_card(main)
        self._build_log_card(main)

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent, fg_color=self._c("card"), corner_radius=RADIUS["card"],
            border_width=1, border_color=self._c("card_border"),
        )
        card.pack(fill="x", pady=(SPACING["md"], 0))
        label = ctk.CTkLabel(
            card, text=title, font=FONT["section"],
            text_color=self._c("text"), anchor="w",
        )
        label.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["md"], 0))
        return card

    # ---- categorias ---------------------------------------------------

    def _build_categories_card(self, parent) -> None:
        card = self._card(parent, "O que limpar")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))

        for key, label_text in CATEGORIES.items():
            sw = ctk.CTkSwitch(
                body, text=label_text, variable=self.cat_vars[key],
                font=FONT["label"], text_color=self._c("text"),
                progress_color=self._c("primary"),
                button_color="#ffffff", button_hover_color="#f3f4f6",
            )
            sw.pack(anchor="w", pady=SPACING["xs"])
            _Tooltip(sw, _CATEGORY_TIPS[key], dict(palette(self.theme_name)))

    # ---- opções ---------------------------------------------------------

    def _build_options_card(self, parent) -> None:
        card = self._card(parent, "Opções")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))

        row1 = ctk.CTkFrame(body, fg_color="transparent")
        row1.pack(fill="x", pady=SPACING["xs"])
        ctk.CTkLabel(
            row1, text="Downloads parados há mais de (dias)",
            font=FONT["label"], text_color=self._c("text_muted"), width=260, anchor="w",
        ).pack(side="left")
        ctk.CTkEntry(
            row1, textvariable=self.old_downloads_days, width=70, height=32,
            corner_radius=RADIUS["input"], font=FONT["label"],
            fg_color=self._c("input_bg"), text_color=self._c("text"),
            border_color=self._c("input_border"),
        ).pack(side="left", padx=SPACING["sm"])

        row2 = ctk.CTkFrame(body, fg_color="transparent")
        row2.pack(fill="x", pady=SPACING["xs"])
        ctk.CTkLabel(
            row2, text="Pasta de projetos (cache de dev)",
            font=FONT["label"], text_color=self._c("text_muted"), width=260, anchor="w",
        ).pack(side="left")
        ctk.CTkEntry(
            row2, textvariable=self.dev_search_root, height=32,
            corner_radius=RADIUS["input"], font=FONT["label"],
            fg_color=self._c("input_bg"), text_color=self._c("text"),
            border_color=self._c("input_border"),
            placeholder_text="Opcional — ex.: D:\\Projetos",
        ).pack(side="left", fill="x", expand=True, padx=SPACING["sm"])
        ctk.CTkButton(
            row2, text="Procurar", command=self._browse_dev_root,
            font=FONT["button"], height=32, width=100,
            corner_radius=RADIUS["button"],
            fg_color=self._c("primary"), hover_color=self._c("primary_hover"),
            text_color="#ffffff",
        ).pack(side="left")

        row3 = ctk.CTkFrame(body, fg_color="transparent")
        row3.pack(fill="x", pady=SPACING["xs"])
        ctk.CTkLabel(
            row3, text="Projeto parado há mais de (dias)",
            font=FONT["label"], text_color=self._c("text_muted"), width=260, anchor="w",
        ).pack(side="left")
        ctk.CTkEntry(
            row3, textvariable=self.dev_stale_days, width=70, height=32,
            corner_radius=RADIUS["input"], font=FONT["label"],
            fg_color=self._c("input_bg"), text_color=self._c("text"),
            border_color=self._c("input_border"),
        ).pack(side="left", padx=SPACING["sm"])

        dry_row = ctk.CTkFrame(body, fg_color="transparent")
        dry_row.pack(fill="x", pady=(SPACING["md"], 0))
        dry_sw = ctk.CTkSwitch(
            dry_row, text="Modo Teste — simula sem apagar nada",
            variable=self.dry_run, font=FONT["label"], text_color=self._c("text"),
            progress_color=self._c("warning"),
            button_color="#ffffff", button_hover_color="#f3f4f6",
        )
        dry_sw.pack(anchor="w")

    def _browse_dev_root(self) -> None:
        folder = filedialog.askdirectory(title="Selecionar pasta de projetos")
        if folder:
            self.dev_search_root.set(folder)

    # ---- ações ------------------------------------------------------------

    def _build_actions(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=SPACING["md"])

        self.scan_btn = ctk.CTkButton(
            row, text="🔍  ANALISAR", command=self._start_scan,
            font=FONT["button_hero"], height=48, corner_radius=RADIUS["button"],
            fg_color=self._c("primary"), hover_color=self._c("primary_hover"),
            text_color="#ffffff",
        )
        self.scan_btn.pack(side="left", padx=(0, SPACING["sm"]), fill="x", expand=True)

        self.clean_btn = ctk.CTkButton(
            row, text="🧹  Limpar selecionadas", command=self._start_clean,
            font=FONT["button_hero"], height=48, corner_radius=RADIUS["button"],
            fg_color=self._c("danger"), hover_color=self._c("danger_hover"),
            text_color="#ffffff", state="disabled",
        )
        self.clean_btn.pack(side="left", fill="x", expand=True)

    # ---- progresso + stats --------------------------------------------

    def _build_progress_card(self, parent) -> None:
        card = self._card(parent, "Progresso")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        self.status_label = ctk.CTkLabel(
            top, text="Pronto.", font=FONT["label"],
            text_color=self._c("text_muted"), anchor="w",
        )
        self.status_label.pack(side="left")
        self.pct_label = ctk.CTkLabel(
            top, text="0%", font=FONT["section"], text_color=self._c("primary"),
        )
        self.pct_label.pack(side="right")

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ctk.CTkProgressBar(
            body, variable=self.progress_var, height=10,
            corner_radius=RADIUS["pill"],
            fg_color=self._c("progress_trough"), progress_color=self._c("progress_fill"),
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))

        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x")
        for i in range(4):
            stats.columnconfigure(i, weight=1, uniform="stat")

        self._stat_cards: Dict[str, ctk.CTkLabel] = {}
        specs = [
            ("found",   "Encontrados", "primary"),
            ("removed", "Removidos",   "success"),
            ("errors",  "Erros",       "danger"),
            ("freed",   "Liberado",    "accent"),
        ]
        for col, (key, label_text, color_key) in enumerate(specs):
            mini = ctk.CTkFrame(
                stats, fg_color=self._c("bg_alt"), corner_radius=RADIUS["button"],
                border_width=1, border_color=self._c("card_border"),
            )
            mini.grid(row=0, column=col, sticky="ew", padx=SPACING["xs"])
            value = ctk.CTkLabel(
                mini, text="0", font=FONT["stat_value"], text_color=self._c(color_key),
            )
            value.pack(pady=(SPACING["sm"], 0))
            ctk.CTkLabel(
                mini, text=label_text, font=FONT["stat_label"],
                text_color=self._c("text_muted"),
            ).pack(pady=(0, SPACING["sm"]))
            self._stat_cards[key] = value

    def _update_stats(self, found: int, removed: int, errors: int, freed: int) -> None:
        self._stat_cards["found"].configure(text=str(found))
        self._stat_cards["removed"].configure(text=str(removed))
        self._stat_cards["errors"].configure(text=str(errors))
        self._stat_cards["freed"].configure(text=human_bytes(freed))

    # ---- log ------------------------------------------------------------

    def _build_log_card(self, parent) -> None:
        card = self._card(parent, "Log")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))

        self.log_text = ctk.CTkTextbox(
            body, height=220, font=FONT["log"],
            fg_color=self._c("log_bg"), text_color=self._c("log_fg"),
            corner_radius=RADIUS["input"],
        )
        self.log_text.pack(fill="both", expand=True)
        self._configure_log_tags()

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(SPACING["sm"], 0))
        ctk.CTkButton(
            btn_row, text="Limpar log", command=self._clear_log,
            font=FONT["button"], height=32, width=120,
            corner_radius=RADIUS["button"],
            fg_color=self._c("neutral"), hover_color=self._c("neutral_hover"),
            text_color="#ffffff",
        ).pack(side="left")

    def _configure_log_tags(self) -> None:
        inner = self.log_text._textbox  # type: ignore[attr-defined]
        inner.tag_config("ok", foreground=self._c("log_ok"))
        inner.tag_config("error", foreground=self._c("log_error"))
        inner.tag_config("warning", foreground=self._c("log_warning"))
        inner.tag_config("dryrun", foreground=self._c("log_dryrun"))
        inner.tag_config("header", foreground=self._c("log_header"))
        inner.tag_config("info", foreground=self._c("log_info"))

    def _tag_for(self, line: str) -> str:
        if line.startswith("[OK]"):
            return "ok"
        if line.startswith("[ERRO]"):
            return "error"
        if line.startswith("[AVISO]"):
            return "warning"
        if line.startswith("[DRY-RUN]") or "MODO TESTE" in line:
            return "dryrun"
        if line.startswith("=") or line.startswith("Itens processados"):
            return "header"
        if line.startswith("ℹ️"):
            return "info"
        return ""

    def _log(self, message: str) -> None:
        tag = self._tag_for(message)
        inner = self.log_text._textbox  # type: ignore[attr-defined]
        inner.insert("end", message + "\n", tag)
        inner.see("end")

    def _clear_log(self) -> None:
        inner = self.log_text._textbox  # type: ignore[attr-defined]
        inner.delete("1.0", "end")

    # ------------------------------------------------------------------ log queue

    def _poll_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and len(item) == 3 and item[0] == "_progress":
                    _, current, total = item
                    pct = (current / total) if total else 1.0
                    self.progress_var.set(pct)
                    self.progress_bar.set(pct)
                    self.pct_label.configure(text=f"{int(pct * 100)}%")
                    self.status_label.configure(text=f"Processando {current} de {total}…")
                else:
                    self._log(str(item))
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------ estado

    def _set_running(self, running: bool) -> None:
        self.is_running = running
        state = "disabled" if running else "normal"
        self.scan_btn.configure(state=state)
        self.clean_btn.configure(state="disabled" if running or not self.scanned_items else "normal")
        if not running:
            self.status_label.configure(text="Pronto.")

    def _selected_categories(self) -> List[str]:
        return [key for key, var in self.cat_vars.items() if var.get()]

    def _parse_int(self, var: tk.StringVar, default: int) -> int:
        try:
            return max(0, int(var.get()))
        except ValueError:
            return default

    # ------------------------------------------------------------------ analisar

    def _start_scan(self) -> None:
        if self.is_running:
            return
        categories = self._selected_categories()
        if not categories:
            messagebox.showwarning("Aviso", "Selecione pelo menos uma categoria.")
            return
        self.progress_var.set(0)
        self.progress_bar.set(0)
        self.pct_label.configure(text="0%")
        self._set_running(True)
        self.status_label.configure(text="Analisando…")
        threading.Thread(target=self._scan_worker, args=(categories,), daemon=True).start()

    def _scan_worker(self, categories: List[str]) -> None:
        try:
            days = self._parse_int(self.old_downloads_days, 30)
            stale_days = self._parse_int(self.dev_stale_days, 60)
            dev_root_raw = self.dev_search_root.get().strip()
            dev_roots = [Path(dev_root_raw)] if dev_root_raw else []

            sep = "=" * 55
            self.log_queue.put(sep)
            self.log_queue.put(f"Analisando: {', '.join(CATEGORIES[c] for c in categories)}")
            self.log_queue.put(sep)

            items = scan_all(
                categories,
                old_downloads_days=days,
                dev_search_roots=dev_roots,
                dev_stale_days=stale_days,
            )
            self.scanned_items = items

            if not items:
                self.log_queue.put("ℹ️  Nada encontrado para limpar nas categorias selecionadas.")
            else:
                for item in items:
                    detail = f"  [{item.detail}]" if item.detail else ""
                    self.log_queue.put(
                        f"  {CATEGORIES[item.category]:<28} "
                        f"{human_bytes(item.size_bytes):>10}  {item.label}{detail}"
                    )
                total_size = sum(i.size_bytes for i in items)
                self.log_queue.put("")
                self.log_queue.put(
                    f"Itens processados: {len(items)} | total encontrado: {human_bytes(total_size)}"
                )

            self.after(0, lambda: self._update_stats(
                len(items), 0, 0, 0,
            ))
        except Exception as e:
            self.log_queue.put(f"[ERRO] {e}")
        finally:
            self.after(0, lambda: self._set_running(False))

    # ------------------------------------------------------------------ limpar

    def _start_clean(self) -> None:
        if self.is_running:
            return
        categories = set(self._selected_categories())
        if not categories:
            messagebox.showwarning("Aviso", "Selecione pelo menos uma categoria.")
            return
        targets = [i for i in self.scanned_items if i.category in categories]
        if not targets:
            messagebox.showinfo("Nada a limpar", "Clique em Analisar primeiro (ou nada foi encontrado).")
            return

        total_size = sum(i.size_bytes for i in targets)
        if not self.dry_run.get():
            confirmed = messagebox.askyesno(
                "Confirmar limpeza",
                f"Remover {len(targets)} item(ns), liberando {human_bytes(total_size)}?\n\n"
                "Esta ação não pode ser desfeita.",
            )
            if not confirmed:
                return

        self.progress_var.set(0)
        self.progress_bar.set(0)
        self.pct_label.configure(text="0%")
        self._set_running(True)
        self.status_label.configure(text="Limpando…")
        threading.Thread(target=self._clean_worker, args=(targets,), daemon=True).start()

    def _clean_worker(self, targets: List[CleanItem]) -> None:
        try:
            sep = "=" * 55
            self.log_queue.put(sep)
            if self.dry_run.get():
                self.log_queue.put("*** MODO TESTE — nenhum arquivo será alterado ***")
            self.log_queue.put(sep)

            def progress_cb(current: int, total: int) -> None:
                self.log_queue.put(("_progress", current, total))

            report, freed, removed, errors = clean(
                targets, dry_run=self.dry_run.get(), progress_cb=progress_cb,
            )
            for line in report.split("\n"):
                if line.strip():
                    self.log_queue.put(line)

            self.after(0, lambda: self._update_stats(len(targets), removed, errors, freed))

            if errors > 0:
                self.log_queue.put(f"[AVISO] Concluído com {errors} erro(s).")
            elif removed > 0:
                self.log_queue.put(f"[OK] {removed} item(ns) processado(s) com sucesso!")
        except Exception as e:
            self.log_queue.put(f"[ERRO] {e}")
        finally:
            self.after(0, lambda: (self.progress_var.set(1.0),
                                   self.progress_bar.set(1.0),
                                   self.pct_label.configure(text="100%")))
            self.after(0, lambda: self._set_running(False))
