"""
cotes_import.py

Logique d'import de cotes (altitudes) depuis :
  A) CSV / XLS / XLSX  — détection heuristique d'en-tête + colonnes station/cote
  B) GeoPackage (.gpkg) — choix couche + champs station/cote, persistance réglages

Retourne un ImportResult contenant les cotes matchées par file_path.
"""

import os
import re
import unicodedata
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Tuple, Any

import customtkinter as ctk

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import fiona
except ImportError:
    fiona = None

# ---------------------------------------------------------------------------
# Résultat d'import
# ---------------------------------------------------------------------------

@dataclass
class ImportResult:
    """Résultat d'un import de cotes."""
    matched: Dict[str, float] = field(default_factory=dict)      # file_path → cote
    unmatched: List[str] = field(default_factory=list)            # noms stations non matchés
    errors: List[str] = field(default_factory=list)               # messages d'erreur


# ---------------------------------------------------------------------------
# Utilitaires de normalisation / matching
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalise un texte pour le matching : lowercase, sans accents, trim."""
    if not text:
        return ""
    text = str(text).strip().lower()
    # Supprimer les accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Supprimer les espaces multiples
    text = re.sub(r"\s+", " ", text)
    return text


def _parse_float(val) -> Optional[float]:
    """Parse une valeur numérique avec tolérance virgule/point."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        import math
        if math.isnan(val):
            return None
        return float(val)
    s = str(val).strip().replace(",", ".")
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _build_essai_lookup(essai_names: Dict[str, dict]) -> Dict[str, str]:
    """Construit un index normalisé → file_path pour le matching.

    Essaie plusieurs variantes pour maximiser le matching :
      - job + test (ex: "P123 01")
      - test seul
      - filename sans extension
    """
    lookup: Dict[str, str] = {}
    for fp, info in essai_names.items():
        job = _normalize(info.get("job", ""))
        test = _normalize(info.get("test", ""))
        fname = _normalize(info.get("file_name", ""))

        # Variantes
        if job and test:
            lookup[f"{job} {test}"] = fp
            lookup[f"{job}{test}"] = fp
            lookup[f"{job}_{test}"] = fp
            lookup[f"{job}-{test}"] = fp
        if test:
            lookup[test] = fp
        if fname:
            # Sans extension
            base = fname.rsplit(".", 1)[0] if "." in fname else fname
            lookup[base] = fp

    return lookup


def _match_station(station_raw: str, lookup: Dict[str, str]) -> Optional[str]:
    """Tente de matcher un nom de station avec les essais connus.

    Retourne le file_path correspondant ou None.
    """
    norm = _normalize(station_raw)
    if not norm:
        return None

    # Match exact
    if norm in lookup:
        return lookup[norm]

    # Match partiel : la station normalisée est contenue dans une clé ou vice-versa
    for key, fp in lookup.items():
        if key in norm or norm in key:
            return fp

    return None


# ---------------------------------------------------------------------------
# Heuristiques de détection d'en-tête et colonnes (CSV / Excel)
# ---------------------------------------------------------------------------

_STATION_SYNONYMS = {
    "station", "nom station", "nom_station", "name", "station name",
    "essai", "nom essai", "nom_essai", "test", "testname", "test_name",
    "sondage", "nom sondage", "nom_sondage", "borehole", "point",
    "nom", "id", "code", "ref", "reference", "nom du sondage",
    "nom du point", "identifiant", "label",
}

_COTE_SYNONYMS = {
    "cote", "altitude", "z", "elevation", "elev", "cote z",
    "cote de depart", "cote_depart", "cote depart", "z sol",
    "z_sol", "altitude sol", "alt", "alt.", "hauteur",
    "cote ngf", "ngf", "cote terrain", "z terrain",
    "cote tn", "z tn", "tn",
}


