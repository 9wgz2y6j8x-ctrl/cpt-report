"""
cpt_cleaning_view.py

Vue fonctionnelle FILTRER integree a l'application principale.
Reprend le design de cpt_cleaning_design.py, alimentee par les vraies
donnees via gef_reader.py, despike_cleaning.py et cpt_plot.py.

Navigation:
- Fleches Haut/Bas : Defiler entre les sondages
- Espace : Activer/Desactiver le filtrage automatique
"""

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator
import pandas as pd
import numpy as np
import threading
from pathlib import Path
from typing import Optional

from gef_reader import read_gef_to_dataframe, GefFileError
from despike_cleaning import hampel_peak_filter_aggressive
from cpt_plot import CPTPlotConfig, _resolve_column_name
from tabular_reader import load_cpt_dataframe

# ---------------------------------------------------------------------------
# Palette et typographie (identiques a la maquette)
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#E8EDF2",
    "card": "#F5F7FA",
    "sidebar": "#DFE4E9",
    "accent": "#0115B8",
    "success": "#16A34A",
    "text_primary": "#1A1A1A",
    "text_secondary": "#6B7280",
    "text_tertiary": "#9CA3AF",
    "selected_bg": "#C7D7E8",
    "divider": "#CBD5E1",
}

FONTS = {
    "title": ("Verdana", 18, "bold"),
    "subtitle": ("Verdana", 13, "bold"),
    "header_job": ("Verdana", 13, "bold"),
    "header_test": ("Verdana", 13),
    "header_file": ("Verdana", 12),
    "list_item": ("Verdana", 11),
    "list_item_bold": ("Verdana", 11, "bold"),
    "body": ("Verdana", 12),
    "small": ("Verdana", 10),
    "tiny": ("Verdana", 9),
}


# ---------------------------------------------------------------------------
# Adapter layer : RawDataManager -> donnees exploitables par la vue
# ---------------------------------------------------------------------------

class CPTFileEntry:
    """Representation d'un essai CPT pour la vue FILTRER.

    Charge les donnees GEF a la demande (lazy) et fournit un DataFrame
    brut + filtre conforme a ce qu'attend le diagramme.
    """

    def __init__(self, file_data: dict, raw_data_manager):
        self.file_path: str = file_data.get("file_path", "")
        self.filename: str = file_data.get("file_name", Path(self.file_path).name)
        self.job_number: str = raw_data_manager.get_effective_value(self.file_path, "Job Number")
        self.test_number: str = raw_data_manager.get_effective_value(self.file_path, "TestNumber")
        self.location: str = raw_data_manager.get_effective_value(self.file_path, "Location")
        self.source_type: str = file_data.get("source_type", "gef")
        self._file_data: dict = file_data

        self.is_filtered: bool = False

        # DataFrames (charges a la demande)
        self._df_raw: Optional[pd.DataFrame] = None
        self._df_filtered: Optional[pd.DataFrame] = None
        self._load_error: Optional[str] = None
        self._col_depth: Optional[str] = None
        self._col_qc: Optional[str] = None
        self._col_qst: Optional[str] = None

    # -- chargement paresseux -------------------------------------------------

    def ensure_loaded(self):
        """Charge le fichier (GEF ou tabulaire) si ce n'est pas deja fait. Retourne True si OK."""
        if self._df_raw is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            df = load_cpt_dataframe(self._file_data)
            if df.empty:
                self._load_error = "DataFrame vide"
                return False

            # Resolution des colonnes via la config par defaut de cpt_plot
            cfg = CPTPlotConfig()
            self._col_depth = _resolve_column_name(df, cfg.col_depth, "col_depth")
            self._col_qc = _resolve_column_name(df, cfg.col_qc, "col_qc")
            self._col_qst = _resolve_column_name(df, cfg.col_qst, "col_qst")

            self._df_raw = df
            return True
        except (GefFileError, ValueError, TypeError) as exc:
            self._load_error = str(exc)
            return False

    def _build_filtered(self):
        """Applique le filtre Hampel sur les colonnes qc et qst."""
        if self._df_raw is None:
            return
        if self._df_filtered is not None:
            return

        try:
            col_qc_idx = list(self._df_raw.columns).index(self._col_qc)
            col_qst_idx = list(self._df_raw.columns).index(self._col_qst)

            df_filt, _stats = hampel_peak_filter_aggressive(
                self._df_raw,
                columns=[col_qc_idx, col_qst_idx],
                window_size=4,
                k=1.9,
                method='linear',
                multi_pass=True,
                verbose=False,
            )
            self._df_filtered = df_filt
        except Exception as exc:
            print(f"Erreur filtrage {self.filename}: {exc}")
            self._df_filtered = self._df_raw.copy()

    # -- acces aux donnees pour le tracage ------------------------------------

    @property
    def df_raw(self) -> Optional[pd.DataFrame]:
        self.ensure_loaded()
        return self._df_raw

    @property
    def df_filtered(self) -> Optional[pd.DataFrame]:
        self.ensure_loaded()
        self._build_filtered()
        return self._df_filtered

    @property
    def col_depth(self):
        self.ensure_loaded()
        return self._col_depth

    @property
    def col_qc(self):
        self.ensure_loaded()
        return self._col_qc

    @property
    def col_qst(self):
        self.ensure_loaded()
        return self._col_qst

    @property
    def load_error(self):
        return self._load_error


