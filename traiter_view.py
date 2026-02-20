"""
traiter_view.py

Vue TRAITER : tableau de synthese des essais CPT avant generation du rapport.
Affiche un Treeview (style identique a la vue Cotes) avec :
  - N dossier, N essai, Machine, Section tube,
    delta Petit Mano, delta Grand Mano, Prof. atteinte, Prof. arrondie, alpha

Logique metier :
  - Prof. arrondie = arrondi au multiple de 0.20 m le plus proche
  - delta mano = entier signe (arrondi si decimale saisie)
  - Ordre personnalisable (Monter / Descendre), persiste pour le rapport
"""

import re
import math
import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from typing import Optional, Dict, List, Any

# ──────── Palette et typographie (coherentes avec cotes_view) ────────
COLORS = {
    "bg": "#E8EDF2",
    "card": "#F5F7FA",
    "accent": "#0115B8",
    "accent_light": "#E8EDF8",
    "text_primary": "#1A1A1A",
    "text_secondary": "#6B7280",
    "row_alt": "#F9FAFB",
    "border": "#D1D5DB",
}

FONTS = {
    "title": ("Verdana", 18, "bold"),
    "subtitle": ("Verdana", 13, "bold"),
    "body": ("Verdana", 12),
    "small": ("Verdana", 10),
    "mono": ("Consolas", 10),
    "button": ("Verdana", 11),
}

# Increment de profondeur pour l'arrondi
_DEPTH_INCREMENT = 0.20

# Sections tube possibles
_SECTION_TUBE_VALUES = ["Grande", "Petite"]


# ──────── Helpers ────────

def _arrondi_profondeur(prof: float) -> float:
    """Arrondit *prof* au multiple de 0.20 m le plus proche."""
    if prof <= 0:
        return 0.0
    return round(round(prof / _DEPTH_INCREMENT) * _DEPTH_INCREMENT, 2)


def _arrondi_entier(val) -> int:
    """Force un entier signe (arrondi si decimale)."""
    try:
        return round(float(val))
    except (ValueError, TypeError):
        return 0


def _natural_sort_key(text: str) -> list:
    """Cle de tri naturel : separe texte et nombres pour trier 'P2' < 'P10'."""
    parts = re.split(r'(\d+)', str(text) if text else "")
    return [int(p) if p.isdigit() else p.lower() for p in parts]


# ══════════════════════════════════════════════════════════════════════
# Vue principale
# ══════════════════════════════════════════════════════════════════════