def _score_column_name(col_name: str, synonyms: set) -> int:
    """Score un nom de colonne par rapport à un ensemble de synonymes.

    Retourne un score > 0 si match, 0 sinon. Plus le score est élevé, meilleur le match.
    """
    norm = _normalize(col_name)
    if not norm:
        return 0

    # Match exact
    if norm in synonyms:
        return 100

    # Match sans espaces/underscores/tirets
    stripped = re.sub(r"[\s_\-]+", "", norm)
    for syn in synonyms:
        syn_stripped = re.sub(r"[\s_\-]+", "", syn)
        if stripped == syn_stripped:
            return 90

    # Le nom contient un synonyme
    for syn in synonyms:
        if syn in norm:
            return 70
        if norm in syn:
            return 50

    # Match partiel sur mots
    norm_words = set(norm.split())
    for syn in synonyms:
        syn_words = set(syn.split())
        if norm_words & syn_words:
            return 30

    return 0


def _detect_header_row(df_raw, max_scan: int = 20) -> int:
    """Détecte la ligne d'en-tête parmi les N premières lignes.

    Heuristique : la première ligne où au moins 2 cellules matchent
    des synonymes de station ou cote.
    """
    n_rows = min(len(df_raw), max_scan)
    best_row = 0
    best_score = 0

    for i in range(n_rows):
        row = df_raw.iloc[i]
        score = 0
        for val in row:
            s = str(val).strip() if val is not None else ""
            score += _score_column_name(s, _STATION_SYNONYMS)
            score += _score_column_name(s, _COTE_SYNONYMS)
        if score > best_score:
            best_score = score
            best_row = i

    return best_row if best_score > 0 else 0


def _identify_columns(
    columns: List[str],
) -> Tuple[Optional[int], Optional[int]]:
    """Identifie les indices des colonnes station et cote parmi les en-têtes.

    Retourne (idx_station, idx_cote) ou None si non trouvé.
    """
    station_best = (-1, 0)
    cote_best = (-1, 0)

    for i, col in enumerate(columns):
        s_score = _score_column_name(col, _STATION_SYNONYMS)
        c_score = _score_column_name(col, _COTE_SYNONYMS)

        if s_score > station_best[1]:
            station_best = (i, s_score)
        if c_score > cote_best[1]:
            cote_best = (i, c_score)

    idx_s = station_best[0] if station_best[1] > 0 else None
    idx_c = cote_best[0] if cote_best[1] > 0 else None

    # Éviter de pointer la même colonne
    if idx_s is not None and idx_s == idx_c:
        # Prioriser celui avec le meilleur score
        if station_best[1] >= cote_best[1]:
            idx_c = None
        else:
            idx_s = None

    return idx_s, idx_c


# ---------------------------------------------------------------------------
# Import CSV / Excel
# ---------------------------------------------------------------------------

def _read_tabular_file(filepath: str) -> Optional["pd.DataFrame"]:
    """Lit un CSV ou Excel brut en DataFrame sans en-tête."""
    if pd is None:
        messagebox.showerror("Erreur", "pandas n'est pas installé.")
        return None

    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".csv":
            # Essayer différents séparateurs
            for sep in [";", ",", "\t"]:
                try:
                    df = pd.read_csv(filepath, sep=sep, header=None,
                                     encoding="utf-8", dtype=str)
                    if len(df.columns) >= 2:
                        return df
                except Exception:
                    continue
            # Fallback
            df = pd.read_csv(filepath, header=None, encoding="latin-1",
                             sep=None, engine="python", dtype=str)
            return df
        elif ext in (".xls", ".xlsx"):
            df = pd.read_excel(filepath, header=None, dtype=str)
            return df
    except Exception as exc:
        messagebox.showerror("Erreur de lecture",
                             f"Impossible de lire le fichier :\n{exc}")
    return None


