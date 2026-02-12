"""
observations_view3.py

Vue OBSERVATIONS intégrée à l'application principale.
Même layout que FILTRER : sidebar gauche (liste des essais) + panneau droit
avec tableau "Observations dans le trou" et tableau d'annotations par profondeur.

Navigation :
- Flèches Haut/Bas : Défiler entre les sondages dans la sidebar
"""

import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
import pandas as pd
import math
from pathlib import Path
from typing import Optional, Dict

from gef_reader import GefFileError
from cpt_plot import CPTPlotConfig, _resolve_column_name
from tabular_reader import load_cpt_dataframe

# ---------------------------------------------------------------------------
# Palette et typographie (identiques à FILTRER / import assistant)
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#E8EDF2",
    "card": "#F5F7FA",
    "sidebar": "#DFE4E9",
    "accent": "#0115B8",
    "accent_light": "#E8EDF8",
    "success": "#16A34A",
    "text_primary": "#1A1A1A",
    "text_secondary": "#6B7280",
    "text_tertiary": "#9CA3AF",
    "selected_bg": "#C7D7E8",
    "divider": "#CBD5E1",
    "border": "#D1D5DB",
    "grid_light": "#E5E7EB",
    "row_alt": "#F9FAFB",
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
    "mono": ("Consolas", 10),
}

DEPTH_STEP = 0.2


# ---------------------------------------------------------------------------
# Adapter layer : CPTFileEntry léger pour la vue OBSERVATIONS
# ---------------------------------------------------------------------------

class ObsFileEntry:
    """Représentation d'un essai CPT pour la vue OBSERVATIONS.

    Charge les données à la demande (lazy) pour récupérer la profondeur max.
    """

    def __init__(self, file_data: dict, raw_data_manager):
        self.file_path: str = file_data.get("file_path", "")
        self.filename: str = file_data.get("file_name", Path(self.file_path).name)
        self.job_number: str = raw_data_manager.get_effective_value(self.file_path, "Job Number")
        self.test_number: str = raw_data_manager.get_effective_value(self.file_path, "TestNumber")
        self.location: str = raw_data_manager.get_effective_value(self.file_path, "Location")
        self.source_type: str = file_data.get("source_type", "gef")
        self._file_data: dict = file_data

        # Profondeur max (chargée à la demande)
        self._max_depth: Optional[float] = None
        self._load_error: Optional[str] = None
        self._loaded: bool = False

    def ensure_loaded(self) -> bool:
        if self._loaded:
            return self._load_error is None
        self._loaded = True
        try:
            df = load_cpt_dataframe(self._file_data)
            if df.empty:
                self._load_error = "DataFrame vide"
                return False
            cfg = CPTPlotConfig()
            col_depth = _resolve_column_name(df, cfg.col_depth, "col_depth")
            self._max_depth = float(df[col_depth].max())
            return True
        except (GefFileError, ValueError, TypeError, Exception) as exc:
            self._load_error = str(exc)
            return False

    @property
    def max_depth(self) -> Optional[float]:
        self.ensure_loaded()
        return self._max_depth

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error


# ---------------------------------------------------------------------------
# Widget : item de liste sidebar (identique à FILTRER)
# ---------------------------------------------------------------------------

