import customtkinter as ctk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk
import os
import tkinter as tk
import threading
from model import get_resource_path 


class TopMenuView(ctk.CTkFrame):
    """
    Gère la barre de menu supérieure, incluant le bouton dossier et les boutons segmentés.
    """
    def __init__(self, parent, model, presenter, *args, **kwargs):
        super().__init__(parent, fg_color=model.menu_bg_color, height=model.menu_height, corner_radius=0, *args, **kwargs)
        self.model = model
        self.presenter = presenter

        # On place le cadre (barre de menu) en haut
        self.pack(side="top", fill="x")

        # Widgets
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(side="left")

        self.folder_button = ctk.CTkButton(
            self.button_frame,
            text="Dossier 49.530",
            font=("Verdana", 22, "bold", "italic"),
            fg_color="#0115B8",
            text_color="white",
            corner_radius=22,
            height=54,
            width=240
        )
        self.folder_button.pack(padx=20, pady=12, fill="y", expand=True)

        self.segmented_button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.segmented_button_frame.pack(side="left", expand=True, fill="x")

        self.menu_action_buttons = ctk.CTkSegmentedButton(
            self.segmented_button_frame,
            values=["DONNÉES BRUTES", "OBSERVATIONS", "EXTRACTIONS", "TRAITER"],
            command=self.on_menu_action_changed,
            font=self.model.main_menu_font,
            fg_color="#404040",
            text_color="white",
            corner_radius=22,
            height=54,
            unselected_color="#404040",
            unselected_hover_color="blue",
            selected_color="grey",
        )
        self.menu_action_buttons.pack(padx=135, fill="both", pady=12, expand=True)

        # Ajout du Canvas pour le dégradé sous la barre de menu
        self.gradient_canvas = ctk.CTkCanvas(parent, height=self.model.gradient_height, highlightthickness=0)
        self.gradient_canvas.pack(side="top", fill="x")

    def on_menu_action_changed(self, workspace_name):
        """Callback quand on clique sur un bouton du menu segmenté."""
        if self.presenter:
            self.presenter.on_workspace_selected(workspace_name)


class SideMenuView(ctk.CTkFrame):
    """
    Gère le panneau latéral, incluant les boutons de réglages et les toolboxes.
    """
    def __init__(self, parent, model, presenter, *args, **kwargs):
        super().__init__(parent, width=model.side_panel_width, fg_color=model.side_panel_color, corner_radius=0, *args, **kwargs)
        self.model = model
        self.presenter = presenter

        # On place le panneau latéral à gauche
        self.pack(side="left", fill="y")
        self.pack_propagate(False)

        # Création des toolboxes
        self._create_toolboxes()

        # Bouton "Réglages"
        self.user_preferences_button = self.create_side_menu_button(
            text="RÉGLAGES",
            command=lambda: self.presenter.on_workspace_selected("PREFERENCES") if self.presenter else None,
            relx=0.5, rely=0.985
        )

    def _create_toolboxes(self):
        """Crée dynamiquement toutes les toolboxes du panneau latéral."""
        toolbox_data = self.model.get_toolbox_data()
        
        # Stocker les références des toolboxes créées
        self.toolboxes = {}
        
        # Parcourir dynamiquement toutes les toolboxes définies dans le modèle
        for toolbox_key, toolbox_config in toolbox_data.items():
            toolbox = self.create_side_toolbox(
                title=toolbox_config["title"],
                items=toolbox_config["items"]
            )
            
            # Stocker la référence avec la clé du modèle
            self.toolboxes[toolbox_key] = toolbox

    def create_side_toolbox(self, title, items):
        """
        Crée une toolbox latérale avec un titre et une liste de boutons avec icônes.
        """
        # Frame principal de la toolbox avec bordure
        toolbox_frame = ctk.CTkFrame(
            self,
            fg_color="#F2F2F2",
            corner_radius=4,
            border_width=1,
            border_color="#86959E"
        )
        toolbox_frame.pack(padx=15, pady=(25, 0), fill="x")

        # Titre sur fond bleu
        title_frame = ctk.CTkFrame(
            toolbox_frame,
            fg_color="dark blue",
            corner_radius=1
        )
        title_frame.pack(fill="x", padx=1, pady=1)

        title_label = ctk.CTkLabel(
            title_frame,
            text=title,
            font=("Verdana", 14, "italic", "bold"),
            text_color="white",
        )
        title_label.pack(padx=6, pady=0)

        # Frame pour les boutons
        buttons_frame = ctk.CTkFrame(toolbox_frame, fg_color="transparent", corner_radius=0)
        buttons_frame.pack(fill="x", padx=10, pady=8)

        # Créer chaque bouton avec icône
        for item in items:
            icon_path = get_resource_path(item.get("icon")) if item.get("icon") else None
            button_title = item.get("title", "")
            action = item.get("action")

            # Charger l'icône si elle existe
            icon_image = None
            if icon_path and os.path.exists(icon_path):
                try:
                    img = Image.open(icon_path)
                    img = img.resize((20, 20), Image.Resampling.LANCZOS)
                    icon_image = ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))
                except Exception as e:
                    print(f"Erreur lors du chargement de l'icône {icon_path}: {e}")

            # Créer le bouton avec style personnalisé
            btn = ctk.CTkButton(
                buttons_frame,
                text=f" {button_title}",
                image=icon_image,
                compound="left",
                fg_color="transparent",
                text_color="black",
                hover_color="light gray",
                font=("Arial", 14),
                height=18,
                border_width=0,
                corner_radius=6,
                anchor="w",
                command=lambda a=action: self.presenter.on_toolbox_action(a) if self.presenter else None
            )
            btn.pack(fill="x", pady=1)

        return toolbox_frame

    def create_side_menu_button(self, text, command, relx, rely, **kwargs):
        """Crée un bouton pour le menu latéral."""
        defaults = {
            "parent": self,
            "font": ("Tahoma", 17, "bold"),
            "fg_color": "transparent",
            "text_color": "black",
            "hover_color": "#FBBC3A",
            "border_color": "black",
            "border_width": 2,
            "width": self.model.side_menu_button_width,
            "height": self.model.side_menu_button_height,
            "corner_radius": 22
        }
        defaults.update(kwargs)
        button = ctk.CTkButton(
            defaults["parent"],
            text=text,
            command=command,
            font=defaults["font"],
            fg_color=defaults["fg_color"],
            text_color=defaults["text_color"],
            hover_color=defaults["hover_color"],
            border_color=defaults["border_color"],
            border_width=defaults["border_width"],
            width=defaults["width"],
            height=defaults["height"],
            corner_radius=defaults["corner_radius"]
        )
        button.place(relx=relx, rely=rely, anchor="s")
        return button