def import_cotes_from_tabular(
    parent_window,
    essai_names: Dict[str, dict],
) -> Optional[ImportResult]:
    """Ouvre un dialogue fichier, lit CSV/Excel, matche et retourne les cotes.

    Arguments:
        parent_window: fenêtre parent tkinter
        essai_names: {file_path: {"job": str, "test": str, "file_name": str}}
    """
    filepath = filedialog.askopenfilename(
        parent=parent_window,
        title="Importer des cotes depuis CSV / Excel",
        filetypes=[
            ("Fichiers tabulaires", "*.csv *.xls *.xlsx *.CSV *.XLS *.XLSX"),
            ("Fichiers CSV", "*.csv *.CSV"),
            ("Fichiers Excel", "*.xls *.xlsx *.XLS *.XLSX"),
            ("Tous les fichiers", "*.*"),
        ],
    )
    if not filepath:
        return None

    df_raw = _read_tabular_file(filepath)
    if df_raw is None or df_raw.empty:
        return None

    # Détecter la ligne d'en-tête
    header_row = _detect_header_row(df_raw)

    # Extraire les noms de colonnes
    col_names = [str(v).strip() if v and str(v).strip() else f"Col {i+1}"
                 for i, v in enumerate(df_raw.iloc[header_row])]

    # Données après l'en-tête
    data_df = df_raw.iloc[header_row + 1:].reset_index(drop=True)
    data_df.columns = range(len(data_df.columns))

    # Identifier les colonnes station et cote
    idx_station, idx_cote = _identify_columns(col_names)

    if idx_station is None or idx_cote is None:
        # Fallback : afficher un message et tenter avec les 2 premières colonnes
        msg = "Détection automatique partielle des colonnes.\n"
        if idx_station is None and idx_cote is None:
            msg += "Aucune colonne 'station' ou 'cote' reconnue.\n"
            msg += "Utilisation des colonnes 1 (station) et 2 (cote) par défaut."
            idx_station = 0
            idx_cote = 1 if len(col_names) > 1 else 0
        elif idx_station is None:
            msg += f"Colonne cote détectée : '{col_names[idx_cote]}'.\n"
            msg += "Colonne station non détectée, utilisation de la première autre colonne."
            idx_station = 0 if idx_cote != 0 else (1 if len(col_names) > 1 else 0)
        else:
            msg += f"Colonne station détectée : '{col_names[idx_station]}'.\n"
            msg += "Colonne cote non détectée, utilisation de la première autre colonne."
            idx_cote = 0 if idx_station != 0 else (1 if len(col_names) > 1 else 0)

        # On continue malgré tout (UX robuste)

    # Construire le lookup
    lookup = _build_essai_lookup(essai_names)

    result = ImportResult()

    for _, row in data_df.iterrows():
        station_raw = str(row.get(idx_station, "")).strip() if idx_station is not None else ""
        cote_raw = row.get(idx_cote, None) if idx_cote is not None else None

        if not station_raw:
            continue

        fp = _match_station(station_raw, lookup)
        cote_val = _parse_float(cote_raw)

        if fp is None:
            result.unmatched.append(station_raw)
        elif cote_val is None:
            result.errors.append(f"'{station_raw}' : valeur cote invalide ({cote_raw})")
        else:
            result.matched[fp] = cote_val

    return result


# ---------------------------------------------------------------------------
# Import GeoPackage
# ---------------------------------------------------------------------------

def _read_gpkg_layers(filepath: str) -> List[str]:
    """Liste les couches disponibles dans un GeoPackage."""
    if fiona is None:
        messagebox.showerror("Erreur", "fiona n'est pas installé.\nInstaller avec : pip install fiona")
        return []
    try:
        return fiona.listlayers(filepath)
    except Exception as exc:
        messagebox.showerror("Erreur", f"Impossible de lire le GeoPackage :\n{exc}")
        return []


def _read_gpkg_fields(filepath: str, layer: str) -> List[str]:
    """Liste les champs (propriétés) d'une couche GPKG."""
    if fiona is None:
        return []
    try:
        with fiona.open(filepath, layer=layer, mode="r") as src:
            return list(src.schema["properties"].keys())
    except Exception:
        return []