class TraiterView(ctk.CTkFrame):
    """Vue de synthese des essais avant generation du rapport CPT."""

    def __init__(self, parent, model, presenter, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)

        self.model = model
        self.presenter = presenter
        self._is_visible = False
        self._rdm_callback = lambda: self._on_raw_data_changed()

        # Stockage des parametres par essai : {file_path: dict}
        self._essai_params: Dict[str, Dict[str, Any]] = {}

        # Ordre explicite des essais (liste de file_path)
        self._order: List[str] = []

        # References edition in-place
        self._edit_widget: Optional[tk.Widget] = None
        self._edit_iid: Optional[str] = None
        self._edit_col_key: Optional[str] = None

        # Mapping iid -> file_path
        self._iid_to_filepath: Dict[str, str] = {}

        self._bindings_installed = False

        self._build_ui()

    # ──────── Colonnes ────────

    _COLUMNS = [
        ("job", "N\u00b0 dossier", 70, "center"),
        ("test", "N\u00b0 essai", 70, "center"),
        ("machine", "Machine", 110, "w"),
        ("section", "Section tube", 80, "center"),
        ("delta_petit", "\u03b4 Petit Mano", 95, "center"),
        ("delta_grand", "\u03b4 Grand Mano", 95, "center"),
        ("prof_atteinte", "Prof. atteinte (m)", 120, "center"),
        ("prof_arrondie", "Prof. arrondie (m)", 125, "center"),
        ("alpha", "\u03b1", 50, "center"),
    ]

    # Colonnes editables et leur type d'edition
    _EDITABLE = {
        "machine": "combo_machine",
        "section": "combo_section",
        "delta_petit": "int",
        "delta_grand": "int",
        "alpha": "float",
    }

    # ──────── Construction UI ────────

    def _build_ui(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["card"], height=75, corner_radius=0)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        toolbar_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        toolbar_inner.pack(fill="both", expand=True, padx=20)

        left = ctk.CTkFrame(toolbar_inner, fg_color="transparent")
        left.pack(side="left", fill="y")

        title_container = ctk.CTkFrame(left, fg_color="transparent")
        title_container.pack(anchor="w", pady=14)

        ctk.CTkLabel(
            title_container, text="Traiter les essais",
            font=FONTS["title"], text_color=COLORS["accent"]
        ).pack(side="left")

        self._count_label = ctk.CTkLabel(
            title_container, text="",
            font=FONTS["small"], text_color=COLORS["text_secondary"]
        )
        self._count_label.pack(side="left", padx=(16, 0))

        # Boutons Monter / Descendre a droite
        right = ctk.CTkFrame(toolbar_inner, fg_color="transparent")
        right.pack(side="right", fill="y")

        btn_frame = ctk.CTkFrame(right, fg_color="transparent")
        btn_frame.pack(anchor="e", pady=18)

        self._btn_up = ctk.CTkButton(
            btn_frame, text="\u25b2  Monter", font=FONTS["button"],
            height=34, corner_radius=8, width=110,
            fg_color=COLORS["accent"], hover_color="#0228E0",
            command=self._move_up,
        )
        self._btn_up.pack(side="left", padx=(0, 8))

        self._btn_down = ctk.CTkButton(
            btn_frame, text="\u25bc  Descendre", font=FONTS["button"],
            height=34, corner_radius=8, width=110,
            fg_color=COLORS["accent"], hover_color="#0228E0",
            command=self._move_down,
        )
        self._btn_down.pack(side="left")

        # Zone de contenu
        content = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=8)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        inner = ctk.CTkFrame(content, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        self._create_tree(inner)

    def _create_tree(self, parent):
        """Cree le Treeview avec les colonnes definies."""
        tree_container = ctk.CTkFrame(parent, fg_color="transparent")
        tree_container.pack(fill="both", expand=True)

        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Traiter.Treeview",
            background="#FFFFFF",
            foreground=COLORS["text_primary"],
            fieldbackground="#FFFFFF",
            font=FONTS["mono"],
            rowheight=28,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Traiter.Treeview.Heading",
            background=COLORS["accent_light"],
            foreground=COLORS["accent"],
            font=("Verdana", 9, "bold"),
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Traiter.Treeview",
            background=[("selected", COLORS["accent_light"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.map(
            "Traiter.Treeview.Heading",
            background=[("active", COLORS["accent_light"])],
        )

        scroll_y = ctk.CTkScrollbar(tree_container, orientation="vertical")

        col_ids = [c[0] for c in self._COLUMNS]
        self._tree = ttk.Treeview(
            tree_container,
            columns=col_ids,
            show="headings",
            style="Traiter.Treeview",
            selectmode="browse",
            yscrollcommand=scroll_y.set,
        )
        scroll_y.configure(command=self._tree.yview)

        for col_id, heading, width, anchor in self._COLUMNS:
            self._tree.heading(col_id, text=heading)
            self._tree.column(col_id, width=width, minwidth=60, anchor=anchor)

        scroll_y.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

        # Tags pour alternance de lignes
        self._tree.tag_configure("oddrow", background="#FFFFFF")
        self._tree.tag_configure("evenrow", background=COLORS["row_alt"])

        # Bindings
        self._tree.bind("<Double-1>", self._on_dblclick)
        self._tree.bind("<Return>", self._on_enter_key)
        self._tree.bind("<F2>", self._on_enter_key)

    # ──────── Cycle de vie ────────

    def on_workspace_shown(self):
        self._is_visible = True
        self.model.raw_data_manager.subscribe(self._rdm_callback)
        self.refresh_data()
        self.after(200, self._setup_bindings)

    def on_workspace_hidden(self):
        self._is_visible = False
        self.model.raw_data_manager.unsubscribe(self._rdm_callback)
        self._cancel_edit()
        self._remove_bindings()

    def _on_raw_data_changed(self):
        if self._is_visible:
            self.after(100, self.refresh_data)

    # ──────── Donnees ────────

    def _get_machine_names(self) -> List[str]:
        """Retourne la liste triee des noms de machines depuis les reglages."""
        machines = self.model.settings_manager.get_machines()
        names = sorted([m.get("nom", "") for m in machines if m.get("nom")],
                       key=str.lower)
        return names if names else ["(aucune)"]

    def _default_params(self) -> Dict[str, Any]:
        """Parametres par defaut pour un essai."""
        return {
            "machine": "",
            "section": "Grande",
            "delta_petit": 0,
            "delta_grand": 0,
            "alpha": 1.5,
        }

    def refresh_data(self):
        """Reconstruit le Treeview depuis RawDataManager."""
        self._cancel_edit()

        rdm = self.model.raw_data_manager
        files = rdm.get_all_files()

        # Lazy-import pour la profondeur max
        from observations_view3 import ObsFileEntry

        # Detecter les nouveaux fichiers et conserver les existants
        current_fps = set()
        file_info: Dict[str, Dict] = {}

        for file_data in files:
            fp = file_data.get("file_path", "")
            current_fps.add(fp)

            entry = ObsFileEntry(file_data, rdm)
            entry.ensure_loaded()

            job = rdm.get_effective_value(fp, "Job Number") or ""
            test = rdm.get_effective_value(fp, "TestNumber") or ""
            max_depth = entry.max_depth

            file_info[fp] = {
                "job": job,
                "test": test,
                "max_depth": max_depth,
            }

            # Initialiser les params si nouveau
            if fp not in self._essai_params:
                self._essai_params[fp] = self._default_params()

        # Nettoyer les fichiers supprimes
        removed = set(self._essai_params.keys()) - current_fps
        for fp in removed:
            self._essai_params.pop(fp, None)

        # Mettre a jour l'ordre : retirer les absents, ajouter les nouveaux
        self._order = [fp for fp in self._order if fp in current_fps]
        new_fps = current_fps - set(self._order)
        if new_fps:
            # Tri naturel pour les nouveaux
            new_sorted = sorted(new_fps, key=lambda fp: (
                _natural_sort_key(file_info[fp]["job"]),
                _natural_sort_key(file_info[fp]["test"]),
            ))
            self._order.extend(new_sorted)

        # Reconstruire le Treeview
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._iid_to_filepath.clear()

        for i, fp in enumerate(self._order):
            info = file_info.get(fp, {})
            params = self._essai_params.get(fp, self._default_params())

            job = info.get("job", "")
            test = info.get("test", "")
            max_depth = info.get("max_depth")

            prof_atteinte = f"{max_depth:.2f}" if max_depth is not None else "-"
            prof_arrondie = ""
            if max_depth is not None:
                prof_arrondie = f"{_arrondi_profondeur(max_depth):.2f}"

            delta_petit = str(params.get("delta_petit", 0))
            delta_grand = str(params.get("delta_grand", 0))
            alpha_val = params.get("alpha", 1.5)
            alpha_str = f"{alpha_val:.1f}" if alpha_val != int(alpha_val) else str(int(alpha_val))

            tag = "evenrow" if i % 2 == 0 else "oddrow"
            iid = self._tree.insert(
                "", "end",
                values=(
                    job, test,
                    params.get("machine", ""),
                    params.get("section", "Grande"),
                    delta_petit, delta_grand,
                    prof_atteinte, prof_arrondie,
                    alpha_str,
                ),
                tags=(tag,),
            )
            self._iid_to_filepath[iid] = fp

        self._count_label.configure(text=f"{len(self._order)} essai(s)")

    # ──────── Monter / Descendre ────────

    def _move_up(self):
        sel = self._tree.selection()
        if not sel:
            return
        fp = self._iid_to_filepath.get(sel[0])
        if not fp:
            return
        idx = self._order.index(fp)
        if idx == 0:
            return
        self._order[idx - 1], self._order[idx] = self._order[idx], self._order[idx - 1]
        self.refresh_data()
        # Reselectionner
        self._select_filepath(fp)

    def _move_down(self):
        sel = self._tree.selection()
        if not sel:
            return
        fp = self._iid_to_filepath.get(sel[0])
        if not fp:
            return
        idx = self._order.index(fp)
        if idx >= len(self._order) - 1:
            return
        self._order[idx], self._order[idx + 1] = self._order[idx + 1], self._order[idx]
        self.refresh_data()
        self._select_filepath(fp)

    def _select_filepath(self, fp: str):
        """Selectionne la ligne correspondant a un file_path."""
        for iid, stored_fp in self._iid_to_filepath.items():
            if stored_fp == fp:
                self._tree.selection_set(iid)
                self._tree.see(iid)
                return

    # ──────── Edition in-place ────────

    def _col_key_from_event(self, event) -> Optional[str]:
        """Retourne la cle de colonne depuis un evenement de clic."""
        col = self._tree.identify_column(event.x)
        col_idx = int(col.replace("#", "")) - 1
        if 0 <= col_idx < len(self._COLUMNS):
            return self._COLUMNS[col_idx][0]
        return None

    def _on_dblclick(self, event):
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col_key = self._col_key_from_event(event)
        if col_key not in self._EDITABLE:
            return
        iid = self._tree.identify_row(event.y)
        if iid:
            self._start_edit(iid, col_key)

    def _on_enter_key(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        # Ouvrir la premiere colonne editable
        self._start_edit(sel[0], "machine")

    def _start_edit(self, iid: str, col_key: str):
        self._cancel_edit()

        edit_type = self._EDITABLE.get(col_key)
        if not edit_type:
            return

        bbox = self._tree.bbox(iid, col_key)
        if not bbox:
            self._tree.see(iid)
            self._tree.update_idletasks()
            bbox = self._tree.bbox(iid, col_key)
            if not bbox:
                return
        x, y, w, h = bbox

        self._edit_iid = iid
        self._edit_col_key = col_key

        fp = self._iid_to_filepath.get(iid, "")
        params = self._essai_params.get(fp, self._default_params())

        if edit_type == "combo_machine":
            values = self._get_machine_names()
            current = params.get("machine", "")
            self._create_combo_editor(x, y, w, h, values, current)

        elif edit_type == "combo_section":
            current = params.get("section", "Grande")
            self._create_combo_editor(x, y, w, h, _SECTION_TUBE_VALUES, current)

        elif edit_type == "int":
            current = str(params.get(col_key, 0))
            self._create_entry_editor(x, y, w, h, current)

        elif edit_type == "float":
            val = params.get(col_key, 1.5)
            current = f"{val:.1f}" if val != int(val) else str(int(val))
            self._create_entry_editor(x, y, w, h, current)

        self._tree.selection_set(iid)

    def _create_entry_editor(self, x, y, w, h, current_text: str):
        entry = tk.Entry(
            self._tree, font=FONTS["mono"],
            justify="center", bd=1, relief="solid",
            highlightthickness=1, highlightcolor=COLORS["accent"],
        )
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_text)
        entry.select_range(0, "end")
        entry.focus_set()

        entry.bind("<Return>", lambda e: self._commit_edit())
        entry.bind("<Tab>", lambda e: self._commit_edit_and_next())
        entry.bind("<Escape>", lambda e: self._cancel_edit())
        entry.bind("<FocusOut>", lambda e: self._commit_edit())

        self._edit_widget = entry

    def _create_combo_editor(self, x, y, w, h, values: list, current: str):
        var = tk.StringVar(value=current)
        combo = ttk.Combobox(
            self._tree, textvariable=var,
            values=values, state="readonly",
            font=FONTS["mono"], justify="center",
        )
        combo.place(x=x, y=y, width=max(w, 140), height=h)
        combo.focus_set()

        # Ouvrir la liste immediatement
        combo.event_generate("<Button-1>")

        combo.bind("<<ComboboxSelected>>", lambda e: self._commit_edit())
        combo.bind("<Escape>", lambda e: self._cancel_edit())
        combo.bind("<FocusOut>", lambda e: self.after(50, self._commit_edit))

        self._edit_widget = combo

    def _commit_edit(self):
        if not self._edit_widget:
            return
        iid = self._edit_iid
        col_key = self._edit_col_key
        fp = self._iid_to_filepath.get(iid, "")
        edit_type = self._EDITABLE.get(col_key, "")

        raw = ""
        if isinstance(self._edit_widget, ttk.Combobox):
            raw = self._edit_widget.get()
        elif isinstance(self._edit_widget, tk.Entry):
            raw = self._edit_widget.get().strip()

        # Appliquer la valeur
        params = self._essai_params.setdefault(fp, self._default_params())

        if edit_type == "combo_machine":
            params["machine"] = raw
        elif edit_type == "combo_section":
            params["section"] = raw if raw in _SECTION_TUBE_VALUES else "Grande"
        elif edit_type == "int":
            params[col_key] = _arrondi_entier(raw)
        elif edit_type == "float":
            try:
                params[col_key] = round(float(raw.replace(",", ".")), 2)
            except (ValueError, TypeError):
                pass

        self._cancel_edit()
        self._update_row(iid, fp)

    def _commit_edit_and_next(self):
        """Valide puis passe a la colonne editable suivante."""
        if not self._edit_widget:
            return
        iid = self._edit_iid
        col_key = self._edit_col_key
        self._commit_edit()

        # Trouver la prochaine colonne editable
        editable_keys = list(self._EDITABLE.keys())
        try:
            idx = editable_keys.index(col_key)
            if idx + 1 < len(editable_keys):
                self._start_edit(iid, editable_keys[idx + 1])
            else:
                # Passer a la ligne suivante, premiere colonne editable
                next_iid = self._tree.next(iid)
                if next_iid:
                    self._start_edit(next_iid, editable_keys[0])
        except ValueError:
            pass

    def _cancel_edit(self):
        if self._edit_widget:
            try:
                self._edit_widget.destroy()
            except Exception:
                pass
            self._edit_widget = None
            self._edit_iid = None
            self._edit_col_key = None

    def _update_row(self, iid: str, fp: str):
        """Met a jour les valeurs affichees d'une ligne."""
        from observations_view3 import ObsFileEntry

        rdm = self.model.raw_data_manager
        file_data = rdm.get_file(fp)
        if not file_data:
            return

        entry = ObsFileEntry(file_data, rdm)
        entry.ensure_loaded()

        params = self._essai_params.get(fp, self._default_params())

        job = rdm.get_effective_value(fp, "Job Number") or ""
        test = rdm.get_effective_value(fp, "TestNumber") or ""
        max_depth = entry.max_depth

        prof_atteinte = f"{max_depth:.2f}" if max_depth is not None else "-"
        prof_arrondie = ""
        if max_depth is not None:
            prof_arrondie = f"{_arrondi_profondeur(max_depth):.2f}"

        delta_petit = str(params.get("delta_petit", 0))
        delta_grand = str(params.get("delta_grand", 0))
        alpha_val = params.get("alpha", 1.5)
        alpha_str = f"{alpha_val:.1f}" if alpha_val != int(alpha_val) else str(int(alpha_val))

        self._tree.item(iid, values=(
            job, test,
            params.get("machine", ""),
            params.get("section", "Grande"),
            delta_petit, delta_grand,
            prof_atteinte, prof_arrondie,
            alpha_str,
        ))

    # ──────── Navigation clavier ────────

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
        if self._edit_widget:
            return
        sel = self._tree.selection()
        if sel:
            prev_iid = self._tree.prev(sel[0])
            if prev_iid:
                self._tree.selection_set(prev_iid)
                self._tree.see(prev_iid)

    def _on_key_down(self, event):
        if self._edit_widget:
            return
        sel = self._tree.selection()
        if sel:
            next_iid = self._tree.next(sel[0])
            if next_iid:
                self._tree.selection_set(next_iid)
                self._tree.see(next_iid)

    # ──────── Accesseurs pour le rapport ────────

    def get_ordered_essais(self) -> List[Dict[str, Any]]:
        """Retourne les essais dans l'ordre utilisateur avec tous les parametres.
        Utilise pour la generation du rapport client."""
        from observations_view3 import ObsFileEntry

        rdm = self.model.raw_data_manager
        result = []

        for fp in self._order:
            file_data = rdm.get_file(fp)
            if not file_data:
                continue

            entry = ObsFileEntry(file_data, rdm)
            entry.ensure_loaded()
            params = self._essai_params.get(fp, self._default_params())
            max_depth = entry.max_depth

            result.append({
                "file_path": fp,
                "job": rdm.get_effective_value(fp, "Job Number") or "",
                "test": rdm.get_effective_value(fp, "TestNumber") or "",
                "machine": params.get("machine", ""),
                "section": params.get("section", "Grande"),
                "delta_petit": params.get("delta_petit", 0),
                "delta_grand": params.get("delta_grand", 0),
                "prof_atteinte": max_depth,
                "prof_arrondie": _arrondi_profondeur(max_depth) if max_depth is not None else None,
                "alpha": params.get("alpha", 1.5),
            })

        return result
