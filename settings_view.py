import customtkinter as ctk
from tkinter import filedialog
import tkinter as tk
from typing import Callable, Optional, Dict, Any

from settings_manager import SettingsManager


# ---------------------------------------------------------------------------
# Constantes de style
# ---------------------------------------------------------------------------
_COLORS = {
    "bg": "#F2F2F2",
    "card": "#FFFFFF",
    "card_border": "#E0E0E0",
    "section_title_bg": "#0115B8",
    "section_title_fg": "#FFFFFF",
    "label_primary": "#1A1A1A",
    "label_secondary": "#6B7280",
    "accent": "#0115B8",
    "accent_hover": "#0030E0",
    "danger": "#DC2626",
    "danger_hover": "#B91C1C",
    "success": "#16A34A",
    "toggle_on": "#19CE1F",
    "toggle_off": "#C8CBD0",
    "input_border": "#D1D5DB",
    "input_bg": "#FAFAFA",
    "divider": "#E5E7EB",
    "path_bg": "#F9FAFB",
}

_FONTS = {
    "section_title": ("Verdana", 15, "bold"),
    "param_name": ("Verdana", 14, "bold"),
    "param_desc": ("Verdana", 12),
    "param_value": ("Verdana", 13),
    "button": ("Verdana", 13, "bold"),
    "button_sm": ("Verdana", 12),
    "machine_title": ("Verdana", 15, "bold"),
    "machine_field": ("Verdana", 13),
    "machine_label": ("Verdana", 12),
    "page_title": ("Verdana", 20, "bold"),
    "path_text": ("Consolas", 12),
}


# ═══════════════════════════════════════════════════════════════════════════
# Composants réutilisables
# ═══════════════════════════════════════════════════════════════════════════

class _SectionHeader(ctk.CTkFrame):
    """Bandeau de titre de section."""

    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, fg_color=_COLORS["section_title_bg"],
                         corner_radius=8, height=40, **kwargs)
        self.pack(fill="x", pady=(24, 0))
        self.pack_propagate(False)
        ctk.CTkLabel(
            self, text=f"  {title}", font=_FONTS["section_title"],
            text_color=_COLORS["section_title_fg"], anchor="w"
        ).pack(side="left", padx=12, fill="y")