class FileSearchZoneView(ctk.CTkFrame):
    """
    Classe dédiée à la zone de recherche de fichiers avec différents modes d'affichage.
    Gère l'interface de recherche et l'affichage des résultats pour le workspace "RECHERCHE RAPIDE".
    """
    def __init__(self, parent, model, presenter, *args, **kwargs):
        super().__init__(parent, fg_color="transparent", corner_radius=0, *args, **kwargs)
        self.model = model
        self.presenter = presenter
        
        # Attributs pour le debounce
        self.search_delay = 600  # 0.6 seconde en millisecondes
        self.search_after_id = None
        
        # Variables pour le tri
        self.sort_reverse = {}
        self.current_results = []  # Stocker les résultats actuels pour le tri
        
        # Variable pour suivre l'item survolé
        self.hovered_item = None
        
        # Variable pour suivre l'état de l'indexation
        self.indexing_completed = False
        
        # Variable pour le mode d'affichage actuel
        self.current_display_mode = "list"  # "list", "group_by_date", "group_by_folder", "group_by_location"
        
        # Configuration des colonnes
        self.columns_config = [
            {"text": "📁 Fichier", "key": "#0", "weight": 2},
            {"text": "📋 Dossier", "key": "dossier", "weight": 1}, 
            {"text": "🔬 Essai", "key": "essai", "weight": 1},
            {"text": "📍 Lieu", "key": "lieu", "weight": 2},
            {"text": "📅 Date", "key": "date", "weight": 1},
            {"text": "👤 Opérateur", "key": "operateur", "weight": 1}
        ]

        # Création de l'interface de recherche
        self._create_search_interface()

        # Positionnement du frame de recherche
        self.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.after(2000, self._check_indexing_status)

    def _check_indexing_status(self):
        """Vérifie et corrige l'état de l'indexation si nécessaire."""
        print("DEBUG VUE: Vérification automatique de l'état d'indexation...")
        
        if not self.indexing_completed:
            try:
                # Test si on peut faire une recherche
                test_results = self.model.search_cpt_files("")
                print(f"DEBUG VUE: Test de recherche retourne {len(test_results)} résultats")
                
                if len(test_results) > 0:
                    print("DEBUG VUE: CORRECTION - L'indexation est terminée mais le flag était à False")
                    self.indexing_completed = True
                    self.results_count_label.configure(
                        text="✅ Prêt à chercher", 
                        text_color="#28a745"
                    )
            except Exception as e:
                print(f"DEBUG VUE: Erreur lors de la vérification automatique : {e}")

    def _create_search_interface(self):
        """Crée tous les éléments de l'interface de recherche avec différents modes d'affichage."""
        # Frame pour le champ de recherche avec coins arrondis
        self.search_input_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=25, height=50)
        self.search_input_frame.pack(fill="x", pady=(0, 5))

        # Création du champ de recherche principal
        self._create_search_entry()

        # Création de l'icône/bouton de recherche
        self._create_search_icon()

        # Frame pour les boutons de tri
        self.buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.buttons_frame.pack(fill="x")

        # Création des boutons de tri et d'affichage
        self._create_sort_buttons()

        # Frame container pour les différents modes d'affichage
        self.display_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=8, border_width=0)
        self.display_container.pack(fill="both", expand=True, padx=5, pady=(10, 0))

        # Configuration du layout du container
        self.display_container.grid_rowconfigure(0, weight=0)  # Frame compteur (fixe)
        self.display_container.grid_rowconfigure(1, weight=1)  # Zone d'affichage (extensible)
        self.display_container.grid_columnconfigure(0, weight=1)

        # Création du frame pour le compteur de résultats
        self._create_results_count_frame()

        # NOUVEAU : Création des différentes zones d'affichage
        self._create_display_zones()

        # Statut initial
        self._show_initial_status()

    def _create_results_count_frame(self):
        """Crée le frame pour afficher le nombre de résultats."""
        self.results_count_frame = ctk.CTkFrame(
            self.display_container, 
            fg_color="#E8F4FD", 
            corner_radius=8,
            height=35
        )
        self.results_count_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 5))
        self.results_count_frame.grid_propagate(False)
        
        self.results_count_label = ctk.CTkLabel(
            self.results_count_frame,
            text="Commencez à chercher",
            font=("Arial", 14, "bold"),
            text_color="#1565C0"
        )
        self.results_count_label.pack(side="left", padx=15, pady=8)

    def _create_display_zones(self):
        """RESULTATS DE LA RECHERCHE : Crée les différentes zones d'affichage selon le mode."""
        # Container principal pour toutes les zones d'affichage
        self.main_display_frame = ctk.CTkFrame(self.display_container, fg_color="transparent")
        self.main_display_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.main_display_frame.grid_rowconfigure(0, weight=1)
        self.main_display_frame.grid_columnconfigure(0, weight=1)

        # 1. Zone d'affichage liste (mode par défaut - Treeview actuel)
        self._create_list_display_zone()

        # 2. Zone d'affichage groupé par date
        self._create_group_by_date_zone()

        # 3. Zone d'affichage groupé par n° de dossier
        self._create_group_by_folder_zone()

        # 4. Zone d'affichage groupé par localité
        self._create_group_by_location_zone()

        # Afficher le mode par défaut (liste)
        self._switch_display_mode("list")

    def _create_list_display_zone(self):
        """Crée la zone d'affichage en mode liste (Treeview)."""
        # Frame pour le mode liste
        self.list_display_frame = ctk.CTkFrame(self.main_display_frame, fg_color="transparent")
        
        # Frame pour les en-têtes
        self.list_headers_frame = ctk.CTkFrame(self.list_display_frame, fg_color="transparent")
        self.list_headers_frame.pack(fill="x", pady=(0, 2))
        
        # Création des en-têtes dans un frame global arrondi
        self._create_rounded_headers_container()

        # Frame pour le Treeview et scrollbars
        self.treeview_frame = ctk.CTkFrame(self.list_display_frame, fg_color="transparent")
        self.treeview_frame.pack(fill="both", expand=True)
        self.treeview_frame.grid_rowconfigure(0, weight=1)
        self.treeview_frame.grid_columnconfigure(0, weight=1)

        # Configuration du Treeview
        self._create_treeview()

    def _create_group_by_date_zone(self):
        """Crée la zone d'affichage groupé par date."""
        self.group_by_date_frame = ctk.CTkFrame(self.main_display_frame, fg_color="white")
        
        # Titre de la zone
        title_label = ctk.CTkLabel(
            self.group_by_date_frame,
            text="📅 Affichage groupé par date",
            font=("Arial", 18, "bold"),
            text_color="#1565C0"
        )
        title_label.pack(pady=20)
        
        # Zone scrollable pour les groupes
        self.date_groups_scrollable = ctk.CTkScrollableFrame(
            self.group_by_date_frame,
            fg_color="transparent"
        )
        self.date_groups_scrollable.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Label indicatif (sera remplacé par votre implémentation)
        info_label = ctk.CTkLabel(
            self.date_groups_scrollable,
            text="Zone d'affichage pour le groupement par date\n(À implémenter selon vos spécifications)",
            font=("Arial", 14),
            text_color="gray"
        )
        info_label.pack(pady=50)

    def _create_group_by_folder_zone(self):
        """Crée la zone d'affichage groupé par n° de dossier."""
        self.group_by_folder_frame = ctk.CTkFrame(self.main_display_frame, fg_color="transparent")
        
        # Zone scrollable pour les groupes
        self.folder_groups_scrollable = ctk.CTkScrollableFrame(
            self.group_by_folder_frame,
            fg_color="transparent"
        )
        self.folder_groups_scrollable.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Label indicatif (sera remplacé par votre implémentation)
        info_label = ctk.CTkLabel(
            self.folder_groups_scrollable,
            text="Zone d'affichage pour le groupement par n° de dossier\n(À implémenter selon vos spécifications)",
            font=("Arial", 14),
            text_color="gray"
        )
        info_label.pack(pady=50)

    def _create_group_by_location_zone(self):
        """Crée la zone d'affichage groupé par localité."""
        self.group_by_location_frame = ctk.CTkFrame(self.main_display_frame, fg_color="transparent")
        
        # Zone scrollable pour les groupes
        self.location_groups_scrollable = ctk.CTkScrollableFrame(
            self.group_by_location_frame,
            fg_color="transparent"
        )
        self.location_groups_scrollable.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Label indicatif (sera remplacé par votre implémentation)
        info_label = ctk.CTkLabel(
            self.location_groups_scrollable,
            text="Zone d'affichage pour le groupement par localité\n(À implémenter selon vos spécifications)",
            font=("Arial", 14),
            text_color="gray"
        )
        info_label.pack(pady=50)

    def _switch_display_mode(self, mode):
        """NOUVEAU : Change le mode d'affichage."""
        print(f"DEBUG: Changement vers le mode d'affichage: {mode}")
        
        # Cacher toutes les zones d'affichage
        if hasattr(self, 'list_display_frame'):
            self.list_display_frame.grid_forget()
        if hasattr(self, 'group_by_date_frame'):
            self.group_by_date_frame.grid_forget()
        if hasattr(self, 'group_by_folder_frame'):
            self.group_by_folder_frame.grid_forget()
        if hasattr(self, 'group_by_location_frame'):
            self.group_by_location_frame.grid_forget()

        # Afficher la zone correspondante au mode
        self.current_display_mode = mode
        
        if mode == "list":
            self.list_display_frame.grid(row=0, column=0, sticky="nsew")
            self._refresh_list_display()
        elif mode == "group_by_date":
            self.group_by_date_frame.grid(row=0, column=0, sticky="nsew")
            self._refresh_group_by_date_display()
        elif mode == "group_by_folder":
            self.group_by_folder_frame.grid(row=0, column=0, sticky="nsew")
            self._refresh_group_by_folder_display()
        elif mode == "group_by_location":
            self.group_by_location_frame.grid(row=0, column=0, sticky="nsew")
            self._refresh_group_by_location_display()

    def _refresh_list_display(self):
        """Rafraîchit l'affichage en mode liste."""
        if hasattr(self, 'results_tree') and self.current_results:
            self._refresh_treeview_display()

    def _refresh_group_by_date_display(self):
        """NOUVEAU : Rafraîchit l'affichage groupé par date."""
        print("DEBUG: Rafraîchissement de l'affichage groupé par date")
        # Ici vous implémenterez votre logique de groupement par date
        # Les données sont disponibles dans self.current_results
        pass

    def _refresh_group_by_folder_display(self):
        """Rafraîchit l'affichage groupé par n° de dossier."""
        print("DEBUG: Rafraîchissement de l'affichage groupé par dossier")

        # Nettoyer les widgets existants
        for widget in self.folder_groups_scrollable.winfo_children():
            widget.destroy()

        if not self.current_results:
            no_result_label = ctk.CTkLabel(
                self.folder_groups_scrollable,
                text="Aucun résultat à afficher",
                font=("Arial", 14),
                text_color="gray"
            )
            no_result_label.pack(pady=50)
            return

        # Grouper les résultats par Job Number
        grouped_results = {}
        for result in self.current_results:
            job_number = result.get('Job Number', 'N/A')
            if job_number not in grouped_results:
                grouped_results[job_number] = []
            grouped_results[job_number].append(result)

        # Créer un frame conteneur avec grid pour l'affichage des cartes
        cards_container = ctk.CTkFrame(self.folder_groups_scrollable, fg_color="transparent")
        cards_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Variables pour la disposition en grille
        row = 0
        col = 0
        max_cols = 3  # Nombre maximum de colonnes

        # Créer une carte pour chaque dossier
        for job_number, results in grouped_results.items():
            card = self._create_folder_card(cards_container, job_number, results)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            # Configurer le poids des colonnes pour une répartition équitable
            cards_container.grid_columnconfigure(col, weight=1, uniform="cards")

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _create_folder_card(self, parent, job_number, results):
        """Crée une carte pour un dossier avec toutes ses informations."""
        # Frame principal de la carte (fond blanc)
        card = ctk.CTkFrame(
            parent,
            fg_color="white",
            corner_radius=10,
            border_width=1,
            border_color="#E0E0E0"
        )

        # Header sous forme de bouton (remplace CTkFrame + CTkLabel)
        header_button = ctk.CTkButton(
            card,
            text=job_number,
            font=("Verdana", 18, "bold"),
            fg_color="#002AC2",
            hover_color="#0015A0",
            text_color="white",
            corner_radius=8,
            height=35,
            command=lambda: self._on_card_header_click(job_number, "dossier")
        )
        header_button.pack(fill="x", padx=5, pady=5)

        # Déterminer le lieu le plus fréquent
        location = self._get_most_frequent_location(results)

        # Nombre de CPT
        cpt_count = len(results)

        # Déterminer les dates (plus ancienne et plus récente)
        date_text = self._get_date_range(results)

        # Extraire les opérateurs
        operators_text = self._extract_operators(results)

        # Affichage du lieu
        location_label = ctk.CTkLabel(
            card,
            text=f"📍 {location.upper()}",
            font=("Verdana", 14, "bold"),
            text_color="#000000",
            anchor="w",
            height=16
        )
        location_label.pack(fill="x", padx=10, pady=0)

        # Affichage du nombre de CPT
        cpt_label = ctk.CTkLabel(
            card,
            text=f"{cpt_count} CPT",
            font=("Verdana", 14, "bold", "italic"),
            text_color="#0115B8",
            anchor="w"
        )
        cpt_label.pack(fill="x", padx=10, pady=0)

        # Affichage des dates
        date_label = ctk.CTkLabel(
            card,
            text=date_text,
            font=("Verdana", 13),
            text_color="#000000",
            anchor="w"
        )
        date_label.pack(fill="x", padx=10, pady=0)

        # Affichage des opérateurs avec icône
        operators_label = ctk.CTkLabel(
            card,
            text=f"👤 {operators_text.upper()}",
            font=("Verdana", 13, "italic"),
            text_color="#666666",
            anchor="w",
            height=14,
            wraplength=250  # Pour gérer les longues listes d'opérateurs
        )
        operators_label.pack(fill="x", padx=10, pady=(1, 10))

        return card

    def _get_most_frequent_location(self, results):
        """Détermine le lieu le plus fréquent parmi les résultats."""
        try:
            locations = {}
            for result in results:
                location = result.get('Location', 'N/A')
                if location and location != 'N/A':
                    locations[location] = locations.get(location, 0) + 1

            if not locations:
                return "Lieux divers"

            # Trouver le lieu avec le plus d'occurrences
            max_count = max(locations.values())
            most_frequent = [loc for loc, count in locations.items() if count == max_count]

            # Si plusieurs lieux ont le même nombre d'occurrences
            if len(most_frequent) > 1:
                return "Lieux divers"

            return most_frequent[0]
        except Exception as e:
            print(f"Erreur dans _get_most_frequent_location: {e}")
            return "Lieux divers"

    def _get_date_range(self, results):
        """Détermine la plage de dates (du ... au ...) ou une date unique."""
        try:
            from datetime import datetime

            dates = []
            for result in results:
                date_str = result.get('Date', '')
                if date_str and date_str != 'N/A':
                    try:
                        # Essayer différents formats de date
                        for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                            try:
                                date_obj = datetime.strptime(date_str, fmt)
                                dates.append(date_obj)
                                break
                            except ValueError:
                                continue
                    except:
                        pass

            if not dates:
                return "Date non disponible"

            # Trier les dates
            dates.sort()

            # Si une seule date ou toutes identiques
            if len(set(dates)) == 1:
                return f"le {dates[0].strftime('%d/%m/%Y')}"

            # Sinon, afficher la plage
            oldest = dates[0].strftime('%d/%m/%Y')
            newest = dates[-1].strftime('%d/%m/%Y')
            return f"du {oldest}\nau {newest}"

        except Exception as e:
            print(f"Erreur dans _get_date_range: {e}")
            return "Date non disponible"

    def _extract_operators(self, results):
        """Extrait et formate la liste des opérateurs uniques."""
        import re

        try:
            operators_set = set()

            for result in results:
                operator_str = result.get('Operator', '')
                if operator_str and operator_str != 'N/A':
                    # Séparer par espace, / ou -
                    parts = re.split(r'[\s/\-]+', operator_str)
                    for part in parts:
                        part = part.strip()
                        if part and len(part) > 1:  # Ignorer les initiales seules
                            operators_set.add(part)

            if not operators_set:
                return "Opérateur non spécifié"

            # Convertir en liste et trier
            operators_list = sorted(list(operators_set))

            # Joindre avec des virgules
            return ", ".join(operators_list)

        except Exception as e:
            print(f"Erreur dans _extract_operators: {e}")
            return "Opérateur non spécifié"

    def _refresh_group_by_location_display(self):
        """Rafraîchit l'affichage groupé par localité."""
        print("DEBUG: Rafraîchissement de l'affichage groupé par localité")

        # Nettoyer les widgets existants
        for widget in self.location_groups_scrollable.winfo_children():
            widget.destroy()

        if not self.current_results:
            no_result_label = ctk.CTkLabel(
                self.location_groups_scrollable,
                text="Aucun résultat à afficher",
                font=("Arial", 14),
                text_color="gray"
            )
            no_result_label.pack(pady=50)
            return

        # Grouper les résultats par Location
        grouped_results = {}
        for result in self.current_results:
            location = result.get('Location', 'N/A')
            if location not in grouped_results:
                grouped_results[location] = []
            grouped_results[location].append(result)

        # Créer un frame conteneur avec grid pour l'affichage des cartes
        cards_container = ctk.CTkFrame(self.location_groups_scrollable, fg_color="transparent")
        cards_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Variables pour la disposition en grille
        row = 0
        col = 0
        max_cols = 3  # Nombre maximum de colonnes

        # Créer une carte pour chaque localité
        for location, results in grouped_results.items():
            card = self._create_location_card(cards_container, location, results)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            # Configurer le poids des colonnes pour une répartition équitable
            cards_container.grid_columnconfigure(col, weight=1, uniform="cards")

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _create_location_card(self, parent, location, results):
        """Crée une carte pour une localité avec toutes ses informations."""
        # Frame principal de la carte (fond blanc)
        card = ctk.CTkFrame(
            parent,
            fg_color="white",
            corner_radius=10,
            border_width=1,
            border_color="#E0E0E0"
        )

        # Header sous forme de bouton (remplace CTkFrame + CTkLabel)
        header_button = ctk.CTkButton(
            card,
            text=location.upper(),
            font=("Verdana", 16, "bold"),
            fg_color="#0B4354",
            hover_color="#105A70",
            text_color="white",
            corner_radius=8,
            height=35,
            command=lambda: self._on_card_header_click(location, "lieu")
        )
        header_button.pack(fill="x", padx=5, pady=5)

        # Déterminer le n° de dossier le plus fréquent
        job_number = self._get_most_frequent_job_number(results)

        # Nombre de CPT
        cpt_count = len(results)

        # Déterminer les dates (plus ancienne et plus récente)
        date_text = self._get_date_range(results)

        # Extraire les opérateurs
        operators_text = self._extract_operators(results)

        # Affichage du n° de dossier (INVERSION par rapport au groupement par dossier)
        job_number_label = ctk.CTkLabel(
            card,
            text=f"📋 {job_number.upper()}",
            font=("Verdana", 14, "bold"),
            text_color="#000000",
            anchor="w",
            height=16
        )
        job_number_label.pack(fill="x", padx=10, pady=0)

        # Affichage du nombre de CPT
        cpt_label = ctk.CTkLabel(
            card,
            text=f"{cpt_count} CPT",
            font=("Verdana", 14, "bold", "italic"),
            text_color="#0B4354",
            anchor="w"
        )
        cpt_label.pack(fill="x", padx=10, pady=0)

        # Affichage des dates
        date_label = ctk.CTkLabel(
            card,
            text=date_text,
            font=("Verdana", 13),
            text_color="#000000",
            anchor="w"
        )
        date_label.pack(fill="x", padx=10, pady=0)

        # Affichage des opérateurs avec icône
        operators_label = ctk.CTkLabel(
            card,
            text=f"👤 {operators_text.upper()}",
            font=("Verdana", 13, "italic"),
            text_color="#666666",
            anchor="w",
            height=14,
            wraplength=250  # Pour gérer les longues listes d'opérateurs
        )
        operators_label.pack(fill="x", padx=10, pady=(1, 10))

        return card

    def _get_most_frequent_job_number(self, results):
        """Détermine le n° de dossier le plus fréquent parmi les résultats."""
        try:
            job_numbers = {}
            for result in results:
                job_number = result.get('Job Number', 'N/A')
                if job_number and job_number != 'N/A':
                    job_numbers[job_number] = job_numbers.get(job_number, 0) + 1

            if not job_numbers:
                return "Dossiers divers"

            # Trouver le n° de dossier avec le plus d'occurrences
            max_count = max(job_numbers.values())
            most_frequent = [job for job, count in job_numbers.items() if count == max_count]

            # Si plusieurs n° de dossier ont le même nombre d'occurrences
            if len(most_frequent) > 1:
                return "Dossiers divers"

            return most_frequent[0]
        except Exception as e:
            print(f"Erreur dans _get_most_frequent_job_number: {e}")
            return "Dossiers divers"

    def _on_card_header_click(self, search_value, search_type):
        """Gère le clic sur le header d'une carte de résultat groupé.

        Args:
            search_value: La valeur à rechercher (n° de dossier ou localité)
            search_type: Le type de recherche ("dossier" ou "lieu")
        """
        print(f"DEBUG: Clic sur header de carte - Type: {search_type}, Valeur: {search_value}")

        # Mettre à jour le champ de recherche avec la valeur du header
        self.search_entry.delete(0, 'end')
        self.search_entry.insert(0, search_value)

        # Passer automatiquement en mode "affichage liste"
        self._switch_display_mode("list")

        # Effectuer la recherche
        if self.presenter:
            self.presenter.on_search_text_changed(search_value)

    def _create_rounded_headers_container(self):
        """Crée un frame global arrondi qui contient tous les en-têtes pour le mode liste."""
        # Frame global avec coins arrondis pour contenir tous les en-têtes
        self.headers_container = ctk.CTkFrame(
            self.list_headers_frame,
            fg_color="dark blue",  # Fond bleu uniforme
            corner_radius=8,    # Frame global arrondi
            height=34
        )
        self.headers_container.pack(fill="x", padx=5)
        self.headers_container.grid_propagate(False)
        
        # Configuration des colonnes dans le frame global
        for i, col_config in enumerate(self.columns_config):
            self.headers_container.grid_columnconfigure(i, weight=col_config["weight"])
        
        self.header_buttons = {}
        
        # Tous les boutons sans coins arrondis individuels
        for i, col_config in enumerate(self.columns_config):
            btn = ctk.CTkButton(
                self.headers_container,
                text=col_config["text"],
                font=("Verdana", 16, "bold"),
                text_color="white",
                fg_color="transparent",        # Fond transparent pour hériter du frame parent
                hover_color="#1976D2",
                corner_radius=10,              
                border_width=0,
                command=lambda key=col_config["key"]: self._on_header_click(key)
            )
            btn.grid(row=0, column=i, sticky="ew", padx=8, pady=3)
            self.header_buttons[col_config["key"]] = btn

    def _create_search_entry(self):
        """Crée le champ de saisie de recherche."""
        self.search_entry = ctk.CTkEntry(
            self.search_input_frame,
            placeholder_text="CHERCHER UN N° DE DOSSIER, LOCALITÉ, DATE, OPÉRATEUR.",
            font=("Verdana", 20, "bold"),
            fg_color="white",
            text_color="black",
            placeholder_text_color="light gray",
            border_width=2,
            border_color="dark blue",
            corner_radius=20,
            height=50
        )
        self.search_entry.pack(fill="both", expand=True, padx=5, pady=5)

        # Liaison des événements avec debounce
        self.search_entry.bind('<KeyRelease>', self._on_search_changed)
        self.search_entry.bind('<Return>', lambda e: self._on_search_click())
        
        print("DEBUG: Événements de recherche liés")

    def _create_search_icon(self):
        """Crée l'icône de recherche sur le côté droit du champ de saisie."""
        try:
            # Charger l'image depuis le dossier 'icons'
            icon_path = get_resource_path(os.path.join("icons", "search.png"))
            image = Image.open(icon_path)

            # Redimensionner l'image pour qu'elle s'adapte au bouton
            image = image.resize((20, 20), Image.Resampling.LANCZOS)

            # Créer l'objet CTkImage pour CustomTkinter
            search_icon_image = ctk.CTkImage(light_image=image, dark_image=image, size=(20, 20))

            # Créer le bouton avec l'icône
            self.search_icon_button = ctk.CTkButton(
                self.search_input_frame,
                fg_color="transparent",
                bg_color="white",
                corner_radius=30,
                width=20,
                height=40,
                image=search_icon_image,
                text="",
                hover_color=self.model.gradient_color_end,
                command=self._on_search_click
            )

            # Garder une référence de l'image pour éviter le garbage collector
            self.search_icon_button.image = search_icon_image

            self.search_icon_button.place(relx=0.986, rely=0.5, anchor="e")

        except FileNotFoundError:
            # Si l'image n'existe pas, créer un bouton avec texte de fallback
            print("Attention: Fichier search.png introuvable dans le dossier icons/")
            self.search_icon_button = ctk.CTkButton(
                self.search_input_frame,
                fg_color=self.model.gradient_color_end,
                bg_color="white",
                corner_radius=18,
                width=40,
                height=32,
                text="🔍",
                font=("Arial", 16),
                text_color="black",
                command=self._on_search_click
            )
            self.search_icon_button.place(relx=0.98, rely=0.5, anchor="e")

    def _create_sort_buttons(self):
        """MODIFIÉ : Crée tous les boutons de tri et d'affichage sans 'Affichage groupé'."""
        # Style commun pour tous les boutons
        button_style = {
            "font": ("Arial", 16),
            "fg_color": "#F6FAFC",
            "text_color": "black",
            "hover_color": "#D0D0D0",
            "corner_radius": 10,
            "height": 30,
            "border_width": 1,
            "border_color": "#C0C0C0"
        }

        # MODIFIÉ : Boutons de tri et d'affichage (sans "Affichage groupé")
        sort_buttons = [
            ("Grouper par date", "group_by_date", "left", (20, 10)),
            ("Grouper par n° de dossier", "group_by_folder", "left", (0, 10)),
            ("Grouper par localité", "group_by_location", "left", (0, 10)),
            ("Affichage liste", "list", "right", (0, 10))
        ]

        for text, action, side, padx in sort_buttons:
            button = ctk.CTkButton(
                self.buttons_frame,
                text=text,
                command=lambda a=action: self._on_display_mode_change(a),
                **button_style
            )
            button.pack(side=side, padx=padx)

    def _on_display_mode_change(self, mode):
        """NOUVEAU : Gère le changement de mode d'affichage."""
        print(f"DEBUG: Changement de mode demandé: {mode}")
        
        # Changer le mode d'affichage
        self._switch_display_mode(mode)
        
        # Informer le presenter si nécessaire
        if self.presenter:
            self.presenter.on_sort_action(mode)

    def _create_treeview(self):
        """Crée le Treeview sans en-têtes natifs pour le mode liste."""
        # Configuration du style moderne
        self._configure_modern_treeview_style()
        
        # Configuration du Treeview SANS en-têtes natifs
        columns = ("dossier", "essai", "lieu", "date", "operateur")
        
        self.results_tree = ttk.Treeview(
            self.treeview_frame,
            columns=columns,
            show="tree",  # IMPORTANT : Seulement "tree", pas "headings"
            selectmode="extended",
            style="Modern.Treeview"
        )
        
        # Largeurs des colonnes (correspondantes aux en-têtes)
        self.results_tree.column("#0", width=200, minwidth=150, anchor="w")
        self.results_tree.column("dossier", width=120, minwidth=80, anchor="w") 
        self.results_tree.column("essai", width=80, minwidth=60, anchor="w")
        self.results_tree.column("lieu", width=180, minwidth=120, anchor="w")
        self.results_tree.column("date", width=120, minwidth=80, anchor="w")
        self.results_tree.column("operateur", width=120, minwidth=80, anchor="w")
        
        # Scrollbars stylisées
        self._create_modern_scrollbars()
        
        # Layout
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configuration des tags pour l'apparence
        self._configure_treeview_tags()
        
        # Binding pour les interactions
        self.results_tree.bind("<<TreeviewSelect>>", self._on_treeview_select_styled)
        self.results_tree.bind("<Motion>", self._on_treeview_hover)
        self.results_tree.bind("<Leave>", self._on_treeview_leave)

    def _configure_modern_treeview_style(self):
        """Configure un style moderne pour le Treeview SANS bordures."""
        style = ttk.Style()
        
        # Changer le thème pour permettre la personnalisation
        style.theme_use('clam')
        
        # Layout personnalisé pour supprimer toutes les bordures
        style.layout("Modern.Treeview", [
            ('Modern.Treeview.treearea', {'sticky': 'nswe'})
        ])
        
        # Configuration du Treeview principal SANS bordures
        style.configure("Modern.Treeview",
                       background="white",
                       foreground="#2E2E2E",
                       fieldbackground="white",
                       font=("Verdana", 14),
                       rowheight=35,
                       borderwidth=0,
                       highlightthickness=0,
                       relief="flat")

    def _create_modern_scrollbars(self):
        """Crée des scrollbars avec style moderne."""
        style = ttk.Style()
        
        # Scrollbar verticale
        style.configure("Modern.Vertical.TScrollbar",
                       background="#E0E0E0",
                       troughcolor="#EEF8FE",
                       borderwidth=0,
                       arrowcolor="#666666",
                       darkcolor="#D0D0D0",
                       lightcolor="#F0F0F0",
                       relief="flat")
        
        # Scrollbar horizontale  
        style.configure("Modern.Horizontal.TScrollbar",
                       background="#E0E0E0",
                       troughcolor="#EEF8FE", 
                       borderwidth=0,
                       arrowcolor="#666666",
                       darkcolor="#D0D0D0",
                       lightcolor="#F0F0F0",
                       relief="flat")
        
        self.v_scrollbar = ttk.Scrollbar(self.treeview_frame, 
                                        orient="vertical", 
                                        command=self.results_tree.yview,
                                        style="Modern.Vertical.TScrollbar")
        self.h_scrollbar = ttk.Scrollbar(self.treeview_frame, 
                                        orient="horizontal", 
                                        command=self.results_tree.xview,
                                        style="Modern.Horizontal.TScrollbar")
        
        self.results_tree.configure(yscrollcommand=self.v_scrollbar.set, 
                                   xscrollcommand=self.h_scrollbar.set)

    def _configure_treeview_tags(self):
        """Configure les tags d'apparence du Treeview."""
        self.results_tree.tag_configure('oddrow', 
                                       background="#F3F3F3", 
                                       foreground="#2E2E2E",
                                       font=("Verdana", 12))
        self.results_tree.tag_configure('evenrow', 
                                       background="white", 
                                       foreground="#2E2E2E",
                                       font=("Verdana", 12))
        self.results_tree.tag_configure('selected', 
                                       background="#E3F2FD", 
                                       foreground="#1565C0",
                                       font=("Verdana", 12, "bold"))
        self.results_tree.tag_configure('hover', 
                                       background="#E8F4FD", 
                                       foreground="#1565C0",
                                       font=("Verdana", 14))
        self.results_tree.tag_configure('searching',
                                       background="#E3F2FD",
                                       foreground="#2196F3", 
                                       font=("Arial", 14, "bold"))
        self.results_tree.tag_configure('no_results', 
                                       background="#FFF3CD", 
                                       foreground="#856404",
                                       font=("Arial", 12, "italic"))

    def _on_header_click(self, column_key):
        """Gère le clic sur un en-tête pour trier la colonne (seulement en mode liste)."""
        if self.current_display_mode != "list" or not self.current_results:
            return
        
        # Déterminer la direction du tri
        reverse = self.sort_reverse.get(column_key, False)
        self.sort_reverse = {k: False for k in self.sort_reverse}  # Réinitialiser tous
        self.sort_reverse[column_key] = not reverse
        
        # Trier les données
        self._sort_current_results(column_key, not reverse)
        
        # Mettre à jour l'affichage
        self._refresh_treeview_display()
        
        # Mettre à jour les indicateurs visuels des en-têtes
        self._update_header_indicators(column_key, not reverse)

    def _sort_current_results(self, column_key, reverse):
        """Trie les résultats actuels selon la colonne spécifiée."""
        def get_sort_key(result):
            if column_key == "#0":
                value = result.get('file_name', '')
            else:
                # Mapper les clés de colonnes aux clés de données
                key_mapping = {
                    "dossier": "Job Number",
                    "essai": "TestNumber",
                    "lieu": "Location",
                    "date": "Date",
                    "operateur": "Operator"
                }
                value = result.get(key_mapping.get(column_key, ''), '')
            
            # Traitement spécial pour la colonne essai : tri numérique
            if column_key == "essai":
                import re
                # Extraire le premier nombre trouvé dans la chaîne
                if value and value != 'N/A':
                    match = re.search(r'\d+', str(value))
                    if match:
                        return int(match.group())
                # Si pas de nombre trouvé, retourner -1 pour mettre en début/fin
                return -1 if not reverse else float('inf')
            
            # Retourner une chaîne vide si valeur manquante, sinon convertir en minuscules
            return str(value).lower() if value and value != 'N/A' else ''
        
        self.current_results.sort(key=get_sort_key, reverse=reverse)


    def _refresh_treeview_display(self):
        """Rafraîchit l'affichage du Treeview avec les données triées."""
        # Effacer le contenu actuel
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Réafficher les résultats triés
        for i, result in enumerate(self.current_results):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            
            file_display = f"📈 {result.get('file_name', 'N/A')}"
            
            self.results_tree.insert(
                "",
                "end",
                text=file_display,
                values=(
                    result.get('Job Number', 'N/A'),
                    result.get('TestNumber', 'N/A'), 
                    result.get('Location', 'N/A'),
                    result.get('Date', 'N/A'),
                    result.get('Operator', 'N/A')
                ),
                tags=(tag,)
            )

    def _update_header_indicators(self, sorted_column, reverse):
        """Met à jour les indicateurs visuels des en-têtes."""
        # Réinitialiser tous les en-têtes
        for col_config in self.columns_config:
            original_text = col_config["text"]
            self.header_buttons[col_config["key"]].configure(text=original_text)
        
        # Ajouter l'indicateur sur la colonne triée
        if sorted_column in self.header_buttons:
            # Trouver le texte original
            original_text = next(col["text"] for col in self.columns_config if col["key"] == sorted_column)
            arrow = " 🔽" if reverse else " 🔼"
            new_text = original_text + arrow
            self.header_buttons[sorted_column].configure(text=new_text)

    def _on_treeview_hover(self, event):
        """Effet de hover sur les lignes."""
        item = self.results_tree.identify_row(event.y)
        
        if item and item != self.hovered_item:
            # Réinitialiser l'ancien item survolé
            if self.hovered_item:
                self._reset_item_style(self.hovered_item)
            
            # Appliquer hover sur le nouvel item
            if item:
                current_tags = list(self.results_tree.item(item)['tags'])
                if 'hover' not in current_tags:
                    current_tags.append('hover')
                self.results_tree.item(item, tags=current_tags)
                self.hovered_item = item

    def _on_treeview_leave(self, event):
        """Réinitialise le hover quand on sort du Treeview."""
        if self.hovered_item:
            self._reset_item_style(self.hovered_item)
            self.hovered_item = None

    def _reset_item_style(self, item):
        """Réinitialise le style d'un item à son état original."""
        try:
            current_tags = list(self.results_tree.item(item)['tags'])
            
            # Retirer le hover
            if 'hover' in current_tags:
                current_tags.remove('hover')
            
            # S'assurer qu'il a son tag original si ce n'est pas un item spécial
            item_text = self.results_tree.item(item)['text']
            if not any(special in item_text for special in ['🔍 Recherche', 'Aucun résultat', 'Indexation']):
                if 'evenrow' not in current_tags and 'oddrow' not in current_tags and 'selected' not in current_tags:
                    # Recalculer le tag original basé sur l'index
                    try:
                        index = self.results_tree.index(item)
                        if index >= 0:
                            original_tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                            current_tags.append(original_tag)
                    except:
                        pass
            
            self.results_tree.item(item, tags=current_tags)
        except:
            pass

    def _on_treeview_select_styled(self, event):
        """Gestion de la sélection avec style moderne."""
        selection = self.results_tree.selection()
        
        # Réinitialiser tous les items
        for item in self.results_tree.get_children():
            current_tags = list(self.results_tree.item(item)['tags'])
            if 'selected' in current_tags:
                current_tags.remove('selected')
            self.results_tree.item(item, tags=current_tags)
        
        # Appliquer le style de sélection
        for item in selection:
            current_tags = list(self.results_tree.item(item)['tags'])
            if 'selected' not in current_tags:
                current_tags.append('selected')
            self.results_tree.item(item, tags=current_tags)
        
        # Traitement de la sélection
        for item in selection:
            item_data = self.results_tree.item(item)
            
            # Ne pas traiter les éléments de statut
            if any(special in item_data['text'] for special in ['🔍 Recherche', 'Aucun résultat', 'Indexation']):
                continue
            
            # Reconstituer les données (retirer l'icône du nom de fichier)
            file_name = item_data['text']
            if file_name.startswith("📈 "):
                file_name = file_name[2:]  # Retirer "📈 "
            
            # Retrouver les données complètes depuis self.current_results
            result_data = None
            for result in self.current_results:
                if result.get('file_name') == file_name:
                    result_data = result
                    break
            
            # Si on n'a pas trouvé les données complètes, reconstituer avec les données disponibles
            if result_data is None:
                values = item_data['values']
                result_data = {
                    'file_name': file_name,
                    'file_path': f"Chemin non disponible pour {file_name}",  # Fallback
                    'Job Number': values[0] if len(values) > 0 else '',
                    'TestNumber': values[1] if len(values) > 1 else '',
                    'Location': values[2] if len(values) > 2 else '',
                    'Date': values[3] if len(values) > 3 else '',
                    'Operator': values[4] if len(values) > 4 else ''
                }

            if self.presenter:
                self.presenter.on_search_result_selected(result_data)

    def display_search_results(self, results):
        """MODIFIÉ : Affiche les résultats selon le mode d'affichage actuel."""
        print(f"DEBUG VUE: display_search_results appelée avec {len(results)} résultats en mode {self.current_display_mode}")
        
        if threading.current_thread() != threading.main_thread():
            print("WARNING: display_search_results appelée depuis un thread secondaire!")
            return
        
        # Stocker les résultats pour tous les modes
        self.current_results = results
        
        # Mettre à jour le compteur de résultats
        self._update_results_count(len(results))
        
        # Rafraîchir l'affichage selon le mode actuel
        if self.current_display_mode == "list":
            self._refresh_list_display()
        elif self.current_display_mode == "group_by_date":
            self._refresh_group_by_date_display()
        elif self.current_display_mode == "group_by_folder":
            self._refresh_group_by_folder_display()
        elif self.current_display_mode == "group_by_location":
            self._refresh_group_by_location_display()
        
        print("DEBUG VUE: Affichage terminé avec succès")

    def _update_results_count(self, count):
        """Met à jour l'affichage du nombre de résultats."""
        if count == 0 and not self.indexing_completed:
            return
        
        if count == 0:
            text = "Aucun résultat trouvé"
            color = "#856404"
        else:
            text = f"✅ {count} résultat(s) trouvé(s)"
            color = "#1565C0"
        
        self.results_count_label.configure(text=text, text_color=color)

    def on_indexing_completed(self, result):
        """Callback appelé quand l'indexation est terminée."""
        print(f"DEBUG VUE: on_indexing_completed APPELÉE avec {result}")
        
        try:
            # Marquer que l'indexation est terminée
            self.indexing_completed = True
            print(f"DEBUG VUE: Flag indexing_completed mis à True")
            
            status_text = f"✅ Indexation terminée : {result.get('total_files', 0)} fichiers indexés"
            if result.get('from_cache'):
                status_text += " (depuis le cache)"
            
            # Mettre à jour le statut temporairement
            self.results_count_label.configure(text=status_text, text_color="#28a745")
            
            # Forcer la mise à jour de l'interface
            self.update_idletasks()
            
            # Après 2 secondes, changer pour un message plus approprié
            self.after(2000, lambda: self.results_count_label.configure(
                text="Affichage des fichiers les plus récents", 
                text_color="#1565C0"
            ))
            
            print(f"DEBUG VUE: Interface mise à jour, indexing_completed = {self.indexing_completed}")
            
        except Exception as e:
            print(f"DEBUG VUE: ERREUR dans on_indexing_completed: {e}")
            # Forcer le flag même en cas d'erreur d'affichage
            self.indexing_completed = True

    def _show_initial_status(self):
        """Affiche le statut initial."""
        self.results_count_label.configure(text="Indexation en cours...", text_color="#2196F3")

    def _show_search_indicator(self):
        """Affiche un indicateur de recherche."""
        if self.indexing_completed:
            self.results_count_label.configure(text="🔍 Recherche en cours...", text_color="#2196F3")

    def _on_search_changed(self, event):
        """Callback avec debounce pour la recherche."""
        search_text = self.search_entry.get()
        print(f"DEBUG VUE: _on_search_changed appelée avec '{search_text}'")
        print(f"DEBUG VUE: indexing_completed = {getattr(self, 'indexing_completed', False)}")
        
        # Vérification plus robuste
        if not getattr(self, 'indexing_completed', False):
            print("DEBUG VUE: Indexation pas terminée, recherche ignorée")
            return
        
        # Annuler la recherche précédente si elle existe
        if self.search_after_id is not None:
            self.after_cancel(self.search_after_id)
            self.search_after_id = None
        
        # Afficher un indicateur de recherche en cours si le texte n'est pas vide
        if search_text.strip():
            self._show_search_indicator()
        
        # Programmer la nouvelle recherche après le délai
        if search_text.strip():
            self.search_after_id = self.after(
                self.search_delay, 
                lambda: self._perform_delayed_search(search_text)
            )
        else:
            # Si le champ est vide, effacer immédiatement les résultats
            self.clear_search_results()

    def _perform_delayed_search(self, search_text):
        """Effectue la recherche après le délai de debounce."""
        print(f"DEBUG VUE: Recherche déclenchée après délai pour '{search_text}'")
        
        # Réinitialiser l'ID du timer
        self.search_after_id = None
        
        # Effectuer la recherche via le presenter
        if self.presenter:
            self.presenter.on_search_text_changed(search_text)
        else:
            print("DEBUG VUE: ERREUR - Presenter n'existe pas!")

    def _on_search_click(self):
        """Callback pour le clic sur le bouton de recherche."""
        if self.presenter and self.indexing_completed:
            self.presenter.on_search_button_clicked()

    def clear_search_results(self):
        """Efface tous les résultats de recherche."""
        # Effacer selon le mode d'affichage
        if self.current_display_mode == "list" and hasattr(self, 'results_tree'):
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
        
        # Remettre le message approprié
        if self.indexing_completed:
            self.results_count_label.configure(text="Commencez à chercher", text_color="#1565C0")

    def _on_sort_action(self, action_type):
        """Callback pour les actions de tri."""
        if self.presenter:
            self.presenter.on_sort_action(action_type)

    def get_search_text(self):
        """Retourne le texte actuellement saisi dans le champ de recherche."""
        return self.search_entry.get()

    def clear_search(self):
        """Efface le contenu du champ de recherche."""
        self.search_entry.delete(0, 'end')

    def focus_search_entry(self):
        """Met le focus sur le champ de recherche."""
        self.search_entry.focus_set()