class ObsFileListItem(ctk.CTkFrame):
    """Item de liste avec indicateur de statut (pastille)."""

    def __init__(self, parent, entry: ObsFileEntry, index: int, on_click,
                 has_data_fn=None):
        super().__init__(parent, fg_color="transparent", corner_radius=6, height=58)
        self.entry = entry
        self.index = index
        self.on_click = on_click
        self._has_data_fn = has_data_fn
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

        main_info = f"{entry.job_number} - {entry.test_number}"
        self.main_label = ctk.CTkLabel(
            text_frame, text=main_info,
            font=FONTS["list_item_bold"],
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.main_label.pack(anchor="w", fill="x")

        self.filename_label = ctk.CTkLabel(
            text_frame, text=entry.filename,
            font=FONTS["tiny"],
            text_color=COLORS["text_secondary"], anchor="w"
        )
        self.filename_label.pack(anchor="w", fill="x", pady=(2, 0))

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
        """Pastille : verte si l'essai a des données, grise sinon."""
        has_data = False
        if self._has_data_fn:
            has_data = self._has_data_fn(self.entry.file_path)
        color = COLORS["success"] if has_data else "#9CA3AF"
        self.status_dot.configure(text_color=color)


# ---------------------------------------------------------------------------
# Vue principale OBSERVATIONS
# ---------------------------------------------------------------------------

class ObservationsView(ctk.CTkFrame):
    """Vue des observations, intégrée dans l'app (même pattern que CPTCleaningView)."""

    def __init__(self, parent, model, presenter, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)

        self.model = model
        self.presenter = presenter
        self.obs_entries: list[ObsFileEntry] = []
        self.current_index = -1
        self.list_items: list[ObsFileListItem] = []
        self._bindings_installed = False

        # Stockage des données par essai (clé = file_path)
        # {file_path: {"hole_obs": {row_key: {"fin_essai": str, "fin_chantier": str}},
        #              "annotations": {depth_float: str}}}
        self._data_store: Dict[str, dict] = {}

        # Référence à l'Entry d'édition in-place du Treeview
        self._edit_entry: Optional[tk.Entry] = None
        self._edit_item: Optional[str] = None
        self._edit_col: Optional[str] = None

        # Layout 2 colonnes
        self.grid_columnconfigure(0, weight=0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_sidebar()
        self._create_content_area()

    # ------------------------------------------------------------------ data store

    def _get_store(self, file_path: str) -> dict:
        """Retourne ou crée le store pour un essai."""
        if file_path not in self._data_store:
            self._data_store[file_path] = {
                "hole_obs": {
                    "Niveau d'eau": {"fin_essai": "", "fin_chantier": ""},
                    "Eboulement": {"fin_essai": "", "fin_chantier": ""},
                },
                "annotations": {},
            }
        return self._data_store[file_path]

    def _has_any_data(self, file_path: str) -> bool:
        """Retourne True si l'essai a au moins une observation/annotation non vide."""
        if file_path not in self._data_store:
            return False
        store = self._data_store[file_path]
        # Vérifier hole_obs
        for row_data in store["hole_obs"].values():
            for v in row_data.values():
                if v and v.strip() and v.strip() != "-":
                    return True
        # Vérifier annotations
        for v in store["annotations"].values():
            if v and v.strip():
                return True
        return False

    # ------------------------------------------------------------------ init

    def refresh_data(self):
        """Recharge la liste depuis RawDataManager et reconstruit la sidebar."""
        rdm = self.model.raw_data_manager
        files = rdm.get_all_files()

        self.obs_entries = [ObsFileEntry(f, rdm) for f in files]
        self._rebuild_list()

        if self.obs_entries:
            self._select_item(0)
        else:
            self.current_index = -1
            self._clear_content()
            self._update_progress()

    def on_workspace_shown(self):
        """Appelée quand on bascule sur ce workspace."""
        self.refresh_data()
        self.after(200, self._setup_bindings)

    def on_workspace_hidden(self):
        """Appelée quand on quitte ce workspace."""
        self._cancel_edit()
        self._remove_bindings()

    # ------------------------------------------------------------ sidebar

    def _create_sidebar(self):
        sidebar = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 1))

        # Header
        header = ctk.CTkFrame(sidebar, fg_color=COLORS["accent"], height=75, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Observations terrain",
            font=FONTS["title"], text_color="white"
        ).pack(pady=(14, 5), padx=20, anchor="w")

        self.progress_label = ctk.CTkLabel(
            header, text="0 essais",
            font=FONTS["small"], text_color="white"
        )
        self.progress_label.pack(padx=20, anchor="w")

        # Liste scrollable
        self.list_frame = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent",
            scrollbar_button_color="#A0A8B0"
        )
        self.list_frame.pack(fill="both", expand=True, padx=8, pady=12)

        # Légende
        legend = ctk.CTkFrame(sidebar, fg_color=COLORS["card"], height=70, corner_radius=8)
        legend.pack(fill="x", side="bottom", padx=10, pady=10)
        legend.pack_propagate(False)

        ctk.CTkLabel(
            legend, text="Légende", font=FONTS["small"],
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=12, pady=(8, 4))

        legend_items = ctk.CTkFrame(legend, fg_color="transparent")
        legend_items.pack(fill="x", padx=12)

        ctk.CTkLabel(
            legend_items, text="\u25cf Sans observation", font=FONTS["tiny"],
            text_color="#9CA3AF"
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            legend_items, text="\u25cf Avec observation(s)", font=FONTS["tiny"],
            text_color=COLORS["success"]
        ).pack(side="left")

    def _rebuild_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.list_items.clear()

        for idx, entry in enumerate(self.obs_entries):
            item = ObsFileListItem(
                self.list_frame, entry, idx, self._on_item_clicked,
                has_data_fn=self._has_any_data
            )
            item.pack(fill="x", pady=3)
            self.list_items.append(item)

    # ---------------------------------------------------------- content area

    def _create_content_area(self):
        content_area = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        content_area.grid(row=0, column=1, sticky="nsew")

        # Toolbar (hauteur 75 alignée sur le header sidebar)
        toolbar = ctk.CTkFrame(content_area, fg_color=COLORS["card"], height=75, corner_radius=0)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        toolbar_content = ctk.CTkFrame(toolbar, fg_color="transparent")
        toolbar_content.pack(fill="both", expand=True)

        info_line = ctk.CTkFrame(toolbar_content, fg_color="transparent")
        info_line.pack(side="left", fill="y", padx=20, expand=True)

        info_container = ctk.CTkFrame(info_line, fg_color="transparent")
        info_container.pack(anchor="w", pady=26)

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

        self.filename_display = ctk.CTkLabel(
            info_container, text="--",
            font=FONTS["header_file"],
            text_color=COLORS["text_tertiary"]
        )
        self.filename_display.pack(side="left")

        # Zone de contenu scrollable (les deux tableaux)
        self.content_frame = ctk.CTkFrame(content_area, fg_color=COLORS["card"], corner_radius=8)
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self._content_inner = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self._content_inner.pack(fill="both", expand=True, padx=16, pady=12)

        # Message d'erreur / info (caché par défaut)
        self._msg_label = ctk.CTkLabel(
            self._content_inner, text="",
            font=FONTS["body"], text_color=COLORS["text_secondary"],
            wraplength=500
        )

        # -- Tableau 1 : Observations dans le trou --
        self._create_hole_obs_table()

        # -- Tableau 2 : Annotations par profondeur --
        self._create_annotations_tree()

    # ---- Tableau 1 : Observations dans le trou ----

    def _create_hole_obs_table(self):
        """Petit tableau éditable avec ttk.Treeview."""
        section_label = ctk.CTkLabel(
            self._content_inner, text="Observations dans le trou",
            font=FONTS["subtitle"], text_color=COLORS["text_primary"]
        )
        section_label.pack(anchor="w", pady=(0, 6))

        hole_container = ctk.CTkFrame(self._content_inner, fg_color="transparent")
        hole_container.pack(fill="x", pady=(0, 16))

        # Style
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "HoleObs.Treeview",
            background="#FFFFFF",
            foreground=COLORS["text_primary"],
            fieldbackground="#FFFFFF",
            font=FONTS["mono"],
            rowheight=28,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "HoleObs.Treeview.Heading",
            background=COLORS["accent_light"],
            foreground=COLORS["accent"],
            font=("Verdana", 9, "bold"),
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "HoleObs.Treeview",
            background=[("selected", COLORS["accent_light"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.map(
            "HoleObs.Treeview.Heading",
            background=[("active", COLORS["accent_light"])],
        )

        self._hole_tree = ttk.Treeview(
            hole_container,
            columns=("label", "fin_essai", "fin_chantier"),
            show="headings",
            style="HoleObs.Treeview",
            height=2,
            selectmode="browse",
        )
        self._hole_tree.heading("label", text="Observations dans le trou")
        self._hole_tree.heading("fin_essai", text="Profondeur en fin d'essai [m]")
        self._hole_tree.heading("fin_chantier", text="Profondeur en fin de chantier [m]")

        self._hole_tree.column("label", width=200, minwidth=150, stretch=False)
        self._hole_tree.column("fin_essai", width=220, minwidth=150, anchor="center")
        self._hole_tree.column("fin_chantier", width=220, minwidth=150, anchor="center")

        self._hole_tree.pack(fill="x")

        # Lignes initiales
        self._hole_rows = {}
        for row_key in ["Niveau d'eau", "Eboulement"]:
            iid = self._hole_tree.insert("", "end", values=(row_key, "", ""))
            self._hole_rows[row_key] = iid

        # Édition in-place sur double-clic
        self._hole_tree.bind("<Double-1>", self._on_hole_tree_dblclick)

        # Référence pour l'entry d'édition du hole tree
        self._hole_edit_entry: Optional[tk.Entry] = None
        self._hole_edit_iid: Optional[str] = None
        self._hole_edit_col_idx: Optional[int] = None

    def _on_hole_tree_dblclick(self, event):
        """Double-clic sur le petit tableau : éditer la cellule cliquée."""
        region = self._hole_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self._hole_tree.identify_column(event.x)
        # col is "#1", "#2", "#3"
        col_idx = int(col.replace("#", "")) - 1
        if col_idx == 0:
            # Colonne label non éditable
            return
        iid = self._hole_tree.identify_row(event.y)
        if not iid:
            return
        self._start_hole_edit(iid, col_idx)

    def _start_hole_edit(self, iid, col_idx):
        """Place un Entry au-dessus de la cellule pour édition."""
        self._cancel_hole_edit()

        # Coordonnées de la cellule
        col_id = self._hole_tree["columns"][col_idx]
        bbox = self._hole_tree.bbox(iid, col_id)
        if not bbox:
            return
        x, y, w, h = bbox

        current_values = self._hole_tree.item(iid, "values")
        current_text = current_values[col_idx] if col_idx < len(current_values) else ""

        entry = tk.Entry(
            self._hole_tree, font=FONTS["mono"],
            justify="center", bd=1, relief="solid",
            highlightthickness=1, highlightcolor=COLORS["accent"]
        )
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_text)
        entry.select_range(0, "end")
        entry.focus_set()

        entry.bind("<Return>", lambda e: self._commit_hole_edit())
        entry.bind("<Tab>", lambda e: self._commit_hole_edit())
        entry.bind("<Escape>", lambda e: self._cancel_hole_edit())
        entry.bind("<FocusOut>", lambda e: self._commit_hole_edit())

        self._hole_edit_entry = entry
        self._hole_edit_iid = iid
        self._hole_edit_col_idx = col_idx

    def _commit_hole_edit(self):
        """Valide l'édition dans le petit tableau."""
        if not self._hole_edit_entry:
            return
        new_val = self._hole_edit_entry.get().strip()
        iid = self._hole_edit_iid
        col_idx = self._hole_edit_col_idx

        # Mettre à jour le Treeview
        values = list(self._hole_tree.item(iid, "values"))
        values[col_idx] = new_val
        self._hole_tree.item(iid, values=values)

        # Sauvegarder dans le store
        self._save_hole_obs_from_tree()

        self._cancel_hole_edit()

    def _cancel_hole_edit(self):
        """Annule / détruit l'Entry d'édition du petit tableau."""
        if self._hole_edit_entry:
            try:
                self._hole_edit_entry.destroy()
            except Exception:
                pass
            self._hole_edit_entry = None
            self._hole_edit_iid = None
            self._hole_edit_col_idx = None

    def _save_hole_obs_from_tree(self):
        """Sauvegarde les données du petit tableau dans le store."""
        if self.current_index < 0:
            return
        entry = self.obs_entries[self.current_index]
        store = self._get_store(entry.file_path)

        for row_key, iid in self._hole_rows.items():
            values = self._hole_tree.item(iid, "values")
            store["hole_obs"][row_key]["fin_essai"] = values[1] if len(values) > 1 else ""
            store["hole_obs"][row_key]["fin_chantier"] = values[2] if len(values) > 2 else ""

        # Mettre à jour la pastille
        if 0 <= self.current_index < len(self.list_items):
            self.list_items[self.current_index].update_status()

    def _load_hole_obs_to_tree(self):
        """Charge les données du store dans le petit tableau."""
        if self.current_index < 0:
            return
        entry = self.obs_entries[self.current_index]
        store = self._get_store(entry.file_path)

        for row_key, iid in self._hole_rows.items():
            data = store["hole_obs"].get(row_key, {"fin_essai": "", "fin_chantier": ""})
            self._hole_tree.item(iid, values=(row_key, data["fin_essai"], data["fin_chantier"]))

    # ---- Tableau 2 : Annotations par profondeur ----

    def _create_annotations_tree(self):
        """Tableau principal Excel-like (Treeview) avec profondeur + annotation."""
        section_label = ctk.CTkLabel(
            self._content_inner, text="Annotations par profondeur",
            font=FONTS["subtitle"], text_color=COLORS["text_primary"]
        )
        section_label.pack(anchor="w", pady=(0, 6))

        tree_container = ctk.CTkFrame(self._content_inner, fg_color="transparent")
        tree_container.pack(fill="both", expand=True)

        # Style dédié
        style = ttk.Style(self)

        style.configure(
            "Annot.Treeview",
            background="#FFFFFF",
            foreground=COLORS["text_primary"],
            fieldbackground="#FFFFFF",
            font=FONTS["mono"],
            rowheight=24,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Annot.Treeview.Heading",
            background=COLORS["accent_light"],
            foreground=COLORS["accent"],
            font=("Verdana", 9, "bold"),
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Annot.Treeview",
            background=[("selected", COLORS["accent_light"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.map(
            "Annot.Treeview.Heading",
            background=[("active", COLORS["accent_light"])],
        )

        # Scrollbar verticale uniquement
        self._annot_scroll_y = ctk.CTkScrollbar(tree_container, orientation="vertical")

        self._annot_tree = ttk.Treeview(
            tree_container,
            columns=("depth", "annotation"),
            show="headings",
            style="Annot.Treeview",
            selectmode="browse",
            yscrollcommand=self._annot_scroll_y.set,
        )
        self._annot_scroll_y.configure(command=self._annot_tree.yview)

        self._annot_tree.heading("depth", text="Profondeur (m)")
        self._annot_tree.heading("annotation", text="Annotation")

        self._annot_tree.column("depth", width=140, minwidth=100, anchor="center", stretch=False)
        self._annot_tree.column("annotation", width=300, minwidth=200, anchor="w")

        self._annot_scroll_y.pack(side="right", fill="y")
        self._annot_tree.pack(side="left", fill="both", expand=True)

        # Tags pour alternance de lignes
        self._annot_tree.tag_configure("oddrow", background="#FFFFFF")
        self._annot_tree.tag_configure("evenrow", background=COLORS["row_alt"])

        # Bindings pour édition
        self._annot_tree.bind("<Double-1>", self._on_annot_dblclick)
        self._annot_tree.bind("<Return>", self._on_annot_enter)
        self._annot_tree.bind("<F2>", self._on_annot_enter)

        # Message si profondeur < 0.2
        self._annot_empty_label = ctk.CTkLabel(
            tree_container, text="",
            font=FONTS["body"], text_color=COLORS["text_secondary"]
        )

    def _generate_depths(self, max_depth: float) -> list[float]:
        """Génère la liste de profondeurs selon les règles spécifiées."""
        if max_depth < DEPTH_STEP:
            return []
        # Dernière profondeur = max arrondie à l'inférieur au pas 0.2
        last = math.floor(max_depth / DEPTH_STEP) * DEPTH_STEP
        # Correction de la précision flottante
        last = round(last, 1)
        if last < DEPTH_STEP:
            return []

        depths = []
        current = DEPTH_STEP
        while current <= last + 1e-9:
            depths.append(round(current, 1))
            current += DEPTH_STEP
            current = round(current, 1)
        return depths

    def _populate_annotations_tree(self):
        """Remplit le tableau d'annotations pour l'essai sélectionné."""
        # Nettoyer
        for iid in self._annot_tree.get_children():
            self._annot_tree.delete(iid)
        self._annot_empty_label.pack_forget()

        if self.current_index < 0:
            return

        entry = self.obs_entries[self.current_index]

        if not entry.ensure_loaded():
            self._annot_empty_label.configure(
                text=f"Impossible de charger le fichier :\n{entry.load_error or 'erreur inconnue'}"
            )
            self._annot_empty_label.pack(fill="x", pady=20)
            return

        max_depth = entry.max_depth
        if max_depth is None or max_depth < DEPTH_STEP:
            self._annot_empty_label.configure(
                text=f"Profondeur max ({max_depth:.2f} m) inférieure à {DEPTH_STEP} m.\nAucune ligne d'annotation à afficher."
                if max_depth is not None else "Profondeur non disponible."
            )
            self._annot_empty_label.pack(fill="x", pady=20)
            return

        depths = self._generate_depths(max_depth)
        store = self._get_store(entry.file_path)
        annotations = store["annotations"]

        for i, d in enumerate(depths):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            annot_text = annotations.get(d, "")
            self._annot_tree.insert(
                "", "end",
                values=(f"{d:.1f}", annot_text),
                tags=(tag,)
            )

    # -- Édition in-place du Treeview annotations --

    def _on_annot_dblclick(self, event):
        region = self._annot_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self._annot_tree.identify_column(event.x)
        col_idx = int(col.replace("#", "")) - 1
        if col_idx != 1:
            # Seule la colonne Annotation est éditable
            return
        iid = self._annot_tree.identify_row(event.y)
        if not iid:
            return
        self._start_annot_edit(iid)

    def _on_annot_enter(self, event):
        """Enter ou F2 : éditer la cellule annotation de la ligne sélectionnée."""
        sel = self._annot_tree.selection()
        if not sel:
            return
        self._start_annot_edit(sel[0])

    def _start_annot_edit(self, iid):
        """Place un Entry au-dessus de la cellule annotation pour édition."""
        self._cancel_edit()

        bbox = self._annot_tree.bbox(iid, "annotation")
        if not bbox:
            # L'item n'est pas visible, le scroller
            self._annot_tree.see(iid)
            self._annot_tree.update_idletasks()
            bbox = self._annot_tree.bbox(iid, "annotation")
            if not bbox:
                return
        x, y, w, h = bbox

        values = self._annot_tree.item(iid, "values")
        current_text = values[1] if len(values) > 1 else ""

        entry = tk.Entry(
            self._annot_tree, font=FONTS["mono"],
            bd=1, relief="solid",
            highlightthickness=1, highlightcolor=COLORS["accent"]
        )
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_text)
        entry.select_range(0, "end")
        entry.focus_set()

        entry.bind("<Return>", lambda e: self._commit_annot_edit())
        entry.bind("<Tab>", lambda e: self._commit_annot_edit_and_next())
        entry.bind("<Escape>", lambda e: self._cancel_edit())
        entry.bind("<FocusOut>", lambda e: self._commit_annot_edit())
        entry.bind("<Up>", lambda e: self._commit_annot_edit_and_move(-1))
        entry.bind("<Down>", lambda e: self._commit_annot_edit_and_move(1))

        self._edit_entry = entry
        self._edit_item = iid
        self._edit_col = "annotation"

        # Sélectionner la ligne dans le Treeview
        self._annot_tree.selection_set(iid)

    def _commit_annot_edit(self):
        """Valide l'annotation et sauvegarde."""
        if not self._edit_entry:
            return
        new_val = self._edit_entry.get().strip()
        # Tronquer à 15 caractères
        new_val = new_val[:15]
        iid = self._edit_item

        # Mettre à jour le Treeview
        values = list(self._annot_tree.item(iid, "values"))
        values[1] = new_val
        self._annot_tree.item(iid, values=values)

        # Sauvegarder dans le store
        self._save_annotation(iid, new_val)

        self._cancel_edit()

    def _commit_annot_edit_and_next(self):
        """Valide et passe à la ligne suivante (Tab)."""
        if not self._edit_entry:
            return
        iid = self._edit_item
        self._commit_annot_edit()
        # Naviguer à la ligne suivante
        next_iid = self._annot_tree.next(iid)
        if next_iid:
            self._annot_tree.selection_set(next_iid)
            self._annot_tree.see(next_iid)
            self._start_annot_edit(next_iid)

    def _commit_annot_edit_and_move(self, delta):
        """Valide et déplace de delta lignes (Up/Down)."""
        if not self._edit_entry:
            return
        iid = self._edit_item
        self._commit_annot_edit()
        if delta < 0:
            target = self._annot_tree.prev(iid)
        else:
            target = self._annot_tree.next(iid)
        if target:
            self._annot_tree.selection_set(target)
            self._annot_tree.see(target)
            self._start_annot_edit(target)

    def _cancel_edit(self):
        """Annule / détruit l'Entry d'édition de l'annotation."""
        if self._edit_entry:
            try:
                self._edit_entry.destroy()
            except Exception:
                pass
            self._edit_entry = None
            self._edit_item = None
            self._edit_col = None

    def _save_annotation(self, iid, value):
        """Sauvegarde une annotation dans le store."""
        if self.current_index < 0:
            return
        entry = self.obs_entries[self.current_index]
        store = self._get_store(entry.file_path)

        values = self._annot_tree.item(iid, "values")
        depth_str = values[0]
        try:
            depth = round(float(depth_str), 1)
        except (ValueError, TypeError):
            return

        if value:
            store["annotations"][depth] = value
        else:
            store["annotations"].pop(depth, None)

        # Mettre à jour la pastille
        if 0 <= self.current_index < len(self.list_items):
            self.list_items[self.current_index].update_status()

    # --------------------------------------------------------- content display

    def _clear_content(self):
        """Vide les tableaux et affiche un message si besoin."""
        for iid in self._annot_tree.get_children():
            self._annot_tree.delete(iid)
        for row_key, iid in self._hole_rows.items():
            self._hole_tree.item(iid, values=(row_key, "", ""))
        self.job_label.configure(text="--")
        self.test_label.configure(text="--")
        self.filename_display.configure(text="--")

    def _update_content(self):
        """Met à jour le panneau droit pour l'essai sélectionné."""
        self._cancel_edit()
        self._cancel_hole_edit()

        if self.current_index < 0:
            self._clear_content()
            return

        entry = self.obs_entries[self.current_index]

        # Header toolbar
        self.job_label.configure(text=entry.job_number or "--")
        self.test_label.configure(text=entry.test_number or "--")
        self.filename_display.configure(text=entry.filename or "--")

        # Charger les tableaux
        self._load_hole_obs_to_tree()
        self._populate_annotations_tree()

    # --------------------------------------------------------- bindings

    def _setup_bindings(self):
        if self._bindings_installed:
            return
        root = self.winfo_toplevel()
        root.bind("<Up>", self._on_key_up)
        root.bind("<Down>", self._on_key_down)
        self._bindings_installed = True

    def _remove_bindings(self):
        if not self._bindings_installed:
            return
        root = self.winfo_toplevel()
        root.unbind("<Up>")
        root.unbind("<Down>")
        self._bindings_installed = False

    def _on_key_up(self, event):
        # Ne pas naviguer si on est en édition
        if self._edit_entry or self._hole_edit_entry:
            return
        self._navigate(-1)

    def _on_key_down(self, event):
        if self._edit_entry or self._hole_edit_entry:
            return
        self._navigate(1)

    # ---------------------------------------------------- selection / nav

    def _select_item(self, index: int):
        if index < 0 or index >= len(self.obs_entries):
            return

        if 0 <= self.current_index < len(self.list_items):
            self.list_items[self.current_index].set_selected(False)

        self.current_index = index
        self.list_items[index].set_selected(True)

        self._scroll_to_item(index)
        self._update_progress()
        self._update_content()

    def _scroll_to_item(self, index: int):
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
        if 0 <= new_index < len(self.obs_entries):
            self._select_item(new_index)

    def _on_item_clicked(self, index: int):
        self._select_item(index)

    def _update_progress(self):
        total = len(self.obs_entries)
        with_obs = sum(1 for e in self.obs_entries if self._has_any_data(e.file_path))
        self.progress_label.configure(text=f"{with_obs} sur {total} avec observations")