# ---------------------------------------------------------------------------
# Widget : item de liste (identique a la maquette)
# ---------------------------------------------------------------------------

class FileListItem(ctk.CTkFrame):
    """Item de liste avec indicateur de statut (pastille)."""

    def __init__(self, parent, entry: CPTFileEntry, index: int, on_click):
        super().__init__(parent, fg_color="transparent", corner_radius=6, height=58)
        self.entry = entry
        self.index = index
        self.on_click = on_click
        self.pack_propagate(False)

        # Pastille statut
        self.status_dot = ctk.CTkLabel(
            self, text="\u25cf", font=("Arial", 24),
            text_color="#9CA3AF", width=28
        )
        self.status_dot.pack(side="left", padx=(12, 8))

        # Conteneur texte
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Info principale : Job Number + Test Number
        main_info = f"{entry.job_number} - {entry.test_number}"
        self.main_label = ctk.CTkLabel(
            text_frame, text=main_info,
            font=FONTS["list_item_bold"],
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.main_label.pack(anchor="w", fill="x")

        # Info secondaire : Nom du fichier
        self.filename_label = ctk.CTkLabel(
            text_frame, text=entry.filename,
            font=FONTS["tiny"],
            text_color=COLORS["text_secondary"], anchor="w"
        )
        self.filename_label.pack(anchor="w", fill="x", pady=(2, 0))

        # Localisation tronquee
        loc = entry.location
        location_short = loc[:35] + "..." if len(loc) > 35 else loc
        self.location_label = ctk.CTkLabel(
            text_frame, text=location_short,
            font=FONTS["tiny"],
            text_color=COLORS["text_secondary"], anchor="w"
        )
        self.location_label.pack(anchor="w", fill="x")

        # Bindings clic
        for widget in [self, self.status_dot, text_frame,
                       self.main_label, self.filename_label, self.location_label]:
            widget.bind("<Button-1>", lambda e, idx=index: self.on_click(idx))

    def set_selected(self, selected: bool):
        self.configure(fg_color=COLORS["selected_bg"] if selected else "transparent")

    def update_status(self):
        """Pastille : verte si filtre, grise sinon."""
        color = COLORS["success"] if self.entry.is_filtered else "#9CA3AF"
        self.status_dot.configure(text_color=color)


# ---------------------------------------------------------------------------
# Vue principale FILTRER
# ---------------------------------------------------------------------------

class CPTCleaningView(ctk.CTkFrame):
    """Vue de nettoyage des valeurs aberrantes, integree dans l'app."""

    def __init__(self, parent, model, presenter, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)

        self.model = model
        self.presenter = presenter
        self.cfg = CPTPlotConfig(
            show_titles=False,       # Titre redondant avec la toolbar
        )
        self.cpt_entries: list[CPTFileEntry] = []
        self.current_index = -1
        self.list_items: list[FileListItem] = []
        self._bindings_installed = False

        # Layout 2 colonnes
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_sidebar()
        self._create_chart_area()

    # ------------------------------------------------------------------ init

    def refresh_data(self):
        """Recharge la liste depuis RawDataManager et reconstruit la sidebar."""
        rdm = self.model.raw_data_manager
        files = rdm.get_all_files()

        # Conserver l'etat is_filtered des entrees deja connues
        old_state = {e.file_path: e.is_filtered for e in self.cpt_entries}

        self.cpt_entries = []
        for f in files:
            entry = CPTFileEntry(f, rdm)
            entry.is_filtered = old_state.get(entry.file_path, False)
            self.cpt_entries.append(entry)

        self._rebuild_list()

        if self.cpt_entries:
            self._select_item(0)
        else:
            self.current_index = -1
            self._clear_chart()
            self._update_progress()

    def on_workspace_shown(self):
        """Appelee quand on bascule sur ce workspace."""
        self.refresh_data()
        self.after(200, self._setup_bindings)

    def on_workspace_hidden(self):
        """Appelee quand on quitte ce workspace."""
        self._remove_bindings()

    # ------------------------------------------------------------ sidebar

    def _create_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 1))

        # Header (hauteur fixe 75)
        header = ctk.CTkFrame(sidebar, fg_color=COLORS["accent"], height=75, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Nettoyage des valeurs aberrantes",
            font=FONTS["title"], text_color="white"
        ).pack(pady=(14, 5), padx=20, anchor="w")

        self.progress_label = ctk.CTkLabel(
            header, text="0 sur 0 traites",
            font=FONTS["small"], text_color="white"
        )
        self.progress_label.pack(padx=20, anchor="w")

        # Liste scrollable
        self.list_frame = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent",
            scrollbar_button_color="#A0A8B0"
        )
        self.list_frame.pack(fill="both", expand=True, padx=8, pady=12)

        # Legende
        legend = ctk.CTkFrame(sidebar, fg_color=COLORS["card"], height=70, corner_radius=8)
        legend.pack(fill="x", side="bottom", padx=10, pady=10)
        legend.pack_propagate(False)

        ctk.CTkLabel(
            legend, text="Legende", font=FONTS["small"],
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=12, pady=(8, 4))

        legend_items = ctk.CTkFrame(legend, fg_color="transparent")
        legend_items.pack(fill="x", padx=12)

        ctk.CTkLabel(
            legend_items, text="\u25cf Non traite", font=FONTS["tiny"],
            text_color="#9CA3AF"
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            legend_items, text="\u25cf Filtre", font=FONTS["tiny"],
            text_color=COLORS["success"]
        ).pack(side="left")

    def _rebuild_list(self):
        """Reconstruit les items de la liste."""
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.list_items.clear()

        for idx, entry in enumerate(self.cpt_entries):
            item = FileListItem(self.list_frame, entry, idx, self._on_item_clicked)
            item.pack(fill="x", pady=3)
            self.list_items.append(item)

    # ---------------------------------------------------------- chart area

    def _create_chart_area(self):
        chart_area = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        chart_area.grid(row=0, column=1, sticky="nsew")

        # Toolbar (hauteur 75 alignee sur le header sidebar)
        toolbar = ctk.CTkFrame(chart_area, fg_color=COLORS["card"], height=75, corner_radius=0)
        toolbar.pack(fill="x", padx=0, pady=(0, 0))
        toolbar.pack_propagate(False)

        toolbar_content = ctk.CTkFrame(toolbar, fg_color="transparent")
        toolbar_content.pack(fill="both", expand=True)

        # Infos en une seule ligne (gauche)
        info_line = ctk.CTkFrame(toolbar_content, fg_color="transparent")
        info_line.pack(side="left", fill="y", padx=20, expand=True)

        info_container = ctk.CTkFrame(info_line, fg_color="transparent")
        info_container.pack(anchor="w", pady=26)

        # Job Number (bleu accent, gras)
        self.job_label = ctk.CTkLabel(
            info_container, text="--",
            font=FONTS["header_job"],
            text_color=COLORS["accent"]
        )
        self.job_label.pack(side="left")

        ctk.CTkLabel(
            info_container, text=" - ",
            font=FONTS["header_test"],
            text_color=COLORS["text_secondary"]
        ).pack(side="left")

        # Test Number
        self.test_label = ctk.CTkLabel(
            info_container, text="--",
            font=FONTS["header_test"],
            text_color=COLORS["text_primary"]
        )
        self.test_label.pack(side="left")

        ctk.CTkLabel(
            info_container, text=" - ",
            font=FONTS["header_file"],
            text_color=COLORS["text_tertiary"]
        ).pack(side="left")

        # Filename
        self.filename_display = ctk.CTkLabel(
            info_container, text="--",
            font=FONTS["header_file"],
            text_color=COLORS["text_tertiary"]
        )
        self.filename_display.pack(side="left")

        # Switch filtre (droite)
        controls = ctk.CTkFrame(toolbar_content, fg_color="transparent")
        controls.pack(side="right", padx=20)

        switch_container = ctk.CTkFrame(controls, fg_color="transparent")
        switch_container.pack(pady=18)

        self.filter_var = ctk.BooleanVar(value=False)
        self.filter_switch = ctk.CTkSwitch(
            switch_container, text="FILTRAGE AUTO", font=FONTS["list_item_bold"],
            command=self._on_filter_toggled, variable=self.filter_var,
            progress_color=COLORS["success"], switch_width=58, switch_height=30
        )
        self.filter_switch.pack()

        # Zone graphique
        chart_frame = ctk.CTkFrame(chart_area, fg_color=COLORS["card"], corner_radius=8)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Matplotlib figure pour affichage écran
        # On utilise un DPI écran (~100) au lieu de cfg.figure_dpi (200, prévu
        # pour l'export PDF).  TkAgg redimensionne la figure pour remplir le
        # widget : avec DPI 100, une zone de 600 px → 6" → polices/grilles
        # proportionnées.  Avec DPI 200, 600 px → 3" → tout parait 2× trop gros.
        cfg = self.cfg
        _screen_dpi = 100
        self.fig = Figure(
            figsize=(cfg.figure_width, cfg.figure_height),
            dpi=_screen_dpi,
            facecolor=COLORS["card"]
        )
        self.fig.subplots_adjust(
            left=cfg.adjust_left, right=cfg.adjust_right,
            top=cfg.adjust_top, bottom=cfg.adjust_bottom
        )

        # Axes conformes a plot_cpt() : ax1=Qst (bas), ax2=qc (haut/twiny)
        self.ax_qst = self.fig.add_subplot(111)
        self.ax_qc = self.ax_qst.twiny()

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

    # --------------------------------------------------------- bindings

    def _setup_bindings(self):
        if self._bindings_installed:
            return
        root = self.winfo_toplevel()
        root.bind("<Up>", self._on_key_up)
        root.bind("<Down>", self._on_key_down)
        root.bind("<space>", self._on_key_space)
        self._bindings_installed = True

    def _remove_bindings(self):
        if not self._bindings_installed:
            return
        root = self.winfo_toplevel()
        root.unbind("<Up>")
        root.unbind("<Down>")
        root.unbind("<space>")
        self._bindings_installed = False

    def _on_key_up(self, event):
        self._navigate(-1)

    def _on_key_down(self, event):
        self._navigate(1)

    def _on_key_space(self, event):
        self.filter_switch.toggle()

    # ---------------------------------------------------- selection / nav

    def _select_item(self, index: int):
        if index < 0 or index >= len(self.cpt_entries):
            return

        # Deselection precedente
        if 0 <= self.current_index < len(self.list_items):
            self.list_items[self.current_index].set_selected(False)

        self.current_index = index
        entry = self.cpt_entries[index]
        self.list_items[index].set_selected(True)

        # Scroll vers l'item visible
        self._scroll_to_item(index)

        # Header
        self.job_label.configure(text=entry.job_number or "--")
        self.test_label.configure(text=entry.test_number or "--")
        self.filename_display.configure(text=entry.filename or "--")

        # Sync switch
        self.filter_var.set(entry.is_filtered)

        self._update_progress()
        self._update_chart()

    def _scroll_to_item(self, index: int):
        """Fait defiler la liste pour rendre l'item visible."""
        if not self.list_items:
            return
        total = len(self.list_items)
        if total <= 1:
            return
        fraction = max(0.0, min(1.0, index / total))
        try:
            self.list_frame._parent_canvas.yview_moveto(fraction)
        except Exception:
            pass

    def _navigate(self, delta: int):
        new_index = self.current_index + delta
        if 0 <= new_index < len(self.cpt_entries):
            self._select_item(new_index)

    def _on_item_clicked(self, index: int):
        self._select_item(index)

    # -------------------------------------------------------- filter toggle

    def _on_filter_toggled(self):
        if self.current_index < 0:
            return
        entry = self.cpt_entries[self.current_index]
        entry.is_filtered = self.filter_var.get()
        self.list_items[self.current_index].update_status()
        self._update_progress()
        self._update_chart()

    def _update_progress(self):
        filtered_count = sum(1 for e in self.cpt_entries if e.is_filtered)
        total = len(self.cpt_entries)
        self.progress_label.configure(text=f"{filtered_count} sur {total} traites")

    # -------------------------------------------------------- chart drawing

    def _clear_chart(self):
        self.ax_qst.clear()
        self.ax_qc.clear()
        self.canvas.draw_idle()

    def _configure_axes(self, entry: CPTFileEntry):
        """Configure les axes en reproduisant fidelement plot_cpt() via CPTPlotConfig."""
        cfg = self.cfg

        # -- ax_qc = axe secondaire (haut, twiny) -- identique a ax2 de plot_cpt()
        self.ax_qc.spines['top'].set_position(('outward', 0))
        self.ax_qc.xaxis.set_ticks_position('top')
        self.ax_qc.xaxis.set_label_position('top')

        self.ax_qc.set_xlim(0, cfg.qc_max)
        self.ax_qc.xaxis.set_major_locator(MultipleLocator(5))
        self.ax_qc.xaxis.set_minor_locator(MultipleLocator(1))

        # Ticks qc formates en entiers gras (lignes 373-380 de cpt_plot)
        qc_ticks = list(range(0, int(cfg.qc_max) + 1, 5))
        if cfg.qc_max not in qc_ticks:
            qc_ticks.append(cfg.qc_max)
        self.ax_qc.set_xticks(qc_ticks)
        qc_labels = [int(t) if t == int(t) else t for t in qc_ticks]
        self.ax_qc.set_xticklabels(qc_labels, fontweight='bold')

        self.ax_qc.set_xlabel(cfg.xlabel_qc, fontweight='light',
                              fontsize=cfg.label_fontsize, labelpad=5)
        self.ax_qc.tick_params(axis='x', which='major', labelsize=cfg.tick_label_fontsize)

        # Grille verticale sur ax_qc (major + minor)
        self.ax_qc.xaxis.grid(True, which='minor', linestyle='--',
                               linewidth=0.65, color='lightgray', dashes=(4, 7))
        self.ax_qc.xaxis.grid(True, which='major', linestyle='--',
                               linewidth=0.65, color='lightgray', dashes=(4, 7))

        # -- ax_qst = axe principal (bas) -- identique a ax1 de plot_cpt()
        self.ax_qst.invert_yaxis()
        self.ax_qst.grid(False)
        self.ax_qst.yaxis.grid(True, linestyle='--', linewidth=0.65,
                                color='lightgray', dashes=(4, 7))

        self.ax_qst.set_xlim(0, cfg.qst_max)
        self.ax_qst.xaxis.set_major_locator(MultipleLocator(25))
        self.ax_qst.xaxis.set_minor_locator(MultipleLocator(5))
        self.ax_qst.xaxis.set_tick_params(which='minor', labelbottom=False)

        self.ax_qst.set_xlabel(cfg.xlabel_qst, fontweight='light',
                               fontsize=cfg.label_fontsize, labelpad=5)
        self.ax_qst.set_ylabel(cfg.ylabel, fontweight='light',
                               fontsize=cfg.label_fontsize, labelpad=5)

        self.ax_qst.tick_params(axis='x', which='major', labelsize=cfg.tick_label_fontsize)
        self.ax_qst.tick_params(axis='y', which='major', labelsize=cfg.tick_label_fontsize)

        # Limites Y (profondeur) via get_depth_limit()
        if entry.df_raw is not None:
            max_depth = entry.df_raw[entry.col_depth].max()
            depth_limit = cfg.get_depth_limit(max_depth)
            self.ax_qst.set_ylim(depth_limit, 0)
        self.ax_qst.yaxis.set_major_locator(MultipleLocator(1))

    def _plot_data(self, entry, df, color_qc=None, color_qst=None,
                   lw_qc=None, lw_qst=None, alpha=1.0, label_suffix=""):
        """Trace qc et qst sur les axes (trait plein, styles depuis CPTPlotConfig)."""
        cfg = self.cfg
        depth = df[entry.col_depth]
        qc = df[entry.col_qc]
        qst = df[entry.col_qst]

        zorder = 3 if alpha == 1.0 else 1

        # Axes conformes a plot_cpt() : qst sur ax_qst (bas), qc sur ax_qc (haut)
        self.ax_qst.plot(
            qst, depth,
            color=color_qst or cfg.qst_color,
            linewidth=lw_qst or cfg.qst_linewidth,
            alpha=alpha, label=f'Qst{label_suffix}', zorder=zorder
        )
        self.ax_qc.plot(
            qc, depth,
            color=color_qc or cfg.qc_color,
            linewidth=lw_qc or cfg.qc_linewidth,
            alpha=alpha, label=f'qc{label_suffix}', zorder=zorder
        )

    def _draw_annotations(self, entry, df):
        """Annotations qc hors-limites, reproduit plot_cpt() lignes 406-425."""
        cfg = self.cfg
        if not cfg.show_annotations:
            return

        col_qc = entry.col_qc
        col_depth = entry.col_depth

        mask = df[col_qc] > cfg.qc_annotation_threshold
        exceeded = df[mask][[col_qc, col_depth]]

        if exceeded.empty:
            return

        last_annotated_depth = -float('inf')
        for _, row in exceeded.iterrows():
            current_depth = row[col_depth]
            if current_depth - last_annotated_depth >= cfg.annotation_interval:
                value_str = f"{row[col_qc]:{cfg.annotation_format}}"
                self.ax_qc.annotate(
                    value_str,
                    (cfg.qc_max, current_depth),
                    textcoords="offset points",
                    xytext=(5, 0),
                    ha='left', va='center',
                    fontsize=cfg.annotation_fontsize,
                    color='black',
                    fontfamily='sans-serif',
                    fontweight='bold'
                )
                last_annotated_depth = current_depth

    def _update_chart(self):
        if self.current_index < 0:
            return

        cfg = self.cfg
        entry = self.cpt_entries[self.current_index]

        self.ax_qst.clear()
        self.ax_qc.clear()

        if not entry.ensure_loaded():
            self.ax_qst.text(
                0.5, 0.5,
                f"Impossible de charger :\n{entry.load_error or 'erreur inconnue'}",
                transform=self.ax_qst.transAxes,
                ha='center', va='center', fontsize=cfg.label_fontsize,
                color=COLORS["text_secondary"], wrap=True
            )
            self.canvas.draw_idle()
            return

        self._configure_axes(entry)

        if entry.is_filtered and entry.df_filtered is not None:
            # Brut en gris leger et plus fin
            self._plot_data(entry, entry.df_raw,
                            color_qc='#C0C0C0', color_qst='#D8D8D8',
                            lw_qc=cfg.qc_linewidth * 0.6,
                            lw_qst=cfg.qst_linewidth * 0.6,
                            alpha=0.7, label_suffix=" (brut)")
            # Filtre opaque (memes couleurs config, linewidth augmentee pour contraste)
            self._plot_data(entry, entry.df_filtered,
                            lw_qc=cfg.qc_linewidth * 1.25,
                            lw_qst=cfg.qst_linewidth * 1.25,
                            alpha=1.0, label_suffix=" (filtre)")
            # Annotations sur les donnees filtrees
            self._draw_annotations(entry, entry.df_filtered)
        else:
            # Brut uniquement (couleurs et linewidths directement depuis config)
            self._plot_data(entry, entry.df_raw)
            # Annotations sur les donnees brutes
            self._draw_annotations(entry, entry.df_raw)

        # Titre (si active dans la config)
        if cfg.show_titles:
            self.ax_qc.annotate(
                cfg.title_main,
                xy=(0.0, 1.08), xycoords='axes fraction',
                ha='left', va='center', fontsize=cfg.title_fontsize
            )

        # Legende
        lines_qst, labels_qst = self.ax_qst.get_legend_handles_labels()
        lines_qc, labels_qc = self.ax_qc.get_legend_handles_labels()
        if labels_qst or labels_qc:
            self.ax_qst.legend(lines_qst + lines_qc, labels_qst + labels_qc,
                               loc='lower right', fontsize=9, framealpha=0.95)

        self.canvas.draw_idle()
