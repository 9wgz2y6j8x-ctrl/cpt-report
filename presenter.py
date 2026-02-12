import sys
import os
from tkinter import filedialog
from model import AppModel
from view import AppView
from import_assistant import ImportAssistant

class AppPresenter:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self._setup_view_callbacks()
        
        # CHANGEMENT : Ne plus passer de callback à l'indexation
        self.model.start_background_indexing()

    def _setup_view_callbacks(self):
        """Configure les callbacks de la vue."""
        # Les callbacks seront définis après la création complète de la vue
        pass

    def on_workspace_selected(self, workspace_name):
        """Gère la sélection d'un espace de travail."""
        success = self.model.set_current_workspace(workspace_name)
        if success:
            self.view.display_workspace(workspace_name)

            # Désélectionner le segmented button si on navigue vers un workspace
            # qui n'en fait pas partie (PREFERENCES, RECHERCHE RAPIDE)
            segmented_values = ["DONNÉES BRUTES", "FILTRER", "OBSERVATIONS", "EXTRACTIONS", "TRAITER"]
            if workspace_name not in segmented_values:
                if hasattr(self.view, "top_menu_view"):
                    self.view.top_menu_view.deselect_all()
        else:
            print(f"Erreur: Workspace '{workspace_name}' introuvable")

    def on_settings_changed(self):
        """Callback déclenché quand un réglage est modifié dans la vue."""
        new_dirs = self.model._get_index_directories()
        if new_dirs != self.model.cpt_root_directories:
            self.model.cpt_root_directories = new_dirs
            # Réinitialiser l'indexeur et relancer l'indexation
            self.model.initialize_indexer()
            if self.model.cpt_indexer:
                self.model.start_background_indexing()

    def on_search_text_changed(self, search_text):
        """Gère le changement du texte de recherche avec recherche CPT."""
        print(f"DEBUG PRESENTER: Recherche pour '{search_text}'")
        self.model.set_search_text(search_text)
        
        # Vérifier que l'indexation est terminée
        status = self.model.get_indexing_status()
        if status.get("is_indexing"):
            print("DEBUG PRESENTER: Indexation en cours, recherche ignorée")
            return

        # Lancer la recherche CPT
        if len(search_text.strip()) >= 1:
            results = self.model.search_cpt_files(search_text)
            print(f"DEBUG PRESENTER: {len(results)} résultats trouvés")
            
            # SÉCURISÉ : Planifier la mise à jour GUI dans le thread principal
            if hasattr(self.view, 'quick_search_zone'):
                self.view.schedule_gui_update(
                    lambda: self.view.quick_search_zone.display_search_results(results)
                )
        elif search_text.strip() == "":
            # Afficher les premiers résultats si recherche vide
            results = self.model.search_cpt_files("")
            if hasattr(self.view, 'quick_search_zone'):
                self.view.schedule_gui_update(
                    lambda: self.view.quick_search_zone.display_search_results(results[:10])
                )
        else:
            # Effacer les résultats si recherche trop courte
            if hasattr(self.view, 'quick_search_zone'):
                self.view.schedule_gui_update(
                    lambda: self.view.quick_search_zone.clear_search_results()
                )

    def on_search_button_clicked(self):
        """Gère le clic sur le bouton de recherche avec focus sur CPT."""
        search_text = self.model.get_search_text()
        if search_text.strip():
            results = self.model.search_cpt_files(search_text)
            if hasattr(self.view, 'quick_search_zone'):
                self.view.schedule_gui_update(
                    lambda: self.view.quick_search_zone.display_search_results(results)
                )
            print(f"Recherche CPT : {len(results)} résultats pour '{search_text}'")
        else:
            self.view.focus_search_entry()

    def on_search_result_selected(self, result_data):
        """Gère la sélection d'un résultat de recherche."""
        print(f"Fichier sélectionné : {result_data.get('file_path')}")

    # ──────────────────────── Ajout aux données brutes ────────────────────────

    def on_add_to_raw_data(self, file_data):
        """Ajoute un fichier unique aux données brutes."""
        if not file_data or not file_data.get("file_path"):
            self._show_toast("Fichier invalide (chemin manquant)")
            return

        rdm = self.model.raw_data_manager
        result = rdm.add_file(file_data)
        name = file_data.get("file_name", "fichier")
        if result == rdm.ADD_OK:
            self._show_toast(f"'{name}' ajouté aux données brutes")
        elif result == rdm.ADD_GEF_MISSING:
            self._show_toast(f"'{name}' : fichier introuvable sur le disque")
        else:
            self._show_toast(f"'{name}' est déjà dans les données brutes")

    def on_add_multiple_to_raw_data(self, files_data):
        """Ajoute plusieurs fichiers aux données brutes."""
        if not files_data:
            return
        result = self.model.raw_data_manager.add_files(files_data)
        added = result["added"]
        duplicates = result["duplicates"]
        gef_missing = result["gef_missing"]
        total = len(files_data)

        parts = []
        if added > 0:
            parts.append(f"{added} ajouté(s)")
        if duplicates > 0:
            parts.append(f"{duplicates} doublon(s)")
        if gef_missing > 0:
            parts.append(f"{gef_missing} GEF introuvable(s)")

        if added == total:
            self._show_toast(f"{added} fichier(s) ajouté(s) aux données brutes")
        elif added == 0 and gef_missing == 0:
            self._show_toast(f"Les {total} fichier(s) sont déjà dans les données brutes")
        else:
            self._show_toast(f"{added}/{total} fichier(s) : {', '.join(parts)}")

    def _show_toast(self, message):
        """Affiche un toast de confirmation via la vue."""
        if hasattr(self.view, "quick_search_zone"):
            self.view.schedule_gui_update(
                lambda: self.view.quick_search_zone.show_toast(message)
            )

    def get_indexing_status(self):
        """Retourne le statut de l'indexation."""
        return self.model.get_indexing_status()

    def on_sort_action(self, sort_type):
        """Gère les actions de tri."""
        self.model.set_sort_type(sort_type)
        self._perform_sort(sort_type)
        print(f"Tri appliqué: {sort_type}")

    def on_toolbox_action(self, action_name):
        """Gère les actions des toolboxes du panneau latéral."""
        action_handlers = {
            "material_settings": self._handle_material_settings,
            "date_settings": self._handle_date_settings,
            "manometer_settings": self._handle_manometer_settings,
            "capacity_settings": self._handle_capacity_settings,
            "quick_search": self._handle_quick_search,
            "usb_import": self._handle_usb_import,
            "find_GEF_file": self._handle_find_GEF_file,
            "new_measurements": self._handle_new_measurements,
            "find_measurements": self._handle_find_measurements
        }

        handler = action_handlers.get(action_name)
        if handler:
            handler()
        else:
            print(f"Action '{action_name}' non reconnue")

    def _perform_search(self, search_text):
        """Effectue la recherche (logique métier)."""
        # TODO: Implémenter la logique de recherche
        pass

    def _perform_sort(self, sort_type):
        """Effectue le tri (logique métier)."""
        # TODO: Implémenter la logique de tri
        pass

    def _handle_material_settings(self):
        """Gère les réglages du matériel."""
        print("Matériel utilisé cliqué")
        # TODO: Implémenter la logique des réglages matériel

    def _handle_date_settings(self):
        """Gère les réglages de date."""
        print("Date des essais cliqué")
        # TODO: Implémenter la logique des réglages de date

    def _handle_manometer_settings(self):
        """Gère les réglages des manomètres."""
        print("Décalage manomètres cliqué")
        # TODO: Implémenter la logique des réglages manomètres

    def _handle_capacity_settings(self):
        """Gère les réglages de capacité."""
        print("Capacité de l'appareil cliqué")
        # TODO: Implémenter la logique des réglages de capacité

    def _handle_quick_search(self):
        """MODIFICATION : Affiche le workspace de recherche rapide."""
        print("Recherche rapide cliqué - Affichage du workspace RECHERCHE RAPIDE")
        self.on_workspace_selected("RECHERCHE RAPIDE")

    def _handle_usb_import(self):
        print("Import depuis clé USB cliqué")
        # TODO: Implémenter la logique

    def _extract_metadata_from_000(self, meta_filepath):
        """
        Extrait les métadonnées d'un fichier .000.

        Paramètres
        ----------
        meta_filepath : str
            Chemin vers le fichier .000

        Retours
        -------
        dict
            Dictionnaire contenant les métadonnées extraites
        """
        required_keys = ["Job Number", "Date", "Location", "TestNumber", "Operator"]
        metadata = {}

        if not os.path.isfile(meta_filepath):
            # Fichier .000 introuvable, retourner valeurs par défaut
            return {key: "Non trouvé" for key in required_keys}

        try:
            with open(meta_filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    for key in required_keys:
                        if key not in metadata and key in line:
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                metadata[key] = parts[1].strip()
                            break
                    if len(metadata) == len(required_keys):
                        break

            # Marquer les clés non trouvées
            for key in required_keys:
                if key not in metadata:
                    metadata[key] = "Non trouvé"

        except Exception as e:
            print(f"Erreur lors de la lecture de {meta_filepath}: {e}")
            metadata = {key: "Erreur" for key in required_keys}

        return metadata

    def _handle_find_GEF_file(self):
        """
        Gère la recherche de fichiers GEF via un dialogue de sélection.
        Permet la sélection multiple de fichiers .GEF et les ajoute aux données brutes.
        """
        # Ouvrir le dialogue de sélection de fichiers
        filepaths = filedialog.askopenfilenames(
            title="Sélectionner des fichiers GEF",
            filetypes=[
                ("Fichiers GEF", "*.gef *.GEF"),
                ("Tous les fichiers", "*.*")
            ]
        )

        # Si aucun fichier n'est sélectionné, ne rien faire
        if not filepaths:
            return

        # Préparer les données pour chaque fichier sélectionné
        files_data = []
        for filepath in filepaths:
            # Vérifier que le fichier existe
            if not os.path.isfile(filepath):
                continue

            # Chercher le fichier .000 correspondant
            base_path = os.path.splitext(filepath)[0]
            meta_filepath = base_path + ".000"

            # Extraire les métadonnées du fichier .000 si disponible
            metadata = self._extract_metadata_from_000(meta_filepath)

            # Construire le dictionnaire de données pour ce fichier
            file_data = {
                "file_path": filepath,
                "file_name": os.path.basename(filepath),
                "meta_filepath": meta_filepath if os.path.isfile(meta_filepath) else None,
                **metadata
            }

            files_data.append(file_data)

        # Ajouter tous les fichiers aux données brutes
        if files_data:
            self.on_add_multiple_to_raw_data(files_data)
        else:
            self._show_toast("Aucun fichier GEF valide sélectionné")

    def _handle_new_measurements(self):
        """Gère la création de nouveaux fichiers de mesures."""
        print("Nouveau fichier de mesures cliqué")
        # TODO: Implémenter la logique de création de fichier

    def _handle_find_measurements(self):
        """
        Gère la recherche et l'import de fichiers Excel/CSV via un dialog
        multi-sélection suivi d'un assistant d'import pour chaque fichier.
        """
        filepaths = filedialog.askopenfilenames(
            title="Sélectionner des fichiers Excel ou CSV",
            filetypes=[
                ("Fichiers tabulaires", "*.csv *.xls *.xlsx *.CSV *.XLS *.XLSX"),
                ("Fichiers CSV", "*.csv *.CSV"),
                ("Fichiers Excel", "*.xls *.xlsx *.XLS *.XLSX"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not filepaths:
            return

        # Traiter chaque fichier séquentiellement via l'assistant
        self._pending_imports = list(filepaths)
        self._import_next_file()

    def _import_next_file(self):
        """Lance l'assistant d'import pour le prochain fichier en attente."""
        if not self._pending_imports:
            return

        filepath = self._pending_imports.pop(0)
        if not os.path.isfile(filepath):
            self._show_toast(f"Fichier introuvable : {os.path.basename(filepath)}")
            self._import_next_file()
            return

        def on_result(file_data):
            if file_data is not None:
                self.on_add_to_raw_data(file_data)
            # Lancer le suivant après un court délai
            if self._pending_imports:
                self.view.after(200, self._import_next_file)

        try:
            ImportAssistant(self.view, filepath, on_result)
        except Exception as exc:
            self._show_toast(f"Erreur d'import : {exc}")
            self._import_next_file()

    def quit_app(self):
        """Ferme l'application."""
        self.view.destroy()

def main():
    model = AppModel()
    # Création de la vue avec un presenter temporaire (None)
    view = AppView(model, None)
    # Création du presenter en passant la référence à la vue
    presenter = AppPresenter(model, view)
    # Affectation du presenter à la vue
    view.presenter = presenter
    view.mainloop()

if __name__ == "__main__":
    main()
