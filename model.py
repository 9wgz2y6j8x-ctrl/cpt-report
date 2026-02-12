import random
import queue
from typing import List, Dict, Optional, Callable
from cpt_files_indexer import CPTFilesIndexer
from settings_manager import SettingsManager
import threading
import os
import sys
import copy


class RawDataManager:
    """
    Gestionnaire centralisé des fichiers GEF sélectionnés pour le traitement.

    Thread-safe, fournit un mécanisme robuste d'ajout/suppression/consultation
    des fichiers à traiter. Utilise le chemin absolu du fichier comme clé unique
    pour éviter les doublons.
    """

    # Champs éditables par l'utilisateur (correspondance clé interne -> label)
    EDITABLE_FIELDS = ["Job Number", "TestNumber", "Date", "Location"]

    def __init__(self):
        self._lock = threading.Lock()
        # Dictionnaire indexé par file_path (clé unique) -> données complètes du fichier
        self._files: Dict[str, Dict] = {}
        # Corrections utilisateur : {file_path: {field: corrected_value}}
        # Séparées des données terrain pour ne jamais les écraser
        self._overrides: Dict[str, Dict[str, str]] = {}
        # Ordre d'insertion pour maintenir un affichage cohérent
        self._insertion_order: List[str] = []
        # Callbacks de notification lors de changements
        self._on_change_callbacks: List[Callable] = []

    # ──────────────────────── Abonnement aux changements ────────────────────────

    def subscribe(self, callback: Callable):
        """Enregistre un callback appelé à chaque modification de la liste."""
        with self._lock:
            if callback not in self._on_change_callbacks:
                self._on_change_callbacks.append(callback)

    def unsubscribe(self, callback: Callable):
        """Retire un callback de notification."""
        with self._lock:
            if callback in self._on_change_callbacks:
                self._on_change_callbacks.remove(callback)

    def _notify(self):
        """Notifie tous les abonnés d'un changement (appelé sous le lock)."""
        callbacks = list(self._on_change_callbacks)
        for cb in callbacks:
            try:
                cb()
            except Exception as e:
                print(f"RawDataManager: erreur dans callback de notification: {e}")

    # ──────────────────────── Ajout de fichiers ────────────────────────

    # Résultat d'ajout : succès, doublon ou fichier introuvable
    ADD_OK = "ok"
    ADD_DUPLICATE = "duplicate"
    ADD_GEF_MISSING = "gef_missing"  # Rétro-compatible ; signifie "fichier introuvable"
    ADD_FILE_MISSING = ADD_GEF_MISSING  # Alias générique

    def add_file(self, file_data: Dict) -> str:
        """
        Ajoute un fichier à la liste des données brutes.

        Avant l'ajout, vérifie que le fichier GEF référencé par file_path
        existe toujours sur le disque.

        Args:
            file_data: Dictionnaire contenant au minimum 'file_path' (chemin GEF)
                       et 'file_name'. Peut aussi contenir 'meta_filepath' (.000).

        Returns:
            ADD_OK si le fichier a été ajouté,
            ADD_DUPLICATE s'il existait déjà,
            ADD_GEF_MISSING si le fichier GEF n'existe plus sur le disque.
        """
        file_path = file_data.get("file_path", "")
        if not file_path:
            return self.ADD_GEF_MISSING

        # Revalidation : le GEF doit exister au moment de l'ajout
        if not os.path.isfile(file_path):
            return self.ADD_GEF_MISSING

        with self._lock:
            if file_path in self._files:
                return self.ADD_DUPLICATE
            self._files[file_path] = copy.deepcopy(file_data)
            self._insertion_order.append(file_path)
            self._notify()
            return self.ADD_OK

    def add_files(self, files_data: List[Dict]) -> Dict[str, int]:
        """
        Ajoute plusieurs fichiers d'un coup.

        Returns:
            Dict avec les compteurs : {"added": N, "duplicates": N, "gef_missing": N}
        """
        added = 0
        duplicates = 0
        gef_missing = 0
        with self._lock:
            for file_data in files_data:
                file_path = file_data.get("file_path", "")
                if not file_path or not os.path.isfile(file_path):
                    gef_missing += 1
                    continue
                if file_path in self._files:
                    duplicates += 1
                    continue
                self._files[file_path] = copy.deepcopy(file_data)
                self._insertion_order.append(file_path)
                added += 1
            if added > 0:
                self._notify()
        return {"added": added, "duplicates": duplicates, "gef_missing": gef_missing}

    # ──────────────────────── Suppression de fichiers ────────────────────────

    def remove_file(self, file_path: str) -> bool:
        """Retire un fichier de la liste. Retourne True si trouvé et retiré."""
        with self._lock:
            if file_path in self._files:
                del self._files[file_path]
                self._insertion_order.remove(file_path)
                self._overrides.pop(file_path, None)
                self._notify()
                return True
            return False

    def remove_files(self, file_paths: List[str]) -> int:
        """Retire plusieurs fichiers. Retourne le nombre effectivement retiré."""
        removed = 0
        with self._lock:
            for fp in file_paths:
                if fp in self._files:
                    del self._files[fp]
                    self._insertion_order.remove(fp)
                    self._overrides.pop(fp, None)
                    removed += 1
            if removed > 0:
                self._notify()
        return removed

    def clear(self):
        """Vide entièrement la liste des fichiers."""
        with self._lock:
            self._files.clear()
            self._insertion_order.clear()
            self._overrides.clear()
            self._notify()

    # ──────────────────────── Consultation ────────────────────────

    def contains(self, file_path: str) -> bool:
        """Vérifie si un fichier est déjà dans la liste."""
        with self._lock:
            return file_path in self._files

    def get_all_files(self) -> List[Dict]:
        """Retourne une copie de tous les fichiers dans l'ordre d'insertion."""
        with self._lock:
            return [copy.deepcopy(self._files[fp]) for fp in self._insertion_order if fp in self._files]

    def get_file(self, file_path: str) -> Optional[Dict]:
        """Retourne les données d'un fichier spécifique, ou None."""
        with self._lock:
            data = self._files.get(file_path)
            return copy.deepcopy(data) if data else None

    @property
    def count(self) -> int:
        """Nombre de fichiers actuellement sélectionnés."""
        with self._lock:
            return len(self._files)

    def get_file_paths(self) -> List[str]:
        """Retourne la liste des chemins de fichiers dans l'ordre d'insertion."""
        with self._lock:
            return list(self._insertion_order)

    # ──────────────────────── Corrections utilisateur ────────────────────────

    def set_override(self, file_path: str, field: str, value: str):
        """
        Enregistre une correction utilisateur pour un champ donné.
        La valeur terrain originale reste intacte dans _files.
        Si la valeur corrigée est identique à l'originale, supprime l'override.
        """
        if field not in self.EDITABLE_FIELDS:
            return
        with self._lock:
            if file_path not in self._files:
                return
            original = self._files[file_path].get(field, "")
            if value == original:
                # Même valeur que l'originale : supprimer l'override s'il existe
                if file_path in self._overrides:
                    self._overrides[file_path].pop(field, None)
                    if not self._overrides[file_path]:
                        del self._overrides[file_path]
            else:
                if file_path not in self._overrides:
                    self._overrides[file_path] = {}
                self._overrides[file_path][field] = value
            self._notify()

    def get_effective_value(self, file_path: str, field: str) -> str:
        """Retourne la valeur corrigée si elle existe, sinon la valeur terrain."""
        with self._lock:
            if file_path in self._overrides and field in self._overrides[file_path]:
                return self._overrides[file_path][field]
            if file_path in self._files:
                return self._files[file_path].get(field, "")
            return ""

    def get_original_value(self, file_path: str, field: str) -> str:
        """Retourne la valeur terrain originale (jamais modifiée)."""
        with self._lock:
            if file_path in self._files:
                return self._files[file_path].get(field, "")
            return ""

    def has_override(self, file_path: str, field: str = None) -> bool:
        """
        Vérifie si un fichier a des corrections.
        Si field est spécifié, vérifie uniquement ce champ.
        """
        with self._lock:
            if file_path not in self._overrides:
                return False
            if field is None:
                return bool(self._overrides[file_path])
            return field in self._overrides[file_path]

    def get_overrides(self, file_path: str) -> Dict[str, str]:
        """Retourne toutes les corrections pour un fichier donné."""
        with self._lock:
            return dict(self._overrides.get(file_path, {}))

    def reset_overrides(self, file_path: str):
        """Rétablit toutes les données terrain pour un fichier (supprime toutes les corrections)."""
        with self._lock:
            if file_path in self._overrides:
                del self._overrides[file_path]
                self._notify()

    def reset_field_override(self, file_path: str, field: str):
        """Rétablit la donnée terrain pour un champ spécifique."""
        with self._lock:
            if file_path in self._overrides and field in self._overrides[file_path]:
                del self._overrides[file_path][field]
                if not self._overrides[file_path]:
                    del self._overrides[file_path]
                self._notify()

