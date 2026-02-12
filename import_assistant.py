"""
import_assistant.py

Assistant d'importation de fichiers tabulaires (CSV / Excel) pour CPT.
Fenêtre CTkToplevel centrée avec :
- Aperçu des données
- Statistiques
- Mapping des colonnes (profondeur, qc, Qst/Qt)
- Conversion Qt -> Qst si nécessaire
"""

import customtkinter as ctk
from tkinter import ttk, messagebox
from typing import Optional, Dict, List, Callable, Tuple
from pathlib import Path
import pandas as pd

from tabular_reader import (
    read_tabular_raw,
    extract_header_names,
    build_data_df,
    compute_preview_stats,
    get_excel_sheet_names,
)


# ---------------------------------------------------------------------------
# Couleurs et polices cohérentes avec l'application principale
# ---------------------------------------------------------------------------

_COLORS = {
    "bg": "#F2F2F2",
    "card": "#FFFFFF",
    "accent": "#0115B8",
    "accent_hover": "#0228E0",
    "accent_light": "#E8EDF8",
    "text": "#1A1A1A",
    "text_secondary": "#6B7280",
    "success": "#16A34A",
    "warning": "#D97706",
    "error": "#DC2626",
    "border": "#D1D5DB",
}

_FONTS = {
    "title": ("Verdana", 15, "bold"),
    "subtitle": ("Verdana", 12, "bold"),
    "body": ("Verdana", 11),
    "small": ("Verdana", 9),
    "mono": ("Consolas", 9),
}


# ---------------------------------------------------------------------------
# Assistant d'importation
# ---------------------------------------------------------------------------

