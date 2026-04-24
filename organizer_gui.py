#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interface gráfica moderna do Organizador de Arquivos (CustomTkinter)."""

from __future__ import annotations

import json
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional

try:
    import customtkinter as ctk
except ImportError as exc:  # pragma: no cover - orientação ao usuário
    raise SystemExit(
        "customtkinter não está instalado.\n"
        "Instale as dependências com: pip install -r requirements.txt"
    ) from exc

from organizer import DEFAULT_MAP, load_map, organize
from theme import (
    FONT,
    LIGHT,
    DARK,
    HEADER_BAR_HEIGHT,
    RADIUS,
    SPACING,
    ThemeName,
    load_theme,
    palette,
    save_theme,
)

PROJECT_ROOT = Path(__file__).resolve().parent
ICON_PATH = PROJECT_ROOT / "assets" / "organizer.ico"
MAX_RECENT = 8


# ---------------------------------------------------------------------------
# Tooltip leve, compatível com widgets do CustomTkinter e Tk
# ---------------------------------------------------------------------------


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
            frame,
            text=self._text,
            bg=bg,
            fg=fg,
            font=FONT["small"],
            padx=8,
            pady=4,
            justify="left",
        ).pack()

    def _hide(self, _event=None):
        if self._win:
            self._win.destroy()
            self._win = None


# ---------------------------------------------------------------------------
# Aplicação principal
# ---------------------------------------------------------------------------


class OrganizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.theme_name: ThemeName = load_theme("dark")
        ctk.set_appearance_mode(self.theme_name)
        ctk.set_default_color_theme("blue")

        self.title("Organizador de Arquivos")
        self.geometry("960x780")
        self.minsize(860, 720)

        self._apply_window_icon()

        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar()
        self.mode = tk.StringVar(value="move")
        self.dry_run = tk.BooleanVar(value=True)
        self.delete_empty = tk.BooleanVar(value=False)
        self.unknown_name = tk.StringVar(value="Outros")
        self.config_path = tk.StringVar()

        self._recent_src: List[str] = []
        self._recent_dst: List[str] = []

        self.log_queue: queue.Queue = queue.Queue()
        self.is_organizing = False
        self._stop_event = threading.Event()

        # Widgets sensíveis ao tema (registrados para repaint no toggle)
        self._themed: List[tuple] = []
        self._tooltips_palette: dict = dict(palette(self.theme_name))

        self.configure(fg_color=self._c("bg"))

        self._build_ui()
        self._bind_shortcuts()
        self._poll_log_queue()

    # ------------------------------------------------------------------ infra

    def _c(self, key: str) -> str:
        return palette(self.theme_name)[key]

    def _pair(self, key: str) -> tuple[str, str]:
        """Par (light, dark) para passar ao CustomTkinter."""
        return (LIGHT[key], DARK[key])

    def _themed_register(self, widget, **mapping) -> None:
        """Registra um widget para ter cores atualizadas no toggle de tema.

        `mapping` faz prop -> chave da paleta ("fg_color", "text_color", etc.).
        """
        self._themed.append((widget, mapping))

    def _apply_window_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        try:
            if sys.platform == "win32":
                self.iconbitmap(str(ICON_PATH))
            else:
                png = ICON_PATH.with_suffix(".png")
                if png.exists():
                    self.iconphoto(True, tk.PhotoImage(file=str(png)))
        except Exception:
            pass

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        self._build_header()

        main = ctk.CTkScrollableFrame(
            self,
            fg_color=self._pair("bg"),
            corner_radius=0,
        )
        main.pack(fill="both", expand=True, padx=SPACING["lg"], pady=(0, SPACING["md"]))

        self._build_paths_card(main)
        self._build_options_card(main)
        self._build_actions(main)
        self._build_progress_card(main)
        self._build_log_card(main)

    # ---- header -----------------------------------------------------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self,
            fg_color=self._pair("header_from"),
            corner_radius=0,
            height=HEADER_BAR_HEIGHT,
        )
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        self._themed_register(header, fg_color="header_from")

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(
            fill="both",
            expand=True,
            padx=SPACING["md"],
            pady=SPACING["xs"],
        )

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y")

        title = ctk.CTkLabel(
            left,
            text="Organizador de Arquivos",
            text_color="#ffffff",
            font=FONT["header_title"],
            anchor="w",
        )
        title.pack(anchor="w", pady=(0, 0))

        subtitle = ctk.CTkLabel(
            left,
            text="Ordene em segundos — simples e seguro.",
            text_color="#c7d2fe",
            font=FONT["header_subtitle"],
            anchor="w",
        )
        subtitle.pack(anchor="w", pady=(0, 0))

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", fill="y")

        self._theme_btn = ctk.CTkButton(
            right,
            text=self._theme_btn_text(),
            width=30,
            height=30,
            corner_radius=15,
            font=(FONT["button"][0], 14),
            fg_color=self._pair("header_chip"),
            hover_color=self._pair("header_chip_hover"),
            text_color="#ffffff",
            border_width=0,
            command=self._toggle_theme,
        )
        self._themed_register(
            self._theme_btn,
            fg_color="header_chip",
            hover_color="header_chip_hover",
        )
        self._theme_btn.pack(side="right")
        _Tooltip(
            self._theme_btn,
            "Alternar tema claro/escuro",
            self._tooltips_palette,
        )

    def _theme_btn_text(self) -> str:
        return "☀" if self.theme_name == "dark" else "🌙"

    # ---- cards helpers ----------------------------------------------------

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=self._pair("card"),
            corner_radius=RADIUS["card"],
            border_width=1,
            border_color=self._pair("card_border"),
        )
        card.pack(fill="x", pady=(SPACING["md"], 0))
        self._themed_register(card, fg_color="card", border_color="card_border")

        header = ctk.CTkLabel(
            card,
            text=title,
            font=FONT["section"],
            text_color=self._pair("text"),
            anchor="w",
        )
        header.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["md"], 0))
        self._themed_register(header, text_color="text")
        return card

    def _separator(self, parent) -> None:
        div = ctk.CTkFrame(parent, fg_color=self._pair("divider"), height=1)
        div.pack(fill="x", padx=SPACING["lg"], pady=SPACING["sm"])
        self._themed_register(div, fg_color="divider")

    # ---- pastas -----------------------------------------------------------

    def _build_paths_card(self, parent) -> None:
        card = self._card(parent, "Pastas")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))
        body.columnconfigure(1, weight=1)

        self._src_combo = self._add_path_row(
            body, 0, "Origem",
            self.source_path, self._recent_src,
            self._browse_source,
            "Pasta que será organizada",
        )
        self._dst_combo = self._add_path_row(
            body, 1, "Destino",
            self.dest_path, self._recent_dst,
            self._browse_dest,
            "Onde os arquivos serão colocados",
        )

        # Linha do JSON de configuração
        label = ctk.CTkLabel(
            body, text="Config JSON", font=FONT["label"],
            text_color=self._pair("text_muted"), anchor="w", width=90,
        )
        label.grid(row=2, column=0, padx=(0, SPACING["sm"]), pady=SPACING["sm"], sticky="w")
        self._themed_register(label, text_color="text_muted")

        cfg_entry = ctk.CTkEntry(
            body,
            textvariable=self.config_path,
            font=FONT["label"],
            height=36,
            corner_radius=RADIUS["input"],
            fg_color=self._pair("input_bg"),
            text_color=self._pair("text"),
            border_color=self._pair("input_border"),
            placeholder_text="Opcional — arquivo JSON de categorias personalizadas",
        )
        cfg_entry.grid(row=2, column=1, padx=SPACING["xs"], pady=SPACING["sm"], sticky="ew")
        self._themed_register(cfg_entry, fg_color="input_bg", text_color="text", border_color="input_border")

        cfg_btn = self._secondary_button(
            body, "Procurar", self._browse_config, tip="Selecionar arquivo JSON de mapeamento",
        )
        cfg_btn.grid(row=2, column=2, padx=(SPACING["xs"], 0), pady=SPACING["sm"])

    def _add_path_row(
        self, parent, row: int, label_text: str,
        var: tk.StringVar, recents: List[str], cmd, tip_text: str,
    ) -> ctk.CTkComboBox:
        label = ctk.CTkLabel(
            parent,
            text=label_text,
            font=FONT["label"],
            text_color=self._pair("text_muted"),
            anchor="w",
            width=90,
        )
        label.grid(row=row, column=0, padx=(0, SPACING["sm"]), pady=SPACING["sm"], sticky="w")
        self._themed_register(label, text_color="text_muted")

        combo = ctk.CTkComboBox(
            parent,
            variable=var,
            values=recents,
            font=FONT["label"],
            height=36,
            corner_radius=RADIUS["input"],
            fg_color=self._pair("input_bg"),
            text_color=self._pair("text"),
            border_color=self._pair("input_border"),
            button_color=self._pair("primary"),
            button_hover_color=self._pair("primary_hover"),
            dropdown_fg_color=self._pair("card"),
            dropdown_text_color=self._pair("text"),
            dropdown_hover_color=self._pair("bg_alt"),
        )
        combo.grid(row=row, column=1, padx=SPACING["xs"], pady=SPACING["sm"], sticky="ew")
        self._themed_register(
            combo,
            fg_color="input_bg", text_color="text", border_color="input_border",
            button_color="primary", button_hover_color="primary_hover",
            dropdown_fg_color="card", dropdown_text_color="text",
            dropdown_hover_color="bg_alt",
        )

        btn = self._primary_button(parent, "Procurar", cmd, tip=tip_text, width=110)
        btn.grid(row=row, column=2, padx=(SPACING["xs"], 0), pady=SPACING["sm"])
        return combo

    # ---- opções -----------------------------------------------------------

    def _build_options_card(self, parent) -> None:
        card = self._card(parent, "Opções")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))

        # Modo (segmented control)
        mode_row = ctk.CTkFrame(body, fg_color="transparent")
        mode_row.pack(fill="x", pady=(0, SPACING["md"]))

        mode_label = ctk.CTkLabel(
            mode_row, text="Modo", font=FONT["label"],
            text_color=self._pair("text_muted"), anchor="w", width=90,
        )
        mode_label.pack(side="left")
        self._themed_register(mode_label, text_color="text_muted")

        seg = ctk.CTkSegmentedButton(
            mode_row,
            values=["Mover", "Copiar"],
            height=34,
            corner_radius=RADIUS["button"],
            font=FONT["label"],
            fg_color=self._pair("bg_alt"),
            selected_color=self._pair("primary"),
            selected_hover_color=self._pair("primary_hover"),
            unselected_color=self._pair("bg_alt"),
            unselected_hover_color=self._pair("divider"),
            text_color=self._pair("text"),
            command=self._on_mode_change,
        )
        seg.set("Mover")
        seg.pack(side="left", padx=SPACING["sm"])
        self._themed_register(
            seg,
            fg_color="bg_alt",
            selected_color="primary",
            selected_hover_color="primary_hover",
            unselected_color="bg_alt",
            unselected_hover_color="divider",
            text_color="text",
        )
        self._mode_segment = seg

        mode_tip = ctk.CTkLabel(
            mode_row,
            text="'Mover' remove os originais; 'Copiar' mantém tudo intacto.",
            font=FONT["small"],
            text_color=self._pair("text_muted"),
        )
        mode_tip.pack(side="left", padx=SPACING["md"])
        self._themed_register(mode_tip, text_color="text_muted")

        # Toggles (switches)
        toggles = ctk.CTkFrame(body, fg_color="transparent")
        toggles.pack(fill="x", pady=(0, SPACING["md"]))

        dry_sw = ctk.CTkSwitch(
            toggles,
            text="Modo Teste — simula sem modificar nada",
            variable=self.dry_run,
            font=FONT["label"],
            text_color=self._pair("text"),
            progress_color=self._pair("warning"),
            button_color="#ffffff",
            button_hover_color="#f3f4f6",
        )
        dry_sw.pack(anchor="w", pady=SPACING["xs"])
        self._themed_register(dry_sw, text_color="text", progress_color="warning")

        empty_sw = ctk.CTkSwitch(
            toggles,
            text="Remover subpastas vazias após organizar",
            variable=self.delete_empty,
            font=FONT["label"],
            text_color=self._pair("text"),
            progress_color=self._pair("primary"),
            button_color="#ffffff",
            button_hover_color="#f3f4f6",
        )
        empty_sw.pack(anchor="w", pady=SPACING["xs"])
        self._themed_register(empty_sw, text_color="text", progress_color="primary")

        # Pasta para desconhecidos
        unk_row = ctk.CTkFrame(body, fg_color="transparent")
        unk_row.pack(fill="x")

        unk_label = ctk.CTkLabel(
            unk_row,
            text="Pasta para tipos não reconhecidos",
            font=FONT["label"],
            text_color=self._pair("text_muted"),
        )
        unk_label.pack(side="left")
        self._themed_register(unk_label, text_color="text_muted")

        unk_entry = ctk.CTkEntry(
            unk_row,
            textvariable=self.unknown_name,
            width=180,
            height=32,
            corner_radius=RADIUS["input"],
            font=FONT["label"],
            fg_color=self._pair("input_bg"),
            text_color=self._pair("text"),
            border_color=self._pair("input_border"),
        )
        unk_entry.pack(side="left", padx=SPACING["sm"])
        self._themed_register(unk_entry, fg_color="input_bg", text_color="text", border_color="input_border")

    def _on_mode_change(self, value: str) -> None:
        self.mode.set("copy" if value == "Copiar" else "move")

    # ---- botões de ação ---------------------------------------------------

    def _build_actions(self, parent) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=SPACING["md"])

        self.organize_btn = ctk.CTkButton(
            row,
            text="▶  ORGANIZAR",
            command=self._start_organize,
            font=FONT["button_hero"],
            height=48,
            corner_radius=RADIUS["button"],
            fg_color=self._pair("success"),
            hover_color=self._pair("success_hover"),
            text_color="#ffffff",
        )
        self.organize_btn.pack(side="left", padx=(0, SPACING["sm"]), fill="x", expand=True)
        self._themed_register(self.organize_btn, fg_color="success", hover_color="success_hover")
        _Tooltip(self.organize_btn, "Iniciar organização  [F5]", self._tooltips_palette)

        self.cancel_btn = ctk.CTkButton(
            row,
            text="✕  Cancelar",
            command=self._cancel,
            font=FONT["button"],
            height=48,
            width=130,
            corner_radius=RADIUS["button"],
            fg_color=self._pair("danger"),
            hover_color=self._pair("danger_hover"),
            text_color="#ffffff",
            state="disabled",
        )
        self.cancel_btn.pack(side="left", padx=SPACING["xs"])
        self._themed_register(self.cancel_btn, fg_color="danger", hover_color="danger_hover")
        _Tooltip(self.cancel_btn, "Cancelar operação em curso  [Esc]", self._tooltips_palette)

        secondary_row = ctk.CTkFrame(parent, fg_color="transparent")
        secondary_row.pack(fill="x", pady=(0, SPACING["xs"]))

        clear_btn = self._neutral_button(
            secondary_row, "Limpar log", self._clear_log,
            tip="Limpar conteúdo do log  [Ctrl+L]", width=130,
        )
        clear_btn.pack(side="left", padx=(0, SPACING["xs"]))

        save_btn = self._secondary_button(
            secondary_row, "Salvar log", self._save_log,
            tip="Salvar log em arquivo  [Ctrl+S]", width=130,
        )
        save_btn.pack(side="left", padx=SPACING["xs"])

        cfg_btn = self._accent_button(
            secondary_row, "Ver config padrão", self._show_default_config,
            tip="Exibe o mapeamento padrão de extensões", width=170,
        )
        cfg_btn.pack(side="left", padx=SPACING["xs"])

    # ---- botões helpers ---------------------------------------------------

    def _primary_button(self, parent, text, cmd, *, tip="", width=110):
        btn = ctk.CTkButton(
            parent, text=text, command=cmd,
            font=FONT["button"], height=36, width=width,
            corner_radius=RADIUS["button"],
            fg_color=self._pair("primary"),
            hover_color=self._pair("primary_hover"),
            text_color="#ffffff",
        )
        self._themed_register(btn, fg_color="primary", hover_color="primary_hover")
        if tip:
            _Tooltip(btn, tip, self._tooltips_palette)
        return btn

    def _secondary_button(self, parent, text, cmd, *, tip="", width=110):
        btn = ctk.CTkButton(
            parent, text=text, command=cmd,
            font=FONT["button"], height=36, width=width,
            corner_radius=RADIUS["button"],
            fg_color=self._pair("warning"),
            hover_color=self._pair("warning_hover"),
            text_color="#ffffff",
        )
        self._themed_register(btn, fg_color="warning", hover_color="warning_hover")
        if tip:
            _Tooltip(btn, tip, self._tooltips_palette)
        return btn

    def _neutral_button(self, parent, text, cmd, *, tip="", width=110):
        btn = ctk.CTkButton(
            parent, text=text, command=cmd,
            font=FONT["button"], height=36, width=width,
            corner_radius=RADIUS["button"],
            fg_color=self._pair("neutral"),
            hover_color=self._pair("neutral_hover"),
            text_color="#ffffff",
        )
        self._themed_register(btn, fg_color="neutral", hover_color="neutral_hover")
        if tip:
            _Tooltip(btn, tip, self._tooltips_palette)
        return btn

    def _accent_button(self, parent, text, cmd, *, tip="", width=130):
        btn = ctk.CTkButton(
            parent, text=text, command=cmd,
            font=FONT["button"], height=36, width=width,
            corner_radius=RADIUS["button"],
            fg_color=self._pair("accent"),
            hover_color=self._pair("accent_hover"),
            text_color="#ffffff",
        )
        self._themed_register(btn, fg_color="accent", hover_color="accent_hover")
        if tip:
            _Tooltip(btn, tip, self._tooltips_palette)
        return btn

    # ---- progresso + stat cards ------------------------------------------

    def _build_progress_card(self, parent) -> None:
        card = self._card(parent, "Progresso")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")

        self.status_label = ctk.CTkLabel(
            top, text="Pronto.", font=FONT["label"],
            text_color=self._pair("text_muted"), anchor="w",
        )
        self.status_label.pack(side="left")
        self._themed_register(self.status_label, text_color="text_muted")

        self.pct_label = ctk.CTkLabel(
            top, text="0%", font=FONT["section"],
            text_color=self._pair("primary"),
        )
        self.pct_label.pack(side="right")
        self._themed_register(self.pct_label, text_color="primary")

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ctk.CTkProgressBar(
            body,
            variable=self.progress_var,
            height=10,
            corner_radius=RADIUS["pill"],
            fg_color=self._pair("progress_trough"),
            progress_color=self._pair("progress_fill"),
        )
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", pady=(SPACING["sm"], SPACING["md"]))
        self._themed_register(self.progress_bar, fg_color="progress_trough", progress_color="progress_fill")

        stats = ctk.CTkFrame(body, fg_color="transparent")
        stats.pack(fill="x")
        for i in range(4):
            stats.columnconfigure(i, weight=1, uniform="stat")

        self._stat_cards: Dict[str, Dict[str, ctk.CTkLabel]] = {}
        specs = [
            ("total",    "Total",        "primary"),
            ("moved",    "Organizados",  "success"),
            ("skipped",  "Pulados",      "warning"),
            ("errors",   "Erros",        "danger"),
        ]
        for col, (key, label_text, color_key) in enumerate(specs):
            mini = ctk.CTkFrame(
                stats,
                fg_color=self._pair("bg_alt"),
                corner_radius=RADIUS["button"],
                border_width=1,
                border_color=self._pair("card_border"),
            )
            mini.grid(row=0, column=col, padx=SPACING["xs"], sticky="ew")
            self._themed_register(mini, fg_color="bg_alt", border_color="card_border")

            value_lbl = ctk.CTkLabel(
                mini, text="—", font=FONT["stat_value"],
                text_color=self._pair(color_key),
            )
            value_lbl.pack(pady=(SPACING["sm"], 0))
            self._themed_register(value_lbl, text_color=color_key)

            text_lbl = ctk.CTkLabel(
                mini, text=label_text, font=FONT["stat_label"],
                text_color=self._pair("text_muted"),
            )
            text_lbl.pack(pady=(0, SPACING["sm"]))
            self._themed_register(text_lbl, text_color="text_muted")

            self._stat_cards[key] = {"value": value_lbl, "label": text_lbl}

    # ---- log --------------------------------------------------------------

    def _build_log_card(self, parent) -> None:
        card = self._card(parent, "Log de Operações")

        body = ctk.CTkFrame(
            card,
            fg_color=self._pair("log_bg"),
            corner_radius=RADIUS["input"],
        )
        body.pack(fill="both", expand=True,
                  padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["lg"]))
        self._themed_register(body, fg_color="log_bg")

        self.log_text = ctk.CTkTextbox(
            body,
            height=220,
            font=FONT["log"],
            fg_color=self._pair("log_bg"),
            text_color=self._pair("log_fg"),
            corner_radius=RADIUS["input"],
            wrap="none",
        )
        self.log_text.pack(fill="both", expand=True, padx=SPACING["sm"], pady=SPACING["sm"])
        self._themed_register(self.log_text, fg_color="log_bg", text_color="log_fg")
        self._configure_log_tags()

    def _configure_log_tags(self) -> None:
        txt = self.log_text
        # CTkTextbox delega tags para o tk.Text interno
        inner = txt._textbox  # type: ignore[attr-defined]
        tags = [
            ("ok",       self._c("log_ok"),      False),
            ("error",    self._c("log_error"),   True),
            ("warning",  self._c("log_warning"), False),
            ("dryrun",   self._c("log_dryrun"),  False),
            ("header",   self._c("log_header"),  True),
            ("info",     self._c("log_info"),    False),
        ]
        for tag, color, bold in tags:
            cfg: dict = {"foreground": color}
            if bold:
                cfg["font"] = (FONT["log"][0], FONT["log"][1], "bold")
            inner.tag_configure(tag, **cfg)

    # ------------------------------------------------------------------ atalhos

    def _bind_shortcuts(self) -> None:
        self.bind("<F5>", lambda _e: self._start_organize())
        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Control-l>", lambda _e: self._clear_log())
        self.bind("<Control-L>", lambda _e: self._clear_log())
        self.bind("<Control-s>", lambda _e: self._save_log())
        self.bind("<Control-S>", lambda _e: self._save_log())

    # ------------------------------------------------------------------ tema

    def _toggle_theme(self) -> None:
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        save_theme(self.theme_name)
        ctk.set_appearance_mode(self.theme_name)
        self._repaint_all()

    def _repaint_all(self) -> None:
        # Atualiza paleta das tooltips
        self._tooltips_palette.clear()
        self._tooltips_palette.update(palette(self.theme_name))

        self.configure(fg_color=self._c("bg"))
        self._theme_btn.configure(text=self._theme_btn_text())

        for widget, mapping in self._themed:
            try:
                kwargs = {prop: self._c(key) for prop, key in mapping.items()}
                widget.configure(**kwargs)
            except Exception:
                continue

        self._configure_log_tags()

    # ------------------------------------------------------------------ log queue

    def _poll_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if (
                    isinstance(item, tuple)
                    and len(item) == 3
                    and item[0] == "_progress"
                ):
                    _, current, total = item
                    pct = (current / total) if total else 1.0
                    self.progress_var.set(pct)
                    self.progress_bar.set(pct)
                    self.pct_label.configure(text=f"{int(pct * 100)}%")
                    self.status_label.configure(
                        text=f"Processando {current} de {total}…"
                    )
                else:
                    self._log(str(item))
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def _log(self, message: str) -> None:
        tag = self._tag_for(message)
        inner = self.log_text._textbox  # type: ignore[attr-defined]
        inner.insert("end", message + "\n", tag)
        inner.see("end")

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

    # ------------------------------------------------------------------ recentes

    def _push_recent(self, path: str, lst: List[str], combo: ctk.CTkComboBox) -> None:
        if path in lst:
            lst.remove(path)
        lst.insert(0, path)
        del lst[MAX_RECENT:]
        combo.configure(values=lst)

    # ------------------------------------------------------------------ browse

    def _browse_source(self) -> None:
        folder = filedialog.askdirectory(title="Selecionar pasta de origem")
        if folder:
            self.source_path.set(folder)
            self._push_recent(folder, self._recent_src, self._src_combo)
            if not self.dest_path.get():
                self.dest_path.set(folder)
                self._push_recent(folder, self._recent_dst, self._dst_combo)

    def _browse_dest(self) -> None:
        folder = filedialog.askdirectory(title="Selecionar pasta de destino")
        if folder:
            self.dest_path.set(folder)
            self._push_recent(folder, self._recent_dst, self._dst_combo)

    def _browse_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecionar arquivo de configuração JSON",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if path:
            self.config_path.set(path)

    # ------------------------------------------------------------------ log ops

    def _clear_log(self) -> None:
        inner = self.log_text._textbox  # type: ignore[attr-defined]
        inner.delete("1.0", "end")

    def _save_log(self) -> None:
        inner = self.log_text._textbox  # type: ignore[attr-defined]
        content = inner.get("1.0", "end")
        if not content.strip():
            messagebox.showwarning("Aviso", "O log está vazio!")
            return
        path = filedialog.asksaveasfilename(
            title="Salvar log",
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if path:
            try:
                Path(path).write_text(content, encoding="utf-8")
                messagebox.showinfo("Sucesso", f"Log salvo em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    def _show_default_config(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Configuração padrão de extensões")
        win.geometry("720x520")
        win.configure(fg_color=self._c("bg"))
        try:
            if sys.platform == "win32" and ICON_PATH.exists():
                win.after(200, lambda: win.iconbitmap(str(ICON_PATH)))
        except Exception:
            pass

        header = ctk.CTkLabel(
            win, text="Configuração padrão de extensões",
            font=FONT["title"], text_color=self._c("text"),
        )
        header.pack(pady=(SPACING["md"], SPACING["sm"]))

        config_json = json.dumps(DEFAULT_MAP, indent=2, ensure_ascii=False)
        txt = ctk.CTkTextbox(
            win,
            font=FONT["log"],
            fg_color=self._c("log_bg"),
            text_color=self._c("log_fg"),
            corner_radius=RADIUS["input"],
        )
        txt.pack(fill="both", expand=True,
                 padx=SPACING["lg"], pady=SPACING["sm"])
        txt.insert("1.0", config_json)
        txt.configure(state="disabled")

        footer = ctk.CTkFrame(win, fg_color="transparent")
        footer.pack(fill="x", padx=SPACING["lg"], pady=SPACING["md"])

        save_btn = ctk.CTkButton(
            footer,
            text="Salvar como…",
            command=lambda: self._save_config_file(config_json),
            font=FONT["button"], height=40,
            corner_radius=RADIUS["button"],
            fg_color=self._c("success"), hover_color=self._c("success_hover"),
            text_color="#ffffff",
        )
        save_btn.pack(side="right")

        close_btn = ctk.CTkButton(
            footer, text="Fechar", command=win.destroy,
            font=FONT["button"], height=40, width=120,
            corner_radius=RADIUS["button"],
            fg_color=self._c("neutral"), hover_color=self._c("neutral_hover"),
            text_color="#ffffff",
        )
        close_btn.pack(side="right", padx=SPACING["xs"])

    def _save_config_file(self, config_json: str) -> None:
        path = filedialog.asksaveasfilename(
            title="Salvar configuração",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
        )
        if path:
            try:
                Path(path).write_text(config_json, encoding="utf-8")
                messagebox.showinfo("Sucesso", f"Configuração salva em:\n{path}")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    # ------------------------------------------------------------------ organizar

    def _cancel(self) -> None:
        if self.is_organizing:
            self._stop_event.set()
            self.log_queue.put("⚠️  Operação cancelada pelo usuário.")
            self._set_ui_state(organizing=False)

    def _set_ui_state(self, *, organizing: bool) -> None:
        self.is_organizing = organizing
        if organizing:
            self.organize_btn.configure(state="disabled", text="Organizando…")
            self.cancel_btn.configure(state="normal")
            self.progress_var.set(0)
            self.progress_bar.set(0)
            self.pct_label.configure(text="0%")
            self.status_label.configure(text="Iniciando…")
        else:
            self.organize_btn.configure(state="normal", text="▶  ORGANIZAR")
            self.cancel_btn.configure(state="disabled")
            self.status_label.configure(text="Pronto.")

    def _update_stats(self, total: int, moved: int, skipped: int, errors: int) -> None:
        self._stat_cards["total"]["value"].configure(text=str(total))
        self._stat_cards["moved"]["value"].configure(text=str(moved))
        self._stat_cards["skipped"]["value"].configure(text=str(skipped))
        self._stat_cards["errors"]["value"].configure(text=str(errors))

    def _start_organize(self) -> None:
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

    def _organize_worker(self) -> None:
        try:
            source = Path(self.source_path.get())
            dest = Path(self.dest_path.get())
            cfgp = Path(self.config_path.get()) if self.config_path.get() else None
            ext_map = load_map(cfgp)

            sep = "=" * 55
            self.log_queue.put(sep)
            self.log_queue.put("Iniciando organização...")
            self.log_queue.put(f"Origem:  {source}")
            self.log_queue.put(f"Destino: {dest}")
            self.log_queue.put(
                f"Modo:    {'Mover' if self.mode.get() == 'move' else 'Copiar'}"
            )
            if self.dry_run.get():
                self.log_queue.put("*** MODO TESTE — nenhum arquivo será alterado ***")
            self.log_queue.put(sep)

            def progress_cb(current: int, total: int) -> None:
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
            self.after(
                0, lambda: self._update_stats(total_count, moved, skipped, errors)
            )

            if errors > 0:
                self.log_queue.put(f"⚠️  Concluído com {errors} erro(s).")
            elif moved > 0:
                self.log_queue.put(f"✅  {moved} item(ns) organizados com sucesso!")
            else:
                self.log_queue.put("ℹ️  Nenhum item foi processado.")

        except Exception as e:
            self.log_queue.put(f"❌  Erro: {e}")
        finally:
            self.after(0, lambda: (self.progress_var.set(1.0),
                                   self.progress_bar.set(1.0),
                                   self.pct_label.configure(text="100%")))
            self.after(0, lambda: self._set_ui_state(organizing=False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app = OrganizerApp()

    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        src = str(downloads)
        app.source_path.set(src)
        app.dest_path.set(src)
        app._push_recent(src, app._recent_src, app._src_combo)
        app._push_recent(src, app._recent_dst, app._dst_combo)

    app.mainloop()


if __name__ == "__main__":
    main()
