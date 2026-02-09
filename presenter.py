import sys
from model import AppModel
from view import AppView

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
        else:
            print(f"Erreur: Workspace '{workspace_name}' introuvable")

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
        # TODO: Implémenter l'ouverture/affichage du fichier

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

    def _handle_find_GEF_file(self):
        """Gère la recherche de fichiers existants."""
        print("Chercher un fichier GEF existant cliqué")
        # TODO: Implémenter la logique de recherche de fichier

    def _handle_new_measurements(self):
        """Gère la création de nouveaux fichiers de mesures."""
        print("Nouveau fichier de mesures cliqué")
        # TODO: Implémenter la logique de création de fichier

    def _handle_find_measurements(self):
        """Gère la recherche de fichiers existants."""
        print("Chercher un fichier existant cliqué")
        # TODO: Implémenter la logique de recherche de fichier

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
