import random
import queue
from typing import List, Dict, Optional
from cpt_files_indexer import CPTFilesIndexer
import threading
import os
import sys

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
        self.main_menu_font = ("Verdana", 17, "bold")

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
        self.workspaces = ["DONNÉES BRUTES", "OBSERVATIONS", "EXTRACTIONS", "TRAITER", "RECHERCHE RAPIDE", "PREFERENCES"]

        # Attributs pour l'indexeur CPT
        self.cpt_indexer = None
        self.search_results = []
        self.indexing_status = {
            "is_indexing": False,
            "progress": 0,
            "status": "not_started"
        }

        # Configuration pour l'indexation
        self.cpt_root_directory = r"Z:\Geotechnique\Résultats\V2 RESULTAT BRUT\2026"
        self.cpt_cache_file = "cpt_index_cache.json"

        # NOUVEAU : Queue thread-safe pour les mises à jour GUI
        self.gui_update_queue = queue.Queue()

    def initialize_indexer(self):
        """Initialise l'indexeur CPT."""
        self.cpt_indexer = CPTFilesIndexer(
            root_directory=self.cpt_root_directory,
            cache_file=self.cpt_cache_file
        )

    def start_background_indexing(self):
        """Lance l'indexation en arrière-plan avec progression réelle."""
        if not self.cpt_indexer:
            self.initialize_indexer()

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
                "title": "Régler pour tous les sondages",
                "items": [
                    {"title": "Matériel utilisé", "icon": "icons/drill.png", "action": "material_settings"},
                    {"title": "Date des essais", "icon": "icons/calendar.png", "action": "date_settings"},
                    {"title": "Décalage manomètres", "icon": "icons/settings.png", "action": "manometer_settings"},
                    {"title": "Capacité de l'appareil", "icon": "icons/capacity.png", "action": "capacity_settings"}
                ]
            },
            "toolbox2": {
                "title": "Mesures automatiques",
                "items": [
                    {"title": "Recherche rapide", "icon": "icons/quick-search.png", "action": "quick_search"},
                    {"title": "Importer depuis une clé USB", "icon": "icons/usb.png", "action": "usb_import"},
                    {"title": "Chercher fichiers GEF", "icon": "icons/folder.png", "action": "find_GEF_file"}
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
