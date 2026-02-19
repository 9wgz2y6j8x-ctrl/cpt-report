"""
cotes_view.py

Vue COTES : gestion des altitudes (cotes de départ) par essai CPT.
Affiche un Treeview global (1 ligne = 1 essai) avec :
  - N° dossier
  - N° essai
  - Profondeur max (m) détectée dans le fichier
  - Cote de départ (m) — éditable

Import depuis CSV/Excel ou GeoPackage via cotes_import.
"""

import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from typing import Optional, Dict

from cotes_import import (
    import_cotes_from_tabular,
    show_gpkg_import_dialog,
    ImportResult,
)

# ---------------------------------------------------------------------------
# Palette et typographie (cohérentes avec observations_view3)
# ---------------------------------------------------------------------------
COLORS = {
    "bg": "#E8EDF2",
    "card": "#F5F7FA",
    "sidebar": "#DFE4E9",
    "accent": "#0115B8",
    "accent_light": "#E8EDF8",
    "success": "#16A34A",
    "warning": "#D97706",
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
    "body": ("Verdana", 12),
    "small": ("Verdana", 10),
    "tiny": ("Verdana", 9),
    "mono": ("Consolas", 10),
    "header_job": ("Verdana", 13, "bold"),
}


class CotesView(ctk.CTkFrame):
    """Vue de gestion des cotes/altitudes pour chaque essai CPT."""

    def __init__(self, parent, model, presenter, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)

        self.model = model
        self.presenter = presenter
        self._is_visible = False
        self._rdm_callback = lambda: self._on_raw_data_changed()

        # Stockage des cotes : {file_path: float_or_None}
        self._cotes: Dict[str, Optional[float]] = {}

        # Référence à l'Entry d'édition in-place
        self._edit_entry: Optional[tk.Entry] = None
        self._edit_iid: Optional[str] = None

        # Mapping iid -> file_path pour le Treeview
        self._iid_to_filepath: Dict[str, str] = {}

        self._bindings_installed = False

        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        # Toolbar en haut
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
            title_container, text="Cotes de départ",
            font=FONTS["title"], text_color=COLORS["accent"]
        ).pack(side="left")

        self._count_label = ctk.CTkLabel(
            title_container, text="",
            font=FONTS["small"], text_color=COLORS["text_secondary"]
        )
        self._count_label.pack(side="left", padx=(16, 0))

        # Boutons d'import à droite
        right = ctk.CTkFrame(toolbar_inner, fg_color="transparent")
        right.pack(side="right", fill="y")

        btn_frame = ctk.CTkFrame(right, fg_color="transparent")
        btn_frame.pack(anchor="e", pady=18)

        self._btn_import_tabular = ctk.CTkButton(
            btn_frame, text="Importer CSV / Excel",
            font=("Verdana", 11), height=34, corner_radius=8,
            fg_color=COLORS["accent"], hover_color="#0228E0",
            command=self._on_import_tabular,
        )
        self._btn_import_tabular.pack(side="left", padx=(0, 8))

        self._btn_import_gpkg = ctk.CTkButton(
            btn_frame, text="Importer GeoPackage",
            font=("Verdana", 11), height=34, corner_radius=8,
            fg_color="#404040", hover_color="#555555",
            command=self._on_import_gpkg,
        )
        self._btn_import_gpkg.pack(side="left")

        # Zone de contenu
        content = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=8)
        content.pack(fill="both", expand=True, padx=10, pady=10)

        inner = ctk.CTkFrame(content, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        # Label de feedback (masqué par défaut)
        self._feedback_label = ctk.CTkLabel(
            inner, text="", font=FONTS["small"],
            text_color=COLORS["text_secondary"], wraplength=800,
        )

        self._create_tree(inner)

    def _create_tree(self, parent):
        """Crée le Treeview principal avec les 4 colonnes."""
        tree_container = ctk.CTkFrame(parent, fg_color="transparent")
        tree_container.pack(fill="both", expand=True)

        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Cotes.Treeview",
            background="#FFFFFF",
            foreground=COLORS["text_primary"],
            fieldbackground="#FFFFFF",
            font=FONTS["mono"],
            rowheight=28,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Cotes.Treeview.Heading",
            background=COLORS["accent_light"],
            foreground=COLORS["accent"],
            font=("Verdana", 9, "bold"),
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Cotes.Treeview",
            background=[("selected", COLORS["accent_light"])],
            foreground=[("selected", COLORS["accent"])],
        )
        style.map(
            "Cotes.Treeview.Heading",
            background=[("active", COLORS["accent_light"])],
        )

        scroll_y = ctk.CTkScrollbar(tree_container, orientation="vertical")

        self._tree = ttk.Treeview(
            tree_container,
            columns=("job", "test", "depth", "cote"),
            show="headings",
            style="Cotes.Treeview",
            selectmode="browse",
            yscrollcommand=scroll_y.set,
        )
        scroll_y.configure(command=self._tree.yview)

        self._tree.heading("job", text="N\u00b0 dossier")
        self._tree.heading("test", text="N\u00b0 essai")
        self._tree.heading("depth", text="Profondeur (m)")
        self._tree.heading("cote", text="Cote de d\u00e9part (m)")

        self._tree.column("job", width=180, minwidth=120, anchor="w")
        self._tree.column("test", width=140, minwidth=80, anchor="center")
        self._tree.column("depth", width=160, minwidth=100, anchor="center")
        self._tree.column("cote", width=180, minwidth=120, anchor="center")

        scroll_y.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)

        # Alternating rows
        self._tree.tag_configure("oddrow", background="#FFFFFF")
        self._tree.tag_configure("evenrow", background=COLORS["row_alt"])
        self._tree.tag_configure("edited", background="#F0FFF0")

        # Bindings
        self._tree.bind("<Double-1>", self._on_dblclick)
        self._tree.bind("<Return>", self._on_enter_key)
        self._tree.bind("<F2>", self._on_enter_key)

    # ------------------------------------------------------------------ lifecycle

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

    # ------------------------------------------------------------------ data

    def refresh_data(self):
        """Reconstruit le Treeview depuis RawDataManager."""
        self._cancel_edit()

        rdm = self.model.raw_data_manager
        files = rdm.get_all_files()

        # Lazy-import ObsFileEntry to get max_depth
        from observations_view3 import ObsFileEntry

        # Supprimer les anciennes lignes
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._iid_to_filepath.clear()

        for i, file_data in enumerate(files):
            fp = file_data.get("file_path", "")
            entry = ObsFileEntry(file_data, rdm)
            entry.ensure_loaded()

            job = rdm.get_effective_value(fp, "Job Number")
            test = rdm.get_effective_value(fp, "TestNumber")
            depth_str = f"{entry.max_depth:.2f}" if entry.max_depth is not None else "-"
            cote_val = self._cotes.get(fp)
            cote_str = f"{cote_val:.2f}" if cote_val is not None else ""

            tag = "evenrow" if i % 2 == 0 else "oddrow"
            iid = self._tree.insert(
                "", "end",
                values=(job, test, depth_str, cote_str),
                tags=(tag,),
            )
            self._iid_to_filepath[iid] = fp

        total = len(files)
        filled = sum(1 for v in self._cotes.values() if v is not None)
        self._count_label.configure(text=f"{filled}/{total} cotes renseignées")
        self._hide_feedback()

    def get_cote(self, file_path: str) -> Optional[float]:
        return self._cotes.get(file_path)

    def set_cote(self, file_path: str, value: Optional[float]):
        if value is not None:
            self._cotes[file_path] = value
        else:
            self._cotes.pop(file_path, None)

    def get_all_cotes(self) -> Dict[str, Optional[float]]:
        return dict(self._cotes)

    # ------------------------------------------------------------------ editing

    def _on_dblclick(self, event):
        region = self._tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self._tree.identify_column(event.x)
        col_idx = int(col.replace("#", "")) - 1
        if col_idx != 3:
            # Seule la colonne "Cote de départ" est éditable
            return
        iid = self._tree.identify_row(event.y)
        if iid:
            self._start_edit(iid)

    def _on_enter_key(self, event):
        sel = self._tree.selection()
        if sel:
            self._start_edit(sel[0])

    def _start_edit(self, iid):
        self._cancel_edit()

        bbox = self._tree.bbox(iid, "cote")
        if not bbox:
            self._tree.see(iid)
            self._tree.update_idletasks()
            bbox = self._tree.bbox(iid, "cote")
            if not bbox:
                return
        x, y, w, h = bbox

        values = self._tree.item(iid, "values")
        current_text = values[3] if len(values) > 3 else ""

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
        entry.bind("<Tab>", lambda e: self._commit_edit_and_move(1))
        entry.bind("<Escape>", lambda e: self._cancel_edit())
        entry.bind("<FocusOut>", lambda e: self._commit_edit())
        entry.bind("<Up>", lambda e: self._commit_edit_and_move(-1))
        entry.bind("<Down>", lambda e: self._commit_edit_and_move(1))

        self._edit_entry = entry
        self._edit_iid = iid
        self._tree.selection_set(iid)

    def _commit_edit(self):
        if not self._edit_entry:
            return
        raw = self._edit_entry.get().strip()
        iid = self._edit_iid
        fp = self._iid_to_filepath.get(iid, "")

        parsed = self._parse_number(raw)
        display = f"{parsed:.2f}" if parsed is not None else ""

        # Update Treeview
        values = list(self._tree.item(iid, "values"))
        values[3] = display
        self._tree.item(iid, values=values)

        # Store
        if parsed is not None:
            self._cotes[fp] = parsed
        else:
            self._cotes.pop(fp, None)

        self._cancel_edit()
        self._update_count()

    def _commit_edit_and_move(self, delta):
        if not self._edit_entry:
            return
        iid = self._edit_iid
        self._commit_edit()
        target = self._tree.next(iid) if delta > 0 else self._tree.prev(iid)
        if target:
            self._tree.selection_set(target)
            self._tree.see(target)
            self._start_edit(target)

    def _cancel_edit(self):
        if self._edit_entry:
            try:
                self._edit_entry.destroy()
            except Exception:
                pass
            self._edit_entry = None
            self._edit_iid = None

    @staticmethod
    def _parse_number(text: str) -> Optional[float]:
        """Parse un nombre avec tolérance virgule/point, vide → None."""
        if not text:
            return None
        text = text.replace(",", ".").strip()
        try:
            return float(text)
        except ValueError:
            return None

    def _update_count(self):
        total = len(self._iid_to_filepath)
        filled = sum(1 for fp in self._iid_to_filepath.values()
                     if self._cotes.get(fp) is not None)
        self._count_label.configure(text=f"{filled}/{total} cotes renseignées")

    # ------------------------------------------------------------------ bindings

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
        if self._edit_entry:
            return
        sel = self._tree.selection()
        if sel:
            prev_iid = self._tree.prev(sel[0])
            if prev_iid:
                self._tree.selection_set(prev_iid)
                self._tree.see(prev_iid)

    def _on_key_down(self, event):
        if self._edit_entry:
            return
        sel = self._tree.selection()
        if sel:
            next_iid = self._tree.next(sel[0])
            if next_iid:
                self._tree.selection_set(next_iid)
                self._tree.see(next_iid)

    # ------------------------------------------------------------------ import

    def _on_import_tabular(self):
        """Import cotes depuis CSV / Excel."""
        self._cancel_edit()
        # Build mapping test_name → file_path
        rdm = self.model.raw_data_manager
        essai_names = {}
        for fp in rdm.get_file_paths():
            job = rdm.get_effective_value(fp, "Job Number")
            test = rdm.get_effective_value(fp, "TestNumber")
            name = rdm.get_effective_value(fp, "file_name") or ""
            essai_names[fp] = {
                "job": job,
                "test": test,
                "file_name": name,
            }

        result: Optional[ImportResult] = import_cotes_from_tabular(
            self.winfo_toplevel(), essai_names
        )
        if result:
            self._apply_import_result(result)

    def _on_import_gpkg(self):
        """Import cotes depuis GeoPackage."""
        self._cancel_edit()
        rdm = self.model.raw_data_manager
        essai_names = {}
        for fp in rdm.get_file_paths():
            job = rdm.get_effective_value(fp, "Job Number")
            test = rdm.get_effective_value(fp, "TestNumber")
            name = rdm.get_effective_value(fp, "file_name") or ""
            essai_names[fp] = {
                "job": job,
                "test": test,
                "file_name": name,
            }

        settings_mgr = self.model.settings_manager
        result: Optional[ImportResult] = show_gpkg_import_dialog(
            self.winfo_toplevel(), essai_names, settings_mgr
        )
        if result:
            self._apply_import_result(result)

    def _apply_import_result(self, result: ImportResult):
        """Applique le résultat d'un import au store et rafraîchit."""
        for fp, cote_val in result.matched.items():
            self._cotes[fp] = cote_val

        self.refresh_data()
        self._show_feedback(result)

    def _show_feedback(self, result: ImportResult):
        """Affiche un message de feedback après import."""
        parts = []
        n_match = len(result.matched)
        n_unmatch = len(result.unmatched)
        n_err = len(result.errors)

        if n_match:
            parts.append(f"{n_match} cote(s) importée(s)")
        if n_unmatch:
            parts.append(f"{n_unmatch} station(s) non reconnue(s)")
        if n_err:
            parts.append(f"{n_err} erreur(s) de parsing")

        msg = " — ".join(parts) if parts else "Aucune donnée importée."
        color = COLORS["success"] if n_match and not n_err else (
            COLORS["warning"] if n_match else COLORS["text_secondary"]
        )
        self._feedback_label.configure(text=msg, text_color=color)
        self._feedback_label.pack(anchor="w", pady=(0, 6))

        # Masquer après 8 secondes
        self.after(8000, self._hide_feedback)

    def _hide_feedback(self):
        self._feedback_label.pack_forget()
