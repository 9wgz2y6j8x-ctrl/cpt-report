"""
import_assistant.py

Assistant d'importation de fichiers tabulaires (CSV / Excel) pour CPT.
Fenêtre Toplevel centrée avec :
- Aperçu des données
- Statistiques
- Mapping des colonnes (profondeur, qc, Qst/Qt)
- Conversion Qt -> Qst si nécessaire
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, List, Callable
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
# Couleurs et polices cohérentes avec l'application
# ---------------------------------------------------------------------------

_COLORS = {
    "bg": "#F2F2F2",
    "card": "#FFFFFF",
    "accent": "#0115B8",
    "accent_light": "#E8EDF8",
    "text": "#1A1A1A",
    "text_secondary": "#6B7280",
    "success": "#16A34A",
    "warning": "#D97706",
    "error": "#DC2626",
    "border": "#D1D5DB",
}

_FONTS = {
    "title": ("Verdana", 14, "bold"),
    "subtitle": ("Verdana", 11, "bold"),
    "body": ("Verdana", 10),
    "small": ("Verdana", 9),
    "mono": ("Consolas", 9),
}


# ---------------------------------------------------------------------------
# Assistant d'importation
# ---------------------------------------------------------------------------

class ImportAssistant(tk.Toplevel):
    """
    Fenêtre assistant pour importer un fichier CSV/Excel comme essai CPT.

    Retourne via le callback `on_result` un dict file_data prêt pour
    RawDataManager, ou None si l'utilisateur annule.
    """

    PREVIEW_ROWS = 15

    def __init__(
        self,
        parent: tk.Tk,
        filepath: str,
        on_result: Callable[[Optional[Dict]], None],
    ):
        super().__init__(parent)
        self.filepath = filepath
        self.on_result = on_result

        self.title(f"Import — {Path(filepath).name}")
        self.resizable(True, True)
        self.configure(bg=_COLORS["bg"])
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
        self._center_window(950, 720)
        self.after(100, self._load_file)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # Conteneur principal avec scrollbar
        main = tk.Frame(self, bg=_COLORS["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=12)

        # -- Section : sélection de feuille (Excel uniquement) --
        self._sheet_frame = tk.LabelFrame(
            main, text="  Feuille Excel  ", font=_FONTS["subtitle"],
            bg=_COLORS["bg"], fg=_COLORS["text"], padx=10, pady=6,
        )
        # Sera pack() seulement si Excel avec plusieurs feuilles

        self._sheet_var = tk.StringVar()
        self._sheet_combo = ttk.Combobox(
            self._sheet_frame, textvariable=self._sheet_var,
            state="readonly", width=40,
        )
        self._sheet_combo.pack(side="left", padx=(0, 10))
        self._sheet_combo.bind("<<ComboboxSelected>>", lambda e: self._on_sheet_changed())

        # -- Section : options header --
        self._opts_frame = tk.LabelFrame(
            main, text="  Options de lecture  ", font=_FONTS["subtitle"],
            bg=_COLORS["bg"], fg=_COLORS["text"], padx=10, pady=6,
        )
        self._opts_frame.pack(fill="x", pady=(0, 8))

        self._header_var = tk.BooleanVar(value=False)
        self._header_check = tk.Checkbutton(
            self._opts_frame, text="La première ligne contient des noms de colonnes (en-tête)",
            variable=self._header_var, font=_FONTS["body"],
            bg=_COLORS["bg"], activebackground=_COLORS["bg"],
            command=self._on_header_toggled,
        )
        self._header_check.pack(anchor="w")

        # -- Section : aperçu --
        preview_frame = tk.LabelFrame(
            main, text="  Aperçu des données  ", font=_FONTS["subtitle"],
            bg=_COLORS["bg"], fg=_COLORS["text"], padx=10, pady=6,
        )
        preview_frame.pack(fill="both", expand=True, pady=(0, 8))

        # Treeview pour l'aperçu
        tree_container = tk.Frame(preview_frame, bg=_COLORS["bg"])
        tree_container.pack(fill="both", expand=True)

        self._tree_scroll_x = tk.Scrollbar(tree_container, orient="horizontal")
        self._tree_scroll_y = tk.Scrollbar(tree_container, orient="vertical")

        self._tree = ttk.Treeview(
            tree_container,
            show="headings",
            height=self.PREVIEW_ROWS,
            xscrollcommand=self._tree_scroll_x.set,
            yscrollcommand=self._tree_scroll_y.set,
        )
        self._tree_scroll_x.config(command=self._tree.xview)
        self._tree_scroll_y.config(command=self._tree.yview)

        self._tree_scroll_y.pack(side="right", fill="y")
        self._tree.pack(side="top", fill="both", expand=True)
        self._tree_scroll_x.pack(side="bottom", fill="x")

        # -- Section : statistiques --
        self._stats_label = tk.Label(
            main, text="", font=_FONTS["small"],
            bg=_COLORS["bg"], fg=_COLORS["text_secondary"],
            justify="left", anchor="w",
        )
        self._stats_label.pack(fill="x", pady=(0, 8))

        # -- Section : mapping colonnes --
        mapping_frame = tk.LabelFrame(
            main, text="  Mapping des colonnes (obligatoire)  ", font=_FONTS["subtitle"],
            bg=_COLORS["bg"], fg=_COLORS["text"], padx=10, pady=8,
        )
        mapping_frame.pack(fill="x", pady=(0, 4))

        # Note cône 10 cm²
        note = (
            "Hypothèse cône 10 cm² : A = 0.001 m²  ⇒  1 MPa × A = 1 kN  "
            "⇒  valeurs numériques MPa ↔ kN identiques pour qc."
        )
        tk.Label(
            mapping_frame, text=note, font=_FONTS["small"],
            bg=_COLORS["accent_light"], fg=_COLORS["accent"],
            wraplength=880, justify="left", padx=8, pady=4,
        ).pack(fill="x", pady=(0, 8))

        grid = tk.Frame(mapping_frame, bg=_COLORS["bg"])
        grid.pack(fill="x")

        self._mapping_vars: Dict[str, tk.StringVar] = {}
        labels = [
            ("depth", "Profondeur (m)"),
            ("qc", "qc (MPa)"),
            ("qst", "Qst (kN)  ou  Qt (kN)"),
        ]
        for i, (key, label) in enumerate(labels):
            tk.Label(
                grid, text=label, font=_FONTS["body"],
                bg=_COLORS["bg"], fg=_COLORS["text"],
            ).grid(row=i, column=0, sticky="w", pady=3, padx=(0, 12))

            var = tk.StringVar()
            combo = ttk.Combobox(grid, textvariable=var, state="readonly", width=35)
            combo.grid(row=i, column=1, sticky="w", pady=3)
            self._mapping_vars[key] = var
            setattr(self, f"_combo_{key}", combo)

        # Checkbox Qt
        self._is_qt_var = tk.BooleanVar(value=False)
        qt_frame = tk.Frame(mapping_frame, bg=_COLORS["bg"])
        qt_frame.pack(fill="x", pady=(8, 0))

        self._qt_check = tk.Checkbutton(
            qt_frame,
            text="La 3e colonne est Qt (résistance totale) — Qst sera calculé : Qst = Qt − qc",
            variable=self._is_qt_var, font=_FONTS["body"],
            bg=_COLORS["bg"], activebackground=_COLORS["bg"],
            command=self._on_qt_toggled,
        )
        self._qt_check.pack(anchor="w")

        self._qt_info_label = tk.Label(
            qt_frame, text="", font=_FONTS["small"],
            bg=_COLORS["bg"], fg=_COLORS["success"],
            justify="left", anchor="w",
        )
        self._qt_info_label.pack(fill="x", padx=(24, 0))

        # -- Boutons --
        btn_frame = tk.Frame(main, bg=_COLORS["bg"])
        btn_frame.pack(fill="x", pady=(12, 0))

        tk.Button(
            btn_frame, text="Annuler", font=_FONTS["body"],
            width=14, command=self._cancel,
        ).pack(side="left")

        self._import_btn = tk.Button(
            btn_frame, text="Importer", font=_FONTS["subtitle"],
            width=14, bg=_COLORS["accent"], fg="white",
            activebackground="#0228E0", activeforeground="white",
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
                    self._sheet_combo["values"] = self._sheet_names
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
            self._stats_label.config(text="")
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

        self._stats_label.config(text="\n".join(parts))

    def _update_mapping_combos(self):
        options = []
        for i, name in enumerate(self._col_names):
            options.append(f"{i + 1} — {name}")

        for key in ("depth", "qc", "qst"):
            combo = getattr(self, f"_combo_{key}")
            combo["values"] = options

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
            self._qt_info_label.config(
                text="✓ Qst sera calculé comme Qst = Qt − qc et stocké pour le traitement/graphique.",
                fg=_COLORS["success"],
            )
        else:
            self._qt_info_label.config(text="")

    # --------------------------------------------------------- actions

    def _parse_combo_index(self, var: tk.StringVar) -> Optional[int]:
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