def get_resource_path(relative_path):
    """Obtient le chemin vers les ressources, que ce soit en dev ou en exe."""
    try:
        # PyInstaller crée un dossier temporaire et y place le bundle
        base_path = sys._MEIPASS
    except Exception:
        # En mode développement
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

class AppModel:
    def __init__(self):
        # Informations sur le logiciel
        self.software_name = "CPT REPORT Lite"
        self.software_version = "v0.2"
        self.splash_screen_delay = 3000  # en millisecondes

        # Liste des messages du splash screen
        self.splash_messages = [
            "Comprendre le sol, c'est comprendre la Terre.",
            "Le succès d'un projet se construit dès ses fondations.",
            "Le sol a toujours une histoire à raconter.",
            "La nature est notre plus ancien manuel d'ingénierie.",
            "La précision est le fondement de la sécurité.",
            "Le sol est la base de toute grande structure.",
            "L'ingénieur transforme les défis du sol en fondations solides.",
            "Un projet réussi commence par une bonne étude du sol.",
            "Le sol parle à celui qui sait écouter.",
            "Nous creusons pour construire, mais aussi pour apprendre.",
            "Chaque mesure nous rapproche d'une meilleure compréhension de la Terre.",
            "Le sol a sa propre mémoire.",
            "Il faut parfois creuser pour trouver la vérité.",
            "Un bon ingénieur écoute la Terre avant de la défier.",
            "La connaissance du sol est le début de chaque projet réussi.",
            "Nous bâtissons sur les épaules des études géotechniques.",
            "Chaque coup de sonde est un pas vers la sécurité.",
            "Construire, c'est aussi comprendre la Terre.",
            "Le sol est notre plus ancien allié dans la construction.",
            "Le monde sous la surface est aussi vaste que celui au-dessus.",
            "La terre cache ses secrets aux yeux pressés.",
            "L'étude du sol, c'est l'art de construire avec la nature.",
            "L'étalonnage régulier des équipements est indispensable pour des mesures fiables.",
            "La cohésion et l'angle de frottement sont des paramètres clés en stabilité.",
            "Considérez la nappe phréatique dans toutes vos analyses.",
            "L'hétérogénéité des sols impose la prudence.",
            "La roche s'effrite, le sable se déplace, mais le savoir persiste.",
            "Un plan sans sondage est une maison sans porte.",
            "Les sols sont comme les clients : imprévisibles et pleins de surprises.",
            "Un jour sans surprise géotechnique est un jour ennuyeux.",
            "Quand on me parle d'un terrain 'sans problème', je me méfie toujours.",
            "On ne peut pas tromper le sol, mais il peut nous tromper.",
            "Si le sol semble parfait, c'est sûrement qu'on a raté quelque chose.",
            "Si l'angle de talus dépasse celui de frottement, attendez-vous à un glissement…",
            "La prise en compte de l'effet des vibrations est essentielle dans les zones industrielles.",
            "Un plan sans nivellement est comme une boussole sans Nord."
        ]

        # Paramètres d'apparence de l'interface
        self.window_width = 1280
        self.window_height = 900
        self.side_panel_color = "#D9D9D9"
        self.side_panel_width = 300
        self.side_menu_button_width = 235
        self.side_menu_button_height = 31
        self.menu_bg_color = "#262626"
        self.menu_height = 81
        self.window_bg_color = "#F2F2F2"
        self.main_menu_font = ("Verdana", 15, "bold")

        # Paramètres du dégradé
        self.gradient_height = 11
        self.gradient_color_start = "#0115B8"
        self.gradient_color_end = "#FBBC3A"
        self.gradient_prolong_ratio = 0.35

        # État de l'application
        self.current_workspace = "DONNÉES BRUTES"
        self.search_text = ""
        self.current_sort_type = None

        # MODIFICATION : Ajout du nouveau workspace "RECHERCHE RAPIDE"
        self.workspaces = ["DONNÉES BRUTES", "FILTRER", "OBSERVATIONS", "EXTRACTIONS", "TRAITER", "RECHERCHE RAPIDE", "PREFERENCES"]

        # Attributs pour l'indexeur CPT
        self.cpt_indexer = None
        self.search_results = []
        self.indexing_status = {
            "is_indexing": False,
            "progress": 0,
            "status": "not_started"
        }

        # Configuration pour l'indexation
        self.cpt_cache_file = "cpt_index_cache.json"

        # NOUVEAU : Queue thread-safe pour les mises à jour GUI
        self.gui_update_queue = queue.Queue()

        # Gestionnaire de réglages persistants
        self.settings_manager = SettingsManager()

        # Gestionnaire des fichiers GEF sélectionnés pour traitement
        self.raw_data_manager = RawDataManager()

        # Répertoires d'indexation lus depuis les réglages utilisateur
        self.cpt_root_directories = self._get_index_directories()

    def _get_index_directories(self) -> list:
        """
        Lit les répertoires d'indexation depuis les réglages utilisateur.
        Retourne une liste de chemins valides (non vides).
        """
        directories = []
        for key in ("emplacement_gef", "emplacement_gef_secondaire"):
            path = self.settings_manager.get("dossiers_travail", key)
            if path and path.strip():
                directories.append(path.strip())
        return directories

    @property
    def cpt_root_directory(self) -> str:
        """Rétro-compatibilité : retourne le premier répertoire configuré."""
        return self.cpt_root_directories[0] if self.cpt_root_directories else ""

    @cpt_root_directory.setter
    def cpt_root_directory(self, value: str):
        """Rétro-compatibilité : met à jour le premier répertoire."""
        if self.cpt_root_directories:
            self.cpt_root_directories[0] = value
        elif value and value.strip():
            self.cpt_root_directories = [value]

    def initialize_indexer(self):
        """Initialise l'indexeur CPT avec les répertoires des réglages."""
        self.cpt_root_directories = self._get_index_directories()
        if not self.cpt_root_directories:
            print("Attention: Aucun répertoire d'indexation configuré dans les réglages.")
            self.cpt_indexer = None
            return
        self.cpt_indexer = CPTFilesIndexer(
            root_directories=self.cpt_root_directories,
            cache_file=self.cpt_cache_file
        )

    def start_background_indexing(self):
        """Lance l'indexation en arrière-plan avec progression réelle."""
        if not self.cpt_indexer:
            self.initialize_indexer()
        if not self.cpt_indexer:
            # Aucun répertoire configuré, signaler sans erreur
            self.gui_update_queue.put(("indexing_error",
                "Aucun répertoire d'essais configuré. "
                "Veuillez définir un emplacement dans les Préférences."))
            return

        def progress_callback(current, total):
            """Callback appelé pour chaque fichier traité."""
            if total > 0:
                percentage = (current / total) * 100
                self.gui_update_queue.put(("indexing_progress", {
                    "current": current,
                    "total": total,
                    "percentage": percentage
                }))

        def indexing_thread():
            self.indexing_status["is_indexing"] = True
            self.indexing_status["status"] = "indexing"
            try:
                # NOUVEAU : Passer le callback de progression
                result = self.cpt_indexer.index_files(
                    max_workers=8,
                    progress_callback=progress_callback
                )
                
                self.indexing_status["is_indexing"] = False
                self.indexing_status["status"] = "completed"
                self.indexing_status["result"] = result
                
                # Mettre le résultat dans la queue
                self.gui_update_queue.put(("indexing_completed", result))
                
            except Exception as e:
                self.indexing_status["is_indexing"] = False
                self.indexing_status["status"] = "error"
                self.indexing_status["error"] = str(e)
                self.gui_update_queue.put(("indexing_error", str(e)))
                print(f"Erreur lors de l'indexation : {e}")

        thread = threading.Thread(target=indexing_thread, daemon=True)
        thread.start()

    def get_gui_updates(self):
        """Récupère les mises à jour en attente pour la GUI."""
        updates = []
        try:
            while True:
                update = self.gui_update_queue.get_nowait()
                updates.append(update)
        except queue.Empty:
            pass
        return updates

    def search_cpt_files(self, query: str) -> List[Dict]:
        """Recherche dans les fichiers CPT indexés."""
        if not self.cpt_indexer:
            print("DEBUG: Indexeur non initialisé")
            return []

        results = self.cpt_indexer.search(query)
        self.search_results = results
        print(f"DEBUG: {len(results)} résultats trouvés pour '{query}'")
        return results

    def get_search_results(self) -> List[Dict]:
        """Retourne les derniers résultats de recherche."""
        return self.search_results

    def get_latest_date_files(self) -> List[Dict]:
        """Retourne les fichiers de la date la plus récente."""
        if not self.cpt_indexer:
            print("DEBUG: Indexeur non initialisé")
            return []

        results = self.cpt_indexer.get_files_by_latest_date()
        print(f"DEBUG: {len(results)} fichiers de la date la plus récente")
        return results

    def get_indexing_status(self) -> Dict:
        """Retourne le statut de l'indexation."""
        return self.indexing_status.copy()

    def get_cpt_statistics(self) -> Dict:
        """Retourne les statistiques de l'index CPT."""
        if not self.cpt_indexer:
            return {}
        return self.cpt_indexer.get_statistics()

    def get_random_splash_message(self):
        """Retourne un message aléatoire pour le splash screen."""
        return random.choice(self.splash_messages)

    def set_current_workspace(self, workspace_name):
        """Définit l'espace de travail actuel."""
        if workspace_name in self.workspaces:
            self.current_workspace = workspace_name
            return True
        return False

    def get_current_workspace(self):
        """Retourne l'espace de travail actuel."""
        return self.current_workspace

    def set_search_text(self, text):
        """Définit le texte de recherche actuel."""
        self.search_text = text

    def get_search_text(self):
        """Retourne le texte de recherche actuel."""
        return self.search_text

    def set_sort_type(self, sort_type):
        """Définit le type de tri actuel."""
        self.current_sort_type = sort_type

    def get_sort_type(self):
        """Retourne le type de tri actuel."""
        return self.current_sort_type

    def get_toolbox_data(self):
        """Retourne les données des toolboxes pour le panneau latéral."""
        return {
            "toolbox1": {
                "title": "Mesures automatiques",
                "items": [
                    {"title": "Recherche rapide", "icon": "icons/quick-search.png", "action": "quick_search"},
                    {"title": "Importer depuis une clé USB", "icon": "icons/usb.png", "action": "usb_import"},
                    {"title": "Chercher fichiers GEF", "icon": "icons/folder.png", "action": "find_GEF_file"}
                ]
            },
            "toolbox2": {
                "title": "Régler pour tous les sondages",
                "items": [
                    
                    {"title": "Matériel utilisé", "icon": "icons/drill.png", "action": "material_settings"},
                    {"title": "Date des essais", "icon": "icons/calendar.png", "action": "date_settings"},
                    {"title": "Décalage manomètres", "icon": "icons/settings.png", "action": "manometer_settings"},
                    {"title": "Capacité de l'appareil", "icon": "icons/capacity.png", "action": "capacity_settings"}
                ]
            },
            "toolbox3": {
                "title": "Mesures manuelles",
                "items": [
                    {"title": "Nouveau fichier de mesures", "icon": "icons/file.png", "action": "new_measurements"},
                    {"title": "Chercher fichiers Excel ou CSV", "icon": "icons/folder.png", "action": "find_measurements"}
                ]
            }
        }