def _read_gpkg_data(
    filepath: str, layer: str, field_station: str, field_cote: str
) -> List[Tuple[str, Any]]:
    """Lit les paires (station, cote) depuis une couche GPKG."""
    if fiona is None:
        return []
    rows = []
    try:
        with fiona.open(filepath, layer=layer, mode="r") as src:
            for feat in src:
                props = feat.get("properties", {})
                station = props.get(field_station, "")
                cote = props.get(field_cote, None)
                if station:
                    rows.append((str(station), cote))
    except Exception as exc:
        messagebox.showerror("Erreur", f"Erreur de lecture GPKG :\n{exc}")
    return rows


class _GpkgImportDialog(ctk.CTkToplevel):
    """Dialogue de sélection couche + champs pour import GeoPackage."""

    def __init__(self, parent, filepath: str, layers: List[str],
                 saved_prefs: Optional[dict] = None):
        super().__init__(parent)
        self.title("Import GeoPackage — Sélection des champs")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._filepath = filepath
        self._layers = layers
        self._fields: List[str] = []
        self._result: Optional[dict] = None
        self._saved_prefs = saved_prefs or {}

        # Dimensionner et centrer sur la fenêtre parente
        w, h = 520, 420
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{x}+{y}")

        self._build_ui()

        # Si prefs sauvegardées, pré-remplir
        saved_layer = self._saved_prefs.get("layer", "")
        if saved_layer in layers:
            self._layer_var.set(saved_layer)
            self._on_layer_changed(saved_layer)

        self.wait_window()

    @property
    def result(self) -> Optional[dict]:
        return self._result

    def _build_ui(self):
        main = ctk.CTkFrame(self, fg_color="#F2F2F2")
        main.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            main, text="Import depuis GeoPackage",
            font=("Verdana", 15, "bold"), text_color="#0115B8"
        ).pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(
            main, text=f"Fichier : {os.path.basename(self._filepath)}",
            font=("Verdana", 10), text_color="#6B7280"
        ).pack(anchor="w", pady=(0, 12))

        # Couche
        ctk.CTkLabel(main, text="Couche / Table :", font=("Verdana", 11, "bold")).pack(anchor="w")
        self._layer_var = ctk.StringVar(value=self._layers[0] if self._layers else "")
        self._layer_menu = ctk.CTkOptionMenu(
            main, values=self._layers, variable=self._layer_var,
            command=self._on_layer_changed, width=400,
        )
        self._layer_menu.pack(anchor="w", pady=(4, 12))

        # Champ station
        ctk.CTkLabel(main, text="Champ station / essai :", font=("Verdana", 11, "bold")).pack(anchor="w")
        self._station_var = ctk.StringVar()
        self._station_menu = ctk.CTkOptionMenu(
            main, values=["(charger une couche)"], variable=self._station_var,
            width=400,
        )
        self._station_menu.pack(anchor="w", pady=(4, 12))

        # Champ cote
        ctk.CTkLabel(main, text="Champ cote / altitude (Z) :", font=("Verdana", 11, "bold")).pack(anchor="w")
        self._cote_var = ctk.StringVar()
        self._cote_menu = ctk.CTkOptionMenu(
            main, values=["(charger une couche)"], variable=self._cote_var,
            width=400,
        )
        self._cote_menu.pack(anchor="w", pady=(4, 16))

        # Boutons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, text="Annuler", fg_color="#888888", hover_color="#666666",
            width=120, command=self._on_cancel,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="Importer", fg_color="#0115B8", hover_color="#0228E0",
            width=120, command=self._on_ok,
        ).pack(side="right")

        # Charger les champs de la première couche
        if self._layers:
            self._on_layer_changed(self._layers[0])

    def _on_layer_changed(self, layer_name: str):
        self._fields = _read_gpkg_fields(self._filepath, layer_name)
        if not self._fields:
            self._fields = ["(aucun champ)"]

        self._station_menu.configure(values=self._fields)
        self._cote_menu.configure(values=self._fields)

        # Pré-remplir depuis les prefs
        saved_station = self._saved_prefs.get("field_station", "")
        saved_cote = self._saved_prefs.get("field_cote", "")

        if saved_station in self._fields:
            self._station_var.set(saved_station)
        else:
            # Heuristique : essayer de trouver un champ correspondant
            best = self._auto_detect_field(self._fields, _STATION_SYNONYMS)
            self._station_var.set(best if best else self._fields[0])

        if saved_cote in self._fields:
            self._cote_var.set(saved_cote)
        else:
            best = self._auto_detect_field(self._fields, _COTE_SYNONYMS)
            self._cote_var.set(best if best else self._fields[0])

    @staticmethod
    def _auto_detect_field(fields: List[str], synonyms: set) -> Optional[str]:
        best_field = None
        best_score = 0
        for f in fields:
            score = _score_column_name(f, synonyms)
            if score > best_score:
                best_score = score
                best_field = f
        return best_field

    def _on_ok(self):
        layer = self._layer_var.get()
        station = self._station_var.get()
        cote = self._cote_var.get()

        if not layer or not station or not cote:
            messagebox.showwarning("Champs manquants",
                                   "Veuillez sélectionner la couche et les deux champs.",
                                   parent=self)
            return
        if station == cote:
            messagebox.showwarning("Champs identiques",
                                   "Les champs station et cote doivent être différents.",
                                   parent=self)
            return

        self._result = {
            "layer": layer,
            "field_station": station,
            "field_cote": cote,
        }
        self.destroy()

    def _on_cancel(self):
        self._result = None
        self.destroy()