class ImportAssistant(ctk.CTkToplevel):
    """
    Fenêtre assistant pour importer un fichier CSV/Excel comme essai CPT.

    Retourne via le callback `on_result` un dict file_data prêt pour
    RawDataManager, ou None si l'utilisateur annule.
    """

    PREVIEW_ROWS = 15

    def __init__(
        self,
        parent,
        filepath: str,
        on_result: Callable[[Optional[Dict]], None],
        *,
        file_index: int = 1,
        file_total: int = 1,
    ):
        super().__init__(parent)
        self.filepath = filepath
        self.on_result = on_result
        self._file_index = file_index
        self._file_total = file_total

        # Titre avec indicateur de progression multi-fichier
        fname = Path(filepath).name
        if file_total > 1:
            self.title(f"Import — {fname}  ({file_index}/{file_total})")
        else:
            self.title(f"Import — {fname}")

        self.resizable(True, True)
        self.configure(fg_color=_COLORS["bg"])
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.grab_set()

        # Données internes
        self._df_raw: Optional[pd.DataFrame] = None
        self._df_numeric: Optional[pd.DataFrame] = None
        self._has_header: bool = False
        self._col_names: List[str] = []
        self._info: Dict = {}
        self._sheet_names: List[str] = []
        self._current_sheet: Optional[str] = None

        # Construire l'UI puis charger les données
        self._build_ui()
        self._center_window(1280, 1024)
        self.after(100, self._load_file)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # Conteneur principal
        main = ctk.CTkFrame(self, fg_color=_COLORS["bg"])
        main.pack(fill="both", expand=True, padx=18, pady=14)

        # -- Bandeau multi-fichier --
        if self._file_total > 1:
            counter_frame = ctk.CTkFrame(main, fg_color=_COLORS["accent_light"], corner_radius=8)
            counter_frame.pack(fill="x", pady=(0, 10))

            ctk.CTkLabel(
                counter_frame,
                text=f"Fichier {self._file_index} / {self._file_total}  —  {Path(self.filepath).name}",
                font=_FONTS["subtitle"],
                text_color=_COLORS["accent"],
            ).pack(padx=14, pady=8)

            # Barre de progression
            progress_val = self._file_index / self._file_total
            progress_bar = ctk.CTkProgressBar(
                counter_frame,
                width=400,
                height=6,
                progress_color=_COLORS["accent"],
                fg_color=_COLORS["border"],
                corner_radius=3,
            )
            progress_bar.pack(padx=14, pady=(0, 8), fill="x")
            progress_bar.set(progress_val)

        # -- Section : sélection de feuille (Excel uniquement) --
        self._sheet_frame = ctk.CTkFrame(main, fg_color=_COLORS["card"], corner_radius=8, border_width=1, border_color=_COLORS["border"])
        # Sera pack() seulement si Excel avec plusieurs feuilles

        sheet_inner = ctk.CTkFrame(self._sheet_frame, fg_color="transparent")
        sheet_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            sheet_inner, text="Feuille Excel", font=_FONTS["subtitle"],
            text_color=_COLORS["text"],
        ).pack(side="left", padx=(0, 12))

        self._sheet_var = ctk.StringVar()
        self._sheet_combo = ctk.CTkComboBox(
            sheet_inner, variable=self._sheet_var,
            state="readonly", width=300,
            font=_FONTS["body"],
            dropdown_font=_FONTS["body"],
            fg_color=_COLORS["bg"],
            border_color=_COLORS["border"],
            button_color=_COLORS["accent_light"],
            button_hover_color=_COLORS["border"],
            command=lambda _: self._on_sheet_changed(),
        )
        self._sheet_combo.pack(side="left")

        # -- Section : options header --
        self._opts_frame = ctk.CTkFrame(main, fg_color=_COLORS["card"], corner_radius=8, border_width=1, border_color=_COLORS["border"])
        self._opts_frame.pack(fill="x", pady=(0, 8))

        opts_inner = ctk.CTkFrame(self._opts_frame, fg_color="transparent")
        opts_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            opts_inner, text="Options de lecture", font=_FONTS["subtitle"],
            text_color=_COLORS["text"],
        ).pack(anchor="w", pady=(0, 6))

        self._header_var = ctk.BooleanVar(value=False)
        self._header_check = ctk.CTkCheckBox(
            opts_inner,
            text="La première ligne contient des noms de colonnes (en-tête)",
            variable=self._header_var, font=_FONTS["body"],
            text_color=_COLORS["text"],
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            command=self._on_header_toggled,
        )
        self._header_check.pack(anchor="w")

        # -- Section : aperçu --
        preview_frame = ctk.CTkFrame(main, fg_color=_COLORS["card"], corner_radius=8, border_width=1, border_color=_COLORS["border"])
        preview_frame.pack(fill="both", expand=True, pady=(0, 8))

        preview_inner = ctk.CTkFrame(preview_frame, fg_color="transparent")
        preview_inner.pack(fill="both", expand=True, padx=14, pady=10)

        ctk.CTkLabel(
            preview_inner, text="Aperçu des données", font=_FONTS["subtitle"],
            text_color=_COLORS["text"],
        ).pack(anchor="w", pady=(0, 6))

        # Treeview pour l'aperçu (ttk — incontournable pour les tableaux)
        tree_container = ctk.CTkFrame(preview_inner, fg_color="transparent")
        tree_container.pack(fill="both", expand=True)

        # Style ttk cohérent
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Import.Treeview",
            background=_COLORS["card"],
            foreground=_COLORS["text"],
            fieldbackground=_COLORS["card"],
            font=_FONTS["mono"],
            rowheight=22,
            borderwidth=0,
        )
        style.configure(
            "Import.Treeview.Heading",
            background=_COLORS["accent_light"],
            foreground=_COLORS["accent"],
            font=("Verdana", 9, "bold"),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Import.Treeview",
            background=[("selected", _COLORS["accent_light"])],
            foreground=[("selected", _COLORS["accent"])],
        )
        style.map(
            "Import.Treeview.Heading",
            background=[("active", _COLORS["accent_light"])],
        )

        self._tree_scroll_x = ctk.CTkScrollbar(tree_container, orientation="horizontal")
        self._tree_scroll_y = ctk.CTkScrollbar(tree_container, orientation="vertical")

        self._tree = ttk.Treeview(
            tree_container,
            show="headings",
            style="Import.Treeview",
            #height=self.PREVIEW_ROWS,
            height=11,
            xscrollcommand=self._tree_scroll_x.set,
            yscrollcommand=self._tree_scroll_y.set,
        )
        self._tree_scroll_x.configure(command=self._tree.xview)
        self._tree_scroll_y.configure(command=self._tree.yview)

        self._tree_scroll_y.pack(side="right", fill="y")
        self._tree.pack(side="top", fill="both", expand=True)
        self._tree_scroll_x.pack(side="bottom", fill="x")

        # -- Section : statistiques --
        self._stats_label = ctk.CTkLabel(
            main, text="", font=_FONTS["small"],
            text_color=_COLORS["text_secondary"],
            justify="left", anchor="w",
        )
        self._stats_label.pack(fill="x", pady=(0, 8))

        # -- Section : mapping colonnes --
        mapping_frame = ctk.CTkFrame(main, fg_color=_COLORS["card"], corner_radius=8, border_width=1, border_color=_COLORS["border"])
        mapping_frame.pack(fill="x", pady=(0, 4))

        mapping_inner = ctk.CTkFrame(mapping_frame, fg_color="transparent")
        mapping_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            mapping_inner, text="Mapping des colonnes (obligatoire)", font=_FONTS["subtitle"],
            text_color=_COLORS["text"],
        ).pack(anchor="w", pady=(0, 6))

        # Note cône 10 cm²
        note = (
            "Hypothèse cône 10 cm² : A = 0.001 m²  ⇒  1 MPa × A = 1 kN  "
            "⇒  valeurs numériques MPa ↔ kN identiques pour qc."
        )
        note_frame = ctk.CTkFrame(mapping_inner, fg_color=_COLORS["accent_light"], corner_radius=6)
        note_frame.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            note_frame, text=note, font=_FONTS["small"],
            text_color=_COLORS["accent"],
            wraplength=880, justify="left",
        ).pack(padx=10, pady=6)

        grid = ctk.CTkFrame(mapping_inner, fg_color="transparent")
        grid.pack(fill="x")

        self._mapping_vars: Dict[str, ctk.StringVar] = {}
        labels = [
            ("depth", "Profondeur (m)"),
            ("qc", "qc (MPa)"),
            ("qst", "Qst (kN)  ou  Qt (kN)"),
        ]
        for i, (key, label) in enumerate(labels):
            ctk.CTkLabel(
                grid, text=label, font=_FONTS["body"],
                text_color=_COLORS["text"],
            ).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 14))

            var = ctk.StringVar()
            combo = ctk.CTkComboBox(
                grid, variable=var, state="readonly", width=300,
                font=_FONTS["body"],
                dropdown_font=_FONTS["body"],
                fg_color=_COLORS["bg"],
                border_color=_COLORS["border"],
                button_color=_COLORS["accent_light"],
                button_hover_color=_COLORS["border"],
            )
            combo.grid(row=i, column=1, sticky="w", pady=4)
            self._mapping_vars[key] = var
            setattr(self, f"_combo_{key}", combo)

        # Checkbox Qt
        self._is_qt_var = ctk.BooleanVar(value=False)
        qt_frame = ctk.CTkFrame(mapping_inner, fg_color="transparent")
        qt_frame.pack(fill="x", pady=(8, 0))

        self._qt_check = ctk.CTkCheckBox(
            qt_frame,
            text="La 3e colonne est Qt (résistance totale) — Qst sera calculé : Qst = Qt − qc",
            variable=self._is_qt_var, font=_FONTS["body"],
            text_color=_COLORS["text"],
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            command=self._on_qt_toggled,
        )
        self._qt_check.pack(anchor="w")

        self._qt_info_label = ctk.CTkLabel(
            qt_frame, text="", font=_FONTS["small"],
            text_color=_COLORS["success"],
            justify="left", anchor="w",
        )
        self._qt_info_label.pack(fill="x", padx=(28, 0))

        # -- Boutons --
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(
            btn_frame, text="Annuler", font=_FONTS["body"],
            width=140, height=38,
            fg_color=_COLORS["card"],
            hover_color=_COLORS["border"],
            text_color=_COLORS["text"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=8,
            command=self._cancel,
        ).pack(side="left")

        self._import_btn = ctk.CTkButton(
            btn_frame, text="Importer", font=_FONTS["subtitle"],
            width=160, height=38,
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            text_color="white",
            corner_radius=8,
            command=self._import,
        )
        self._import_btn.pack(side="right")

    # --------------------------------------------------------- centrage

    def _center_window(self, width: int, height: int):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------- chargement

    def _load_file(self):
        try:
            ext = Path(self.filepath).suffix.lower()

            # Feuilles Excel ?
            if ext in (".xls", ".xlsx"):
                self._sheet_names = get_excel_sheet_names(self.filepath)
                if len(self._sheet_names) > 1:
                    self._sheet_frame.pack(fill="x", pady=(0, 8), before=self._opts_frame)
                    self._sheet_combo.configure(values=self._sheet_names)
                    self._sheet_var.set(self._sheet_names[0])
                self._current_sheet = self._sheet_names[0] if self._sheet_names else None

            self._read_and_refresh()

        except Exception as exc:
            messagebox.showerror(
                "Erreur de lecture",
                f"Impossible de lire le fichier :\n{exc}",
                parent=self,
            )
            self._cancel()

    def _on_sheet_changed(self):
        self._current_sheet = self._sheet_var.get()
        try:
            self._read_and_refresh()
        except Exception as exc:
            messagebox.showerror("Erreur", str(exc), parent=self)

    def _read_and_refresh(self):
        self._df_raw, self._has_header, self._info = read_tabular_raw(
            self.filepath,
            sheet_name=self._current_sheet,
        )
        self._header_var.set(self._has_header)
        self._refresh_preview()

    def _on_header_toggled(self):
        self._has_header = self._header_var.get()
        self._refresh_preview()

    # --------------------------------------------------------- aperçu

    def _refresh_preview(self):
        if self._df_raw is None:
            return

        # Extraire noms de colonnes
        if self._has_header:
            self._col_names = extract_header_names(self._df_raw)
        else:
            self._col_names = [f"Col {i + 1}" for i in range(len(self._df_raw.columns))]

        # Construire le DataFrame numérique
        self._df_numeric = build_data_df(self._df_raw, self._has_header)

        # Mettre à jour le Treeview
        self._update_treeview()

        # Mettre à jour les stats
        self._update_stats()

        # Mettre à jour les combos de mapping
        self._update_mapping_combos()

    def _update_treeview(self):
        # Effacer
        self._tree.delete(*self._tree.get_children())
        for col in self._tree["columns"]:
            self._tree.heading(col, text="")

        if self._df_numeric is None or self._df_numeric.empty:
            return

        cols = list(self._df_numeric.columns)
        col_ids = [str(c) for c in cols]
        self._tree["columns"] = col_ids

        for i, cid in enumerate(col_ids):
            heading = self._col_names[i] if i < len(self._col_names) else f"Col {i + 1}"
            self._tree.heading(cid, text=heading)
            self._tree.column(cid, width=110, minwidth=60, anchor="center")

        # Insérer les N premières lignes
        n = min(self.PREVIEW_ROWS, len(self._df_numeric))
        for row_idx in range(n):
            values = []
            for c in cols:
                v = self._df_numeric.iloc[row_idx, c] if isinstance(c, int) else self._df_numeric[c].iloc[row_idx]
                if pd.isna(v):
                    values.append("")
                else:
                    try:
                        values.append(f"{float(v):.4f}")
                    except (ValueError, TypeError):
                        values.append(str(v))
            self._tree.insert("", "end", values=values)

    def _update_stats(self):
        if self._df_numeric is None:
            self._stats_label.configure(text="")
            return

        stats = compute_preview_stats(self._df_numeric, self._col_names)
        parts = [f"Lignes : {stats['n_rows']}   |   Colonnes : {stats['n_cols']}"]

        for idx, col_info in stats["columns"].items():
            label = col_info["label"]
            n_nan = col_info["n_nan"]
            vmin = col_info["min"]
            vmax = col_info["max"]
            if vmin is not None:
                parts.append(
                    f"  {label} : min={vmin:.3f}  max={vmax:.3f}  NaN={n_nan}"
                )
            else:
                parts.append(f"  {label} : pas de valeurs numériques  NaN={n_nan}")

        self._stats_label.configure(text="\n".join(parts))

    def _update_mapping_combos(self):
        options = []
        for i, name in enumerate(self._col_names):
            options.append(f"{i + 1} — {name}")

        for key in ("depth", "qc", "qst"):
            combo = getattr(self, f"_combo_{key}")
            combo.configure(values=options)

        # Auto-sélection par défaut (colonnes 1, 2, 3)
        n = len(options)
        if n >= 1 and not self._mapping_vars["depth"].get():
            self._mapping_vars["depth"].set(options[0])
        if n >= 2 and not self._mapping_vars["qc"].get():
            self._mapping_vars["qc"].set(options[1])
        if n >= 3 and not self._mapping_vars["qst"].get():
            self._mapping_vars["qst"].set(options[2])

    # --------------------------------------------------------- Qt toggle

    def _on_qt_toggled(self):
        if self._is_qt_var.get():
            self._qt_info_label.configure(
                text="Qst sera calculé comme Qst = Qt - qc et stocké pour le traitement/graphique.",
                text_color=_COLORS["success"],
            )
        else:
            self._qt_info_label.configure(text="")

    # --------------------------------------------------------- actions

    def _parse_combo_index(self, var: ctk.StringVar) -> Optional[int]:
        """Extrait l'index 0-based depuis la valeur du combobox ('3 — nom')."""
        val = var.get()
        if not val:
            return None
        try:
            idx_str = val.split("—")[0].strip()
            return int(idx_str) - 1  # 0-based
        except (ValueError, IndexError):
            return None

    def _cancel(self):
        self.on_result(None)
        self.grab_release()
        self.destroy()

    def _import(self):
        # Valider le mapping
        depth_idx = self._parse_combo_index(self._mapping_vars["depth"])
        qc_idx = self._parse_combo_index(self._mapping_vars["qc"])
        qst_idx = self._parse_combo_index(self._mapping_vars["qst"])

        if depth_idx is None or qc_idx is None or qst_idx is None:
            messagebox.showwarning(
                "Mapping incomplet",
                "Veuillez sélectionner une colonne pour Profondeur, qc et Qst/Qt.",
                parent=self,
            )
            return

        if len({depth_idx, qc_idx, qst_idx}) < 3:
            messagebox.showwarning(
                "Colonnes dupliquées",
                "Les trois colonnes mappées doivent être différentes.",
                parent=self,
            )
            return

        # Vérifier que les colonnes sont numériques
        if self._df_numeric is not None:
            for idx, label in [(depth_idx, "Profondeur"), (qc_idx, "qc"), (qst_idx, "Qst/Qt")]:
                col = self._df_numeric.iloc[:, idx]
                if col.notna().sum() == 0:
                    messagebox.showerror(
                        "Colonne non numérique",
                        f"La colonne '{label}' ne contient aucune valeur numérique.",
                        parent=self,
                    )
                    return

        file_data = {
            "file_path": self.filepath,
            "file_name": Path(self.filepath).name,
            "source_type": "tabular",
            "has_header": self._has_header,
            "tabular_mapping": {
                "depth": depth_idx,
                "qc": qc_idx,
                "qst": qst_idx,
                "is_qt": self._is_qt_var.get(),
            },
            # Métadonnées par défaut (pas de .000 pour tabulaire)
            "Job Number": "",
            "TestNumber": "",
            "Date": "",
            "Location": "",
            "Operator": "",
        }

        # Infos CSV/Excel
        if self._info.get("csv_sep"):
            file_data["csv_sep"] = self._info["csv_sep"]
        if self._info.get("csv_decimal"):
            file_data["csv_decimal"] = self._info["csv_decimal"]
        if self._info.get("sheet_name"):
            file_data["sheet_name"] = self._info["sheet_name"]

        self.on_result(file_data)
        self.grab_release()
        self.destroy()