class AppView(ctk.CTk):
    """
    Fenêtre principale de l'application avec splash screen intelligent.
    """
    def __init__(self, model, presenter):
        super().__init__()
        self.model = model
        self.presenter = presenter
        self._closing = False
        
        # Variables pour gérer le splash screen intelligent
        self.splash_min_time_elapsed = False
        self.indexing_completed = False
        self.interface_ready = False

        self.title(self.model.software_name)
        self.configure(bg=self.model.window_bg_color)
        self.gradient_image = None
        self.gradient_tk_image = None

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.setup_root_window()
        self.create_splash_screen()

        # Démarrer les timers
        self.after(self.model.splash_screen_delay, self._on_min_splash_time_elapsed)
        self.after(100, self.poll_gui_updates)

    def _on_min_splash_time_elapsed(self):
        """Marque que le temps minimum du splash screen est écoulé."""
        print("DEBUG SPLASH: Temps minimum écoulé")
        self.splash_min_time_elapsed = True
        self._check_ready_to_load_interface()

    def _on_indexing_completed_splash(self, result):
        """Gère la fin d'indexation pendant le splash screen."""
        print(f"DEBUG SPLASH: Indexation terminée - {result}")
        self.indexing_completed = True
        self._check_ready_to_load_interface()

    def _check_ready_to_load_interface(self):
        """Vérifie si on peut charger l'interface principale."""
        if self.splash_min_time_elapsed and self.indexing_completed and not self.interface_ready:
            print("DEBUG SPLASH: Conditions remplies, chargement de l'interface")
            self.interface_ready = True
            self.load_main_interface()

    def _update_splash_progress(self, progress_data):
        """Met à jour la barre de progression avec les vraies données."""
        if not hasattr(self, 'splash_progress_bar') or not self.splash_progress_bar.winfo_exists():
            return
            
        try:
            self._real_progress_received = True
            
            current = progress_data.get("current", 0)
            total = progress_data.get("total", 100)
            percentage = progress_data.get("percentage", 0)
            
            #print(f"DEBUG PROGRESS: {current}/{total} = {percentage:.1f}%")
            
            # Mettre à jour la barre de progression
            progress_value = min(percentage / 100.0, 1.0)
            self.splash_progress_bar.set(progress_value)
            
            # Mettre à jour le texte
            if hasattr(self, 'splash_progress_label'):
                if total > 0:
                    self.splash_progress_label.configure(
                        text=f"Indexation : {current}/{total} fichiers ({percentage:.1f}%)"
                    )
                else:
                    self.splash_progress_label.configure(text="Initialisation...")
            
            # Forcer la mise à jour de l'affichage
            self.splash_progress_bar.update_idletasks()
            
        except Exception as e:
            print(f"Erreur lors de la mise à jour de progression : {e}")

    def schedule_gui_update(self, update_function):
        """Programme une mise à jour GUI dans le thread principal."""
        self.after(0, update_function)

    def poll_gui_updates(self):
        """Version modifiée pour gérer la progression réelle pendant le splash."""
        if self._closing:
            return
            
        try:
            updates = self.model.get_gui_updates()
            
            for update_type, data in updates:
                if update_type == "indexing_progress":
                    self._update_splash_progress(data)
                    
                elif update_type == "indexing_completed":
                    if not self.interface_ready:
                        # Pendant le splash screen
                        self._on_indexing_completed_splash(data)
                    else:
                        # Interface déjà chargée
                        if hasattr(self, 'quick_search_zone'):
                            self.quick_search_zone.on_indexing_completed(data)
                            
                            # Afficher les fichiers de la date la plus récente
                            latest_files = self.model.get_latest_date_files()
                            if latest_files:
                                self.quick_search_zone.display_search_results(latest_files)
                                print(f"DEBUG: Affichage de {len(latest_files)} fichiers de la date la plus récente après indexation")
                                
                                # Mettre à jour le message après affichage
                                def update_message():
                                    self.quick_search_zone.results_count_label.configure(
                                        text="Affichage des fichiers les plus récents",
                                        text_color="#1565C0"
                                    )
                                
                                # Attendre 2 secondes après le message d'indexation terminée
                                self.after(2000, update_message)
                            
                elif update_type == "indexing_error":
                    print(f"GUI: Erreur d'indexation - {data}")
                    # En cas d'erreur, on charge quand même l'interface
                    if not self.interface_ready:
                        self.indexing_completed = True
                        self._check_ready_to_load_interface()
                        
        except Exception as e:
            print(f"Erreur lors du polling GUI : {e}")
        
        # Continuer le polling
        if not self._closing:
            self.after(100, self.poll_gui_updates)

    def on_closing(self):
        """Méthode appelée lors de la fermeture de l'application."""
        self._closing = True

        # Nettoyer les ressources si nécessaire
        if hasattr(self, 'gradient_image'):
            self.gradient_image = None
        if hasattr(self, 'gradient_tk_image'):
            self.gradient_tk_image = None

        # Fermer l'application
        self.destroy()

    def setup_root_window(self):
        """Configure la fenêtre principale (taille et position)."""
        self.geometry(f"{self.model.window_width}x{self.model.window_height}")
        self.center_window(self.model.window_width, self.model.window_height)

    def center_window(self, window_width, window_height):
        """Centre la fenêtre sur l'écran."""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_cordinate = int((screen_width / 2) - (window_width / 2))
        y_cordinate = int((screen_height / 2) - (window_height / 2))
        self.geometry(f"{window_width}x{window_height}+{x_cordinate}+{y_cordinate}")

    def create_splash_screen(self):
        """Affiche l'écran de démarrage avec indicateur de progression intelligent."""
        self.splash_frame = ctk.CTkFrame(self, fg_color="#262626")
        self.splash_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        splash_message = self.model.get_random_splash_message()
        self.splash_label = ctk.CTkLabel(
            self.splash_frame,
            text=splash_message,
            font=("Arial", 27, "bold"),
            text_color="white"
        )
        self.splash_label.place(relx=0.5, rely=0.4, anchor="center")

        self.splash_label_software_name = ctk.CTkLabel(
            self.splash_frame,
            text=f"{self.model.software_name} - {self.model.software_version}",
            font=("Courier New", 26),
            text_color="white"
        )
        self.splash_label_software_name.place(relx=0.5, rely=0.99, anchor="s")
        
        # Indicateur de progression
        self.splash_progress_label = ctk.CTkLabel(
            self.splash_frame,
            text="Vérification de l'indexation des fichiers...",
            font=("Arial", 16),
            text_color="#FBBC3A"
        )
        self.splash_progress_label.place(relx=0.5, rely=0.6, anchor="center")
        
        # Barre de progression
        self.splash_progress_bar = ctk.CTkProgressBar(
            self.splash_frame,
            width=300,
            height=20,
            progress_color="#FBBC3A"
        )
        self.splash_progress_bar.place(relx=0.5, rely=0.7, anchor="center")
        self.splash_progress_bar.set(0)
        
        # Animation de la barre de progression
        self._animate_splash_progress()

    def _animate_splash_progress(self):
        """Animation qui ne conflite pas avec la progression réelle."""
        if not self.interface_ready and hasattr(self, 'splash_progress_bar'):
            try:
                if self.indexing_completed:
                    # Compléter à 100% quand l'indexation est terminée
                    self.splash_progress_bar.set(1.0)
                    if hasattr(self, 'splash_progress_label'):
                        self.splash_progress_label.configure(text="Indexation terminée !")
                    return
                
                # Ne faire l'animation que si aucune progression réelle n'est reçue
                if not hasattr(self, '_real_progress_received'):
                    self._real_progress_received = False
                
                if not self._real_progress_received:
                    # Animation de va-et-vient seulement si pas de vraie progression
                    current_progress = self.splash_progress_bar.get()
                    
                    if not hasattr(self, 'progress_direction'):
                        self.progress_direction = 1
                    
                    new_progress = current_progress + (0.03 * self.progress_direction)
                    
                    if new_progress >= 0.8:  # Ne pas aller jusqu'à 100% en mode animation
                        self.progress_direction = -1
                    elif new_progress <= 0:
                        self.progress_direction = 1
                    
                    self.splash_progress_bar.set(new_progress)
                
                # Continuer l'animation
                if not self.indexing_completed:
                    self.after(150, self._animate_splash_progress)
                    
            except:
                pass

    def load_main_interface(self):
        """Charge l'interface principale avec indexation déjà terminée."""
        print("DEBUG SPLASH: Chargement de l'interface principale")
        self.splash_frame.place_forget()

        # Création des composants principaux de l'interface
        self.top_menu_view = TopMenuView(self, self.model, self.presenter)
        self.side_menu_view = SideMenuView(self, self.model, self.presenter)

        # Création de l'espace de travail principal et des workspaces
        self.create_main_workspace_frame()
        self.create_workspaces(self.main_workspace_frame)

        # L'indexation est déjà terminée, marquer le flag pour quick_search_zone
        if hasattr(self, 'quick_search_zone'):
            self.quick_search_zone.indexing_completed = True
            
            # Afficher les fichiers de la date la plus récente
            latest_files = self.model.get_latest_date_files()
            if latest_files:
                self.quick_search_zone.display_search_results(latest_files)
                print(f"DEBUG: Affichage de {len(latest_files)} fichiers de la date la plus récente")
                
                # Mettre le bon message après affichage des fichiers
                self.quick_search_zone.results_count_label.configure(
                    text="Affichage des fichiers les plus récents",
                    text_color="#1565C0"
                )
            else:
                # Si aucun fichier récent, afficher message de prêt
                self.quick_search_zone.results_count_label.configure(
                    text="✅ Prêt à chercher",
                    text_color="#28a745"
                )

        # Liaison des événements globaux
        self.bind_events()
        
        # Forcer le dessin initial du dégradé après un court délai
        self.after(100, self.draw_initial_gradient)

    def draw_initial_gradient(self):
        """Dessine le dégradé initial après que l'interface soit complètement chargée."""
        try:
            if hasattr(self, 'top_menu_view') and hasattr(self.top_menu_view, 'gradient_canvas'):
                canvas = self.top_menu_view.gradient_canvas
                
                # Forcer la mise à jour de la géométrie
                self.update_idletasks()
                
                height = canvas.winfo_height()
                width = canvas.winfo_width()
                
                if height > 0 and width > 0:
                    self.draw_gradient(
                        canvas,
                        height,
                        self.model.gradient_color_start,
                        self.model.gradient_color_end,
                        prolong_ratio=self.model.gradient_prolong_ratio
                    )
        except Exception as e:
            print(f"Erreur lors du dessin initial du dégradé: {e}")

    def create_main_workspace_frame(self):
        """Crée le cadre principal qui contiendra les différents espaces de travail."""
        self.main_workspace_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_workspace_frame.pack(side="left", fill="both", expand=True)

    def create_workspaces(self, parent):
        """Crée les différents onglets/espaces de travail dans un dictionnaire."""
        # Workspace 1 - DONNÉES BRUTES (maintenant vide)
        workspace1 = ctk.CTkFrame(parent, fg_color="lightgray", corner_radius=0)
        empty_label = ctk.CTkLabel(workspace1, text="Workspace DONNÉES BRUTES", 
                                  font=("Arial", 24, "bold"), text_color="black")
        empty_label.place(relx=0.5, rely=0.5, anchor="center")

        # Workspace 2 : OBSERVATIONS
        workspace2 = ctk.CTkFrame(parent, fg_color="blue", corner_radius=0)

        # Workspace 3 : EXTRACTIONS
        workspace3 = ctk.CTkFrame(parent, fg_color="white", corner_radius=0)

        # Workspace 4 : TRAITER (avec panneaux de paramètres CPT)
        workspace4 = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        self.create_CPTborehole_parameters_frame(workspace4, (20, 25))
        self.create_CPTborehole_parameters_frame(workspace4, (20, 225))
        self.create_CPTborehole_parameters_frame(workspace4, (20, 425))

        # Workspace RECHERCHE RAPIDE (avec l'interface de recherche)
        workspace_quick_search = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        self.quick_search_zone = FileSearchZoneView(workspace_quick_search, self.model, self.presenter)

        # Workspace 5 : PREFERENCES
        workspace5 = ctk.CTkFrame(parent, fg_color="purple", corner_radius=0)

        # Dictionnaire des workspaces
        self.workspaces = {
            "DONNÉES BRUTES": workspace1,
            "OBSERVATIONS": workspace2,
            "EXTRACTIONS": workspace3,
            "TRAITER": workspace4,
            "RECHERCHE RAPIDE": workspace_quick_search,
            "PREFERENCES": workspace5
        }

    def display_workspace(self, workspace_name):
        """Affiche l'espace de travail demandé, masque les autres."""
        if hasattr(self, 'workspaces'):
            for workspace in self.workspaces.values():
                workspace.place_forget()
            workspace = self.workspaces.get(workspace_name)
            if workspace:
                workspace.place(x=0, y=0, relwidth=1, relheight=1)

    def focus_search_entry(self):
        """Met le focus sur le champ de recherche."""
        if hasattr(self, 'quick_search_zone'):
            self.quick_search_zone.focus_search_entry()

    def create_CPTborehole_parameters_frame(self, parent, place_coordinates):
        """Exemple de création d'un panneau paramétrable (CPT Borehole)."""
        borehole_settings_panel = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=20, width=1200)
        borehole_settings_panel.place(x=place_coordinates[0], y=place_coordinates[1])

        title_frame = ctk.CTkFrame(borehole_settings_panel, width=180, height=40, corner_radius=10, fg_color="#1E56A0")
        title_frame.place(x=0, y=0)
        title_label = ctk.CTkLabel(title_frame, text="SONDAGE P2BIS", text_color="white", font=("Arial", 15, "bold"))
        title_label.place(relx=0.5, rely=0.5, anchor="center")

        content_frame = ctk.CTkFrame(borehole_settings_panel, width=700, height=150, corner_radius=24, border_color="grey", border_width=1, fg_color="white")
        content_frame.place(x=15, y=20)
        content_frame.lower(title_frame)

        font_style = ("Arial", 14)
        offset_y = 0.10

        # Labels des paramètres
        labels_data = [
            ("Matériel utilisé", (0.03, 0.05 + offset_y), "bold"),
            ("Machine : Volvo V2", (0.03, 0.2 + offset_y), "normal"),
            ("Capacité : 20 t", (0.03, 0.35 + offset_y), "normal"),
            ("Delta petit mano : 20", (0.03, 0.5 + offset_y), "normal"),
            ("Delta grand mano : -100", (0.03, 0.65 + offset_y), "normal"),
            ("Cote de départ : -0,10 m", (0.32, 0.05 + offset_y), "normal"),
            ("Niveau d'eau", (0.32, 0.35 + offset_y), "bold"),
            ("Fin d'essai : 5,6 m", (0.32, 0.5 + offset_y), "normal"),
            ("Fin de chantier : 5,4 m", (0.32, 0.65 + offset_y), "normal"),
            ("Eboulement", (0.57, 0.35 + offset_y), "bold"),
            ("Fin d'essai : 6,10 m", (0.57, 0.5 + offset_y), "normal"),
            ("Fin de chantier : 6,10 m", (0.57, 0.65 + offset_y), "normal"),
        ]

        for text, (relx, rely), weight in labels_data:
            font = (font_style[0], font_style[1], weight) if weight == "bold" else font_style
            label = ctk.CTkLabel(content_frame, text=text, font=font)
            label.place(relx=relx, rely=rely)

        # Boutons
        depth_button = ctk.CTkButton(content_frame, text="18.60 m", font=("Arial", 12, "bold"), 
                                   fg_color="light grey", corner_radius=8, width=22, 
                                   text_color="black", border_color="grey", border_width=1)
        depth_button.place(relx=0.75, rely=0.05 + offset_y)

        date_button = ctk.CTkButton(content_frame, text="17/07/2024", font=("Arial", 12, "bold"), 
                                  fg_color="light grey", corner_radius=8, width=22, 
                                  text_color="black", border_color="grey", border_width=1)
        date_button.place(relx=0.85, rely=0.05 + offset_y)

    def bind_events(self):
        """Bind de certains événements globaux (ex : redimensionnement) pour dessiner le dégradé de la barre de menu."""
        self.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        """Au redimensionnement, on redessine le dégradé de la barre de menu."""
        # Ne rien faire si l'application se ferme
        if getattr(self, '_closing', False):
            return

        # Ignorer les événements qui ne concernent pas la fenêtre principale
        if event.widget != self:
            return

        # Délai court pour s'assurer que les dimensions sont à jour
        self.after(10, self._redraw_gradient_delayed)

    def _redraw_gradient_delayed(self):
        """Redessine le dégradé avec un délai pour s'assurer des bonnes dimensions."""
        try:
            # Vérifications d'existence
            if not hasattr(self, 'top_menu_view'):
                return

            top_menu = self.top_menu_view
            if not hasattr(top_menu, 'gradient_canvas'):
                return

            canvas = top_menu.gradient_canvas

            # Vérifier si le widget existe encore dans Tkinter
            if not canvas.winfo_exists():
                return

            # Forcer la mise à jour de la géométrie
            self.update_idletasks()

            # Obtenir les dimensions de manière sécurisée
            try:
                height = canvas.winfo_height()
                width = canvas.winfo_width()
            except tk.TclError:
                return

            # Vérifier des dimensions valides
            if height <= 0 or width <= 0:
                return

            # Redessiner le dégradé
            self.draw_gradient(
                canvas,
                height,
                self.model.gradient_color_start,
                self.model.gradient_color_end,
                prolong_ratio=self.model.gradient_prolong_ratio
            )

        except (AttributeError, tk.TclError, RuntimeError):
            # Toute erreur liée à la destruction des widgets
            pass

    def draw_gradient(self, canvas, height, color1, color2, prolong_ratio=0):
        """Dessine un dégradé horizontal sur le canvas donné."""
        width = canvas.winfo_width()
        if width <= 0 or height <= 0:
            return
        # On ne génère l'image que si la taille a changé
        if not self.gradient_image or self.gradient_image.size != (width, height):
            gradient_image = Image.new("RGB", (width, height), color1)
            draw = ImageDraw.Draw(gradient_image)
            prolong_steps = int(prolong_ratio * width)
            for x in range(prolong_steps, width):
                ratio = (x - prolong_steps) / (width - prolong_steps)
                color = self.interpolate_color(color1, color2, ratio)
                draw.line([(x, 0), (x, height)], fill=color)
            self.gradient_image = gradient_image
            self.gradient_tk_image = ImageTk.PhotoImage(gradient_image)
        canvas.create_image(0, 0, anchor="nw", image=self.gradient_tk_image)

    def interpolate_color(self, color1, color2, ratio):
        """Interpole entre deux couleurs hexadécimales selon un ratio donné."""
        r1, g1, b1 = self.hex_to_rgb(color1)
        r2, g2, b2 = self.hex_to_rgb(color2)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        return f'#{r:02x}{g:02x}{b:02x}'

    def hex_to_rgb(self, hex_color):
        """Convertit une couleur hexadécimale en tuple RGB."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