def show_gpkg_import_dialog(
    parent_window,
    essai_names: Dict[str, dict],
    settings_manager=None,
) -> Optional[ImportResult]:
    """Ouvre un dialogue pour importer des cotes depuis un GeoPackage.

    Arguments:
        parent_window: fenêtre parent
        essai_names: {file_path: {"job", "test", "file_name"}}
        settings_manager: SettingsManager pour persister les choix
    """
    filepath = filedialog.askopenfilename(
        parent=parent_window,
        title="Importer des cotes depuis un GeoPackage",
        filetypes=[
            ("GeoPackage", "*.gpkg *.GPKG"),
            ("Tous les fichiers", "*.*"),
        ],
    )
    if not filepath:
        return None

    layers = _read_gpkg_layers(filepath)
    if not layers:
        messagebox.showinfo("GeoPackage vide",
                            "Aucune couche trouvée dans ce fichier.",
                            parent=parent_window)
        return None

    # Charger les prefs sauvegardées
    saved_prefs = {}
    if settings_manager:
        saved_prefs = settings_manager.get_section("import_cotes_gpkg") or {}

    dlg = _GpkgImportDialog(parent_window, filepath, layers, saved_prefs)
    choices = dlg.result
    if not choices:
        return None

    # Sauvegarder les choix
    if settings_manager:
        settings_manager.set("import_cotes_gpkg", "layer", choices["layer"])
        settings_manager.set("import_cotes_gpkg", "field_station", choices["field_station"])
        settings_manager.set("import_cotes_gpkg", "field_cote", choices["field_cote"])

    # Lire les données
    rows = _read_gpkg_data(
        filepath, choices["layer"],
        choices["field_station"], choices["field_cote"]
    )

    if not rows:
        messagebox.showinfo("Aucune donnée",
                            "Aucune donnée trouvée dans la couche sélectionnée.",
                            parent=parent_window)
        return ImportResult()

    # Matcher
    lookup = _build_essai_lookup(essai_names)
    result = ImportResult()

    for station_raw, cote_raw in rows:
        fp = _match_station(station_raw, lookup)
        cote_val = _parse_float(cote_raw)

        if fp is None:
            result.unmatched.append(station_raw)
        elif cote_val is None:
            result.errors.append(f"'{station_raw}' : valeur cote invalide ({cote_raw})")
        else:
            result.matched[fp] = cote_val

    return result
