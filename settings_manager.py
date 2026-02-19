import json
import os
import sys
import copy
import uuid
from typing import Dict, List, Optional, Any


def _get_app_data_directory() -> str:
    """Retourne le dossier de préférences locales selon le système d'exploitation."""
    app_name = "CPTReportLite"

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA", "")
        if not base:
            base = os.path.expanduser("~")
        return os.path.join(base, app_name)

    elif sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", app_name
        )

    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        if not xdg:
            xdg = os.path.join(os.path.expanduser("~"), ".config")
        return os.path.join(xdg, app_name)


DEFAULT_SETTINGS: Dict[str, Any] = {
    "dossiers_travail": {
        "emplacement_gef": "",
        "emplacement_gef_secondaire": "",
        "dossier_resultats": "",
    },
    "controle_qualite": {
        "verifier_calibration": True,
        "verifier_vitesse_enfoncement": True,
        "verifier_valeurs_negatives_qc": False,
    },
    "optimisation_traitement": {
        "detection_preforages": True,
        "facteur_k_filtrage": 3,
    },
    "parametres_calcul": {
        "masse_volumique_sol_sec": 1800,
        "masse_volumique_sol_sature": 2000,
        "methode_calcul_portance": "De Beer (adapté)",
        "largeur_semelle_fondation_1": 0.6,
        "largeur_semelle_fondation_2": 1.5,
    },
    "unites": {
        "qc_mpa_max": 70.0,
        "qc_kg_max": 7000.0,
        "qst_kn_max": 600.0,
        "qst_kg_max": 60000.0,
        "percentile": 99.0,
        "tip_area_cm2": 10.0,
        "paire_graphique": "MPa_kN",
    },
    "machines": [],
}

DEFAULT_MACHINE: Dict[str, Any] = {
    "id": "",
    "nom": "Nouvelle machine",
    "capacite_tonnes": 20,
    "poids_tube_penetration": 0.0,
    "poids_tige_interieure": 0.0,
    "nb_tubes_avant_sol": 0,
}


class SettingsManager:
    """Gestionnaire de réglages persistants au format JSON.

    Les réglages sont stockés dans le dossier des préférences locales
    de l'OS (LOCALAPPDATA sous Windows, ~/Library/Application Support
    sous macOS, ~/.config sous Linux).
    """

    SETTINGS_FILENAME = "settings.json"

    def __init__(self):
        self._directory = _get_app_data_directory()
        self._filepath = os.path.join(self._directory, self.SETTINGS_FILENAME)
        self._settings: Dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        """Charge les réglages depuis le fichier JSON."""
        if not os.path.isfile(self._filepath):
            return

        try:
            with open(self._filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[SettingsManager] Erreur de lecture des réglages : {exc}")
            return

        self._merge(data)

    def _merge(self, data: Dict[str, Any]):
        """Fusionne les données chargées dans les réglages par défaut.

        Garantit que toute clé manquante reçoit sa valeur par défaut.
        """
        defaults = copy.deepcopy(DEFAULT_SETTINGS)

        for section_key, section_default in defaults.items():
            if section_key == "machines":
                self._settings["machines"] = data.get("machines", [])
                continue
            if isinstance(section_default, dict):
                loaded_section = data.get(section_key, {})
                if not isinstance(loaded_section, dict):
                    loaded_section = {}
                merged = {**section_default, **{
                    k: v for k, v in loaded_section.items()
                    if k in section_default
                }}
                self._settings[section_key] = merged
            else:
                self._settings[section_key] = data.get(section_key, section_default)

    def save(self):
        """Persiste les réglages sur disque."""
        os.makedirs(self._directory, exist_ok=True)
        try:
            with open(self._filepath, "w", encoding="utf-8") as fh:
                json.dump(self._settings, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            print(f"[SettingsManager] Erreur d'écriture des réglages : {exc}")

    # ------------------------------------------------------------------
    # Accesseurs génériques
    # ------------------------------------------------------------------

    def get(self, section: str, key: str) -> Any:
        """Retourne la valeur d'un réglage."""
        return self._settings.get(section, {}).get(key)

    def set(self, section: str, key: str, value: Any):
        """Définit la valeur d'un réglage et sauvegarde."""
        if section not in self._settings:
            self._settings[section] = {}
        self._settings[section][key] = value
        self.save()

    def get_section(self, section: str) -> Dict[str, Any]:
        """Retourne une copie d'une section complète."""
        return copy.deepcopy(self._settings.get(section, {}))

    @property
    def filepath(self) -> str:
        return self._filepath

    # ------------------------------------------------------------------
    # CRUD Machines
    # ------------------------------------------------------------------

    def get_machines(self) -> List[Dict[str, Any]]:
        """Retourne la liste des machines (copies)."""
        return copy.deepcopy(self._settings.get("machines", []))

    def add_machine(self, machine_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Ajoute une nouvelle machine et retourne sa copie."""
        new_machine = copy.deepcopy(DEFAULT_MACHINE)
        new_machine["id"] = uuid.uuid4().hex[:8]
        if machine_data:
            for key in new_machine:
                if key != "id" and key in machine_data:
                    new_machine[key] = machine_data[key]
        self._settings.setdefault("machines", []).append(new_machine)
        self.save()
        return copy.deepcopy(new_machine)

    def update_machine(self, machine_id: str, machine_data: Dict[str, Any]):
        """Met à jour une machine existante par son id."""
        machines = self._settings.get("machines", [])
        for machine in machines:
            if machine.get("id") == machine_id:
                for key in machine:
                    if key != "id" and key in machine_data:
                        machine[key] = machine_data[key]
                self.save()
                return True
        return False

    def delete_machine(self, machine_id: str) -> bool:
        """Supprime une machine par son id."""
        machines = self._settings.get("machines", [])
        original_len = len(machines)
        self._settings["machines"] = [
            m for m in machines if m.get("id") != machine_id
        ]
        if len(self._settings["machines"]) < original_len:
            self.save()
            return True
        return False