class _SettingCard(ctk.CTkFrame):
    """Carte individuelle pour un paramètre (fond blanc, bords arrondis)."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent, fg_color=_COLORS["card"], corner_radius=10,
            border_width=1, border_color=_COLORS["card_border"], **kwargs
        )
        self.pack(fill="x", pady=(8, 0), ipady=6)


class _ToggleSettingCard(_SettingCard):
    """Carte avec toggle on/off pour un booléen."""

    def __init__(self, parent, title: str, description: str,
                 initial_value: bool, on_change: Callable[[bool], None]):
        super().__init__(parent)

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, padx=16, pady=10)

        ctk.CTkLabel(
            text_frame, text=title, font=_FONTS["param_name"],
            text_color=_COLORS["label_primary"], anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_frame, text=description, font=_FONTS["param_desc"],
            text_color=_COLORS["label_secondary"], anchor="w",
            justify="left", wraplength=520
        ).pack(anchor="w", pady=(2, 0))

        self._var = ctk.BooleanVar(value=initial_value)
        self._switch = ctk.CTkSwitch(
            self, variable=self._var, text="",
            onvalue=True, offvalue=False,
            progress_color=_COLORS["toggle_on"],
            button_color="#E0E0E0",
            button_hover_color="#BBBBBD",
            fg_color=_COLORS["toggle_off"],
            switch_width=52, switch_height=26,
            width=26, height=26,
            command=lambda: on_change(self._var.get())
        )
        self._switch.pack(side="right", padx=20)

    @property
    def value(self) -> bool:
        return self._var.get()


class _PathSettingCard(_SettingCard):
    """Carte avec sélecteur de dossier."""

    def __init__(self, parent, title: str, description: str,
                 initial_value: str, on_change: Callable[[str], None]):
        super().__init__(parent)
        self._on_change = on_change

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            text_frame, text=title, font=_FONTS["param_name"],
            text_color=_COLORS["label_primary"], anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_frame, text=description, font=_FONTS["param_desc"],
            text_color=_COLORS["label_secondary"], anchor="w",
            justify="left", wraplength=600
        ).pack(anchor="w", pady=(2, 0))

        row_frame = ctk.CTkFrame(self, fg_color="transparent")
        row_frame.pack(fill="x", padx=16, pady=(2, 10))

        self._path_var = ctk.StringVar(value=initial_value)
        self._entry = ctk.CTkEntry(
            row_frame, textvariable=self._path_var,
            font=_FONTS["path_text"],
            fg_color=_COLORS["path_bg"],
            border_color=_COLORS["input_border"],
            border_width=1, corner_radius=6, height=34,
            placeholder_text="Aucun dossier sélectionné"
        )
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._entry.bind("<FocusOut>", lambda _e: self._on_manual_edit())

        ctk.CTkButton(
            row_frame, text="Parcourir", font=_FONTS["button_sm"],
            fg_color=_COLORS["accent"], hover_color=_COLORS["accent_hover"],
            text_color="white", corner_radius=6, width=100, height=34,
            command=self._browse
        ).pack(side="right")

    def _browse(self):
        path = filedialog.askdirectory(title="Sélectionner un dossier")
        if path:
            self._path_var.set(path)
            self._on_change(path)

    def _on_manual_edit(self):
        self._on_change(self._path_var.get())

    @property
    def value(self) -> str:
        return self._path_var.get()


class _ComboSettingCard(_SettingCard):
    """Carte avec liste déroulante."""

    def __init__(self, parent, title: str, description: str,
                 values: list, initial_value, on_change: Callable):
        super().__init__(parent)

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, padx=16, pady=10)

        ctk.CTkLabel(
            text_frame, text=title, font=_FONTS["param_name"],
            text_color=_COLORS["label_primary"], anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_frame, text=description, font=_FONTS["param_desc"],
            text_color=_COLORS["label_secondary"], anchor="w",
            justify="left", wraplength=520
        ).pack(anchor="w", pady=(2, 0))

        str_values = [str(v) for v in values]
        self._var = ctk.StringVar(value=str(initial_value))
        self._combo = ctk.CTkComboBox(
            self, values=str_values, variable=self._var,
            font=_FONTS["param_value"], dropdown_font=_FONTS["param_value"],
            fg_color=_COLORS["input_bg"], border_color=_COLORS["input_border"],
            button_color=_COLORS["accent"],
            button_hover_color=_COLORS["accent_hover"],
            dropdown_fg_color=_COLORS["card"],
            corner_radius=6, width=100, height=34, state="readonly",
            command=lambda v: on_change(int(v))
        )
        self._combo.pack(side="right", padx=20)


# ═══════════════════════════════════════════════════════════════════════════
# Carte machine (CRUD)
# ═══════════════════════════════════════════════════════════════════════════

class _MachineCard(ctk.CTkFrame):
    """Carte affichant / éditant une machine CPT."""

    _CAPACITY_RANGE = (5, 30)
    _WEIGHT_RANGE = (0, 20)
    _NAME_MAX_LENGTH = 30
    _NB_TUBES_VALUES = ["0", "1", "2", "3"]

    def __init__(self, parent, machine_data: Dict[str, Any],
                 on_save: Callable[[str, Dict], None],
                 on_delete: Callable[[str], None]):
        super().__init__(
            parent, fg_color=_COLORS["card"], corner_radius=10,
            border_width=1, border_color=_COLORS["card_border"]
        )
        self.pack(fill="x", pady=(8, 0))

        self._machine_id = machine_data["id"]
        self._on_save = on_save
        self._on_delete = on_delete
        self._editing = False

        # -- Conteneur principal
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="x", padx=16, pady=12)

        # -- Ligne titre + boutons
        header = ctk.CTkFrame(self._content, fg_color="transparent")
        header.pack(fill="x")

        self._name_var = ctk.StringVar(value=machine_data.get("nom", ""))
        self._name_label = ctk.CTkLabel(
            header, text=machine_data.get("nom", "Machine"),
            font=_FONTS["machine_title"],
            text_color=_COLORS["accent"], anchor="w"
        )
        self._name_label.pack(side="left")

        # Boutons d'action
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        self._delete_btn = ctk.CTkButton(
            btn_frame, text="Supprimer", font=_FONTS["button_sm"],
            fg_color=_COLORS["danger"], hover_color=_COLORS["danger_hover"],
            text_color="white", corner_radius=6, width=90, height=30,
            command=self._confirm_delete
        )
        self._delete_btn.pack(side="right", padx=(6, 0))

        self._edit_btn = ctk.CTkButton(
            btn_frame, text="Modifier", font=_FONTS["button_sm"],
            fg_color=_COLORS["accent"], hover_color=_COLORS["accent_hover"],
            text_color="white", corner_radius=6, width=90, height=30,
            command=self._toggle_edit
        )
        self._edit_btn.pack(side="right")

        # -- Zone de détail (grille de champs)
        self._fields_frame = ctk.CTkFrame(self._content, fg_color="transparent")
        self._fields_frame.pack(fill="x", pady=(8, 0))

        self._build_fields(machine_data)
        self._set_fields_state("disabled")

    # ---- Construction des champs ----

    def _build_fields(self, data: Dict[str, Any]):
        grid = self._fields_frame
        for i in range(3):
            grid.grid_columnconfigure(i * 2, weight=0)
            grid.grid_columnconfigure(i * 2 + 1, weight=1)

        fields_def = [
            ("Nom", "nom", "entry", data.get("nom", ""), 0, 0),
            ("Capacité (tonnes)", "capacite_tonnes", "entry",
             str(data.get("capacite_tonnes", 20)), 0, 2),
            ("Tubes avant le sol", "nb_tubes_avant_sol", "combo",
             str(data.get("nb_tubes_avant_sol", 0)), 0, 4),
            ("Poids tube pénétration (kg)", "poids_tube_penetration", "entry",
             str(data.get("poids_tube_penetration", 0.0)), 1, 0),
            ("Poids tige intérieure (kg)", "poids_tige_interieure", "entry",
             str(data.get("poids_tige_interieure", 0.0)), 1, 2),
        ]

        self._field_widgets: Dict[str, Any] = {}

        for label_text, key, widget_type, default_val, row, col in fields_def:
            lbl = ctk.CTkLabel(
                grid, text=f"{label_text} :", font=_FONTS["machine_label"],
                text_color=_COLORS["label_secondary"], anchor="e"
            )
            lbl.grid(row=row, column=col, sticky="e", padx=(12, 4), pady=4)

            if widget_type == "entry":
                var = ctk.StringVar(value=default_val)
                widget = ctk.CTkEntry(
                    grid, textvariable=var, font=_FONTS["machine_field"],
                    fg_color=_COLORS["input_bg"],
                    border_color=_COLORS["input_border"],
                    border_width=1, corner_radius=6, height=32, width=150
                )
                widget.grid(row=row, column=col + 1, sticky="w", padx=(0, 16), pady=4)
                self._field_widgets[key] = (var, widget)

            elif widget_type == "combo":
                var = ctk.StringVar(value=default_val)
                widget = ctk.CTkComboBox(
                    grid, values=self._NB_TUBES_VALUES, variable=var,
                    font=_FONTS["machine_field"],
                    fg_color=_COLORS["input_bg"],
                    border_color=_COLORS["input_border"],
                    button_color=_COLORS["accent"],
                    button_hover_color=_COLORS["accent_hover"],
                    dropdown_fg_color=_COLORS["card"],
                    corner_radius=6, width=100, height=32, state="readonly"
                )
                widget.grid(row=row, column=col + 1, sticky="w", padx=(0, 16), pady=4)
                self._field_widgets[key] = (var, widget)

    def _set_fields_state(self, state: str):
        for key, (var, widget) in self._field_widgets.items():
            if isinstance(widget, ctk.CTkComboBox):
                widget.configure(state="readonly" if state == "disabled" else "readonly")
                # Pour les combos, on toggle via l'interactivité
                if state == "disabled":
                    widget.configure(
                        button_color=_COLORS["toggle_off"],
                        fg_color="#F0F0F0"
                    )
                else:
                    widget.configure(
                        button_color=_COLORS["accent"],
                        fg_color=_COLORS["input_bg"]
                    )
            else:
                widget.configure(
                    state=state,
                    fg_color="#F0F0F0" if state == "disabled" else _COLORS["input_bg"]
                )

    # ---- Actions ----

    def _toggle_edit(self):
        if not self._editing:
            self._editing = True
            self._edit_btn.configure(
                text="Enregistrer",
                fg_color=_COLORS["success"],
                hover_color="#15803D"
            )
            self._set_fields_state("normal")
        else:
            self._save()

    def _save(self):
        data = self._collect_data()
        if data is None:
            return
        self._on_save(self._machine_id, data)
        self._editing = False
        self._edit_btn.configure(
            text="Modifier",
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"]
        )
        self._name_label.configure(text=data.get("nom", "Machine"))
        self._set_fields_state("disabled")

    def _collect_data(self) -> Optional[Dict[str, Any]]:
        try:
            nom = " ".join(self._field_widgets["nom"][0].get().split())
            if not nom:
                nom = "Machine sans nom"
            nom = nom[:self._NAME_MAX_LENGTH]

            capacite_str = self._field_widgets["capacite_tonnes"][0].get().strip()
            capacite = float(capacite_str)
            capacite = max(self._CAPACITY_RANGE[0],
                           min(self._CAPACITY_RANGE[1], capacite))

            poids_tube = float(
                self._field_widgets["poids_tube_penetration"][0].get().strip() or "0"
            )
            poids_tube = max(self._WEIGHT_RANGE[0],
                             min(self._WEIGHT_RANGE[1], poids_tube))

            poids_tige = float(
                self._field_widgets["poids_tige_interieure"][0].get().strip() or "0"
            )
            poids_tige = max(self._WEIGHT_RANGE[0],
                             min(self._WEIGHT_RANGE[1], poids_tige))

            nb_tubes = int(
                self._field_widgets["nb_tubes_avant_sol"][0].get().strip() or "0"
            )

            # Update displayed values to reflect clamped values
            self._field_widgets["nom"][0].set(nom)
            self._field_widgets["capacite_tonnes"][0].set(str(capacite))
            self._field_widgets["poids_tube_penetration"][0].set(str(poids_tube))
            self._field_widgets["poids_tige_interieure"][0].set(str(poids_tige))

            return {
                "nom": nom,
                "capacite_tonnes": capacite,
                "poids_tube_penetration": poids_tube,
                "poids_tige_interieure": poids_tige,
                "nb_tubes_avant_sol": nb_tubes,
            }
        except (ValueError, KeyError):
            return None

    def _confirm_delete(self):
        self._on_delete(self._machine_id)


# ═══════════════════════════════════════════════════════════════════════════
# Vue principale du workspace REGLAGES
# ═══════════════════════════════════════════════════════════════════════════

class SettingsView(ctk.CTkFrame):
    """Interface complète du workspace REGLAGES.

    Affiche toutes les sections de paramètres dans un layout scrollable
    avec un style moderne cohérent avec le reste de l'application.
    """

    def __init__(self, parent, settings_manager: SettingsManager,
                 on_settings_changed: Optional[Callable] = None, **kwargs):
        super().__init__(parent, fg_color=_COLORS["bg"], corner_radius=0, **kwargs)
        self._sm = settings_manager
        self._on_settings_changed = on_settings_changed

        # Conteneur scrollable
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=_COLORS["bg"],
            scrollbar_button_color="#C4C4C4",
            scrollbar_button_hover_color="#A0A0A0",
            corner_radius=0
        )
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Contenu interne avec largeur maîtrisée
        self._inner = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._inner.pack(fill="x", expand=True, padx=32, pady=(16, 32))

        # Titre de la page
        ctk.CTkLabel(
            self._inner, text="Reglages",
            font=_FONTS["page_title"],
            text_color=_COLORS["label_primary"], anchor="w"
        ).pack(anchor="w", pady=(0, 4))

        # Chemin du fichier de config (info)
        ctk.CTkLabel(
            self._inner,
            text=f"Fichier de configuration : {self._sm.filepath}",
            font=("Consolas", 11),
            text_color=_COLORS["label_secondary"], anchor="w"
        ).pack(anchor="w", pady=(0, 12))

        # Construction des sections
        self._build_section_dossiers()
        self._build_section_qualite()
        self._build_section_optimisation()
        self._build_section_machines()

    # ------------------------------------------------------------------
    # Callback wrapper
    # ------------------------------------------------------------------
    def _notify_change(self):
        if self._on_settings_changed:
            self._on_settings_changed()

    def _make_setter(self, section: str, key: str):
        def _set(value):
            self._sm.set(section, key, value)
            self._notify_change()
        return _set

    # ------------------------------------------------------------------
    # Section : Dossiers de travail
    # ------------------------------------------------------------------
    def _build_section_dossiers(self):
        _SectionHeader(self._inner, "Dossiers de travail")

        data = self._sm.get_section("dossiers_travail")

        _PathSettingCard(
            self._inner,
            title="Emplacement des fichiers d'essais bruts (GEF)",
            description="Dossier principal contenant les fichiers .GEF des essais CPT.",
            initial_value=data.get("emplacement_gef", ""),
            on_change=self._make_setter("dossiers_travail", "emplacement_gef")
        )

        _PathSettingCard(
            self._inner,
            title="Emplacement secondaire des fichiers d'essais bruts",
            description="Dossier supplémentaire facultatif pour les fichiers GEF.",
            initial_value=data.get("emplacement_gef_secondaire", ""),
            on_change=self._make_setter("dossiers_travail",
                                        "emplacement_gef_secondaire")
        )

        _PathSettingCard(
            self._inner,
            title="Dossier d'enregistrement des résultats",
            description="Emplacement où les résultats traités seront enregistrés.",
            initial_value=data.get("dossier_resultats", ""),
            on_change=self._make_setter("dossiers_travail", "dossier_resultats")
        )

    # ------------------------------------------------------------------
    # Section : Contrôle de la qualité des essais
    # ------------------------------------------------------------------
    def _build_section_qualite(self):
        _SectionHeader(self._inner, "Controle de la qualite des essais")

        data = self._sm.get_section("controle_qualite")

        _ToggleSettingCard(
            self._inner,
            title="Verifier la presence d'un fichier de calibration valide",
            description=(
                "Controle que chaque essai est associe a un fichier "
                "de calibration en cours de validite."
            ),
            initial_value=data.get("verifier_calibration", True),
            on_change=self._make_setter("controle_qualite",
                                        "verifier_calibration")
        )

        _ToggleSettingCard(
            self._inner,
            title="Verifier la vitesse d'enfoncement et detecter les pauses",
            description=(
                "Analyse la vitesse de penetration et signale les arrets "
                "ou variations anormales pendant l'essai."
            ),
            initial_value=data.get("verifier_vitesse_enfoncement", True),
            on_change=self._make_setter("controle_qualite",
                                        "verifier_vitesse_enfoncement")
        )

        _ToggleSettingCard(
            self._inner,
            title="Verifier les valeurs negatives de qc",
            description=(
                "Detecte les valeurs de resistance de pointe (qc) negatives "
                "qui indiquent generalement un probleme de capteur ou de calibration."
            ),
            initial_value=data.get("verifier_valeurs_negatives_qc", False),
            on_change=self._make_setter("controle_qualite",
                                        "verifier_valeurs_negatives_qc")
        )

    # ------------------------------------------------------------------
    # Section : Optimisation du traitement
    # ------------------------------------------------------------------
    def _build_section_optimisation(self):
        _SectionHeader(self._inner, "Optimisation du traitement")

        data = self._sm.get_section("optimisation_traitement")

        _ToggleSettingCard(
            self._inner,
            title="Detection des preforages",
            description=(
                "Identifie automatiquement les zones de preforage "
                "dans les donnees et ajuste le traitement en consequence."
            ),
            initial_value=data.get("detection_preforages", True),
            on_change=self._make_setter("optimisation_traitement",
                                        "detection_preforages")
        )

        _ComboSettingCard(
            self._inner,
            title="Reglage du facteur k pour le filtrage des donnees",
            description=(
                "Le facteur k controle l'intensite du lissage applique "
                "aux mesures brutes. Une valeur plus elevee produit des courbes "
                "plus lisses."
            ),
            values=[3, 4, 5],
            initial_value=data.get("facteur_k_filtrage", 3),
            on_change=self._make_setter("optimisation_traitement",
                                        "facteur_k_filtrage")
        )

    # ------------------------------------------------------------------
    # Section : Configuration des machines
    # ------------------------------------------------------------------
    def _build_section_machines(self):
        _SectionHeader(self._inner, "Configuration des machines")

        # Bouton ajouter
        add_frame = ctk.CTkFrame(self._inner, fg_color="transparent")
        add_frame.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(
            add_frame, text="+ Ajouter une machine", font=_FONTS["button_sm"],
            fg_color="transparent", hover_color="#E0E4F0",
            text_color=_COLORS["accent"], border_width=1,
            border_color=_COLORS["accent"],
            corner_radius=8, height=34, width=200,
            command=self._add_machine
        ).pack(anchor="w")

        # Conteneur des cartes machines
        self._machines_container = ctk.CTkFrame(
            self._inner, fg_color="transparent"
        )
        self._machines_container.pack(fill="x", pady=(4, 0))

        self._refresh_machines()

    def _refresh_machines(self):
        for child in self._machines_container.winfo_children():
            child.destroy()

        machines = self._sm.get_machines()

        if not machines:
            ctk.CTkLabel(
                self._machines_container,
                text="Aucune machine configuree. Cliquez sur "
                     "\"+ Ajouter une machine\" pour commencer.",
                font=_FONTS["param_desc"],
                text_color=_COLORS["label_secondary"]
            ).pack(pady=20)
            return

        for machine in machines:
            _MachineCard(
                self._machines_container,
                machine_data=machine,
                on_save=self._save_machine,
                on_delete=self._delete_machine
            )

    def _add_machine(self):
        self._sm.add_machine()
        self._refresh_machines()
        self._notify_change()

    def _save_machine(self, machine_id: str, data: Dict[str, Any]):
        self._sm.update_machine(machine_id, data)
        self._notify_change()

    def _delete_machine(self, machine_id: str):
        self._sm.delete_machine(machine_id)
        self._refresh_machines()
        self._notify_change()
