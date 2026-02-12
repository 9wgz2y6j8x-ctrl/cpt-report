"""
Vue d'accueil affichée au lancement de l'application.
Affiche une icône loupe, un texte d'onboarding et l'état de l'indexation en temps réel.
"""

import os
import customtkinter as ctk
from datetime import datetime

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from model import get_resource_path


class HomeView(ctk.CTkFrame):
    """
    Écran d'accueil avec :
    - Grande icône loupe (200x200)
    - Texte d'onboarding
    - Bloc état de l'indexation (mise à jour automatique)
    """

    def __init__(self, parent, model, presenter):
        super().__init__(parent, fg_color="#F2F2F2", corner_radius=0)
        self.model = model
        self.presenter = presenter

        # Conserver une référence à l'image pour éviter le garbage collection
        self._loupe_image = None

        self._build_ui()
        self._poll_indexing_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Spacer haut pour pousser le contenu vers ~40 % vertical
        self._spacer_top = ctk.CTkFrame(self, fg_color="transparent", height=0)
        self._spacer_top.pack(side="top", fill="x", expand=True)

        # Conteneur centré horizontal
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(side="top", anchor="center")

        # --- Icône loupe 200x200 ---
        self._create_loupe_icon(container)

        # --- Texte d'onboarding ---
        onboarding_text = (
            "Commencez par ajouter des données brutes en utilisant\n"
            "la recherche rapide ou en parcourant les fichiers de l'ordinateur"
        )
        ctk.CTkLabel(
            container,
            text=onboarding_text,
            font=("Verdana", 13),
            text_color="#888888",
            justify="center",
            wraplength=500,
        ).pack(pady=(18, 0))

        # --- Bloc état de l'indexation ---
        self._create_indexing_block(container)

        # Spacer bas pour équilibrer
        self._spacer_bottom = ctk.CTkFrame(self, fg_color="transparent", height=0)
        self._spacer_bottom.pack(side="top", fill="both", expand=True)

    # ------------------------------------------------------------------ Icône
    def _create_loupe_icon(self, parent):
        icon_path = get_resource_path(os.path.join("icons", "loupe-big.png"))
        fallback_path = get_resource_path(os.path.join("icons", "loupe (1).png"))

        loaded = False
        for path in (icon_path, fallback_path):
            if os.path.isfile(path):
                try:
                    if _HAS_PIL:
                        pil_img = Image.open(path).resize((200, 200), Image.LANCZOS)
                        self._loupe_image = ctk.CTkImage(
                            light_image=pil_img, dark_image=pil_img, size=(200, 200)
                        )
                        ctk.CTkLabel(parent, image=self._loupe_image, text="").pack(pady=(0, 0))
                    else:
                        import tkinter as tk
                        self._loupe_image = tk.PhotoImage(file=path)
                        ctk.CTkLabel(parent, image=self._loupe_image, text="").pack(pady=(0, 0))
                    loaded = True
                    break
                except Exception as e:
                    print(f"Erreur chargement icône ({path}) : {e}")

        if not loaded:
            # Placeholder si l'icône est introuvable
            placeholder = ctk.CTkFrame(
                parent, width=200, height=200, fg_color="#E0E0E0", corner_radius=12
            )
            placeholder.pack(pady=(0, 0))
            placeholder.pack_propagate(False)
            ctk.CTkLabel(
                placeholder,
                text="Icône\nmanquante",
                font=("Verdana", 12),
                text_color="#AAAAAA",
                justify="center",
            ).place(relx=0.5, rely=0.5, anchor="center")

    # ------------------------------------------------------------------ Indexation
    def _create_indexing_block(self, parent):
        block = ctk.CTkFrame(parent, fg_color="#EAEAEA", corner_radius=8)
        block.pack(pady=(28, 0), padx=20, fill="x")

        ctk.CTkLabel(
            block,
            text="État de l'indexation",
            font=("Verdana", 13, "bold"),
            text_color="#444444",
        ).pack(pady=(12, 4))

        info_frame = ctk.CTkFrame(block, fg_color="transparent")
        info_frame.pack(padx=16, pady=(0, 4))

        mono = ("Consolas", 12)
        color = "#555555"

        self._lbl_status = ctk.CTkLabel(info_frame, text="Statut : —", font=mono, text_color=color, anchor="w")
        self._lbl_status.pack(anchor="w", pady=1)

        self._lbl_progress = ctk.CTkLabel(info_frame, text="Progression : —", font=mono, text_color=color, anchor="w")
        self._lbl_progress.pack(anchor="w", pady=1)

        self._lbl_files = ctk.CTkLabel(info_frame, text="Fichiers indexés : —", font=mono, text_color=color, anchor="w")
        self._lbl_files.pack(anchor="w", pady=1)

        self._lbl_last = ctk.CTkLabel(info_frame, text="Dernière indexation : —", font=mono, text_color=color, anchor="w")
        self._lbl_last.pack(anchor="w", pady=(1, 10))

        # Bouton lancer l'indexation
        self._btn_index = ctk.CTkButton(
            block,
            text="Lancer l'indexation",
            font=("Verdana", 12),
            width=180,
            height=30,
            corner_radius=6,
            command=self._on_start_indexing,
        )
        self._btn_index.pack(pady=(0, 12))

        # Message si aucun emplacement configuré
        self._lbl_no_config = ctk.CTkLabel(
            block,
            text="",
            font=("Verdana", 11),
            text_color="#CC6600",
        )
        self._lbl_no_config.pack(pady=(0, 8))

    def _on_start_indexing(self):
        self.model.start_background_indexing()

    # ------------------------------------------------------------------ Polling
    def _poll_indexing_status(self):
        """Met à jour l'affichage de l'état d'indexation toutes les 400ms."""
        try:
            self._refresh_indexing_display()
        except Exception as e:
            print(f"Erreur polling accueil : {e}")

        self.after(400, self._poll_indexing_status)

    def _refresh_indexing_display(self):
        status_info = self.model.get_indexing_status()
        status_code = status_info.get("status", "not_started")

        # Vérifier si des répertoires sont configurés
        has_dirs = bool(self.model.cpt_root_directories)

        if not has_dirs:
            self._lbl_no_config.configure(
                text="Aucun emplacement configuré dans les Préférences."
            )
            self._btn_index.configure(state="disabled")
        else:
            self._lbl_no_config.configure(text="")
            is_indexing = status_info.get("is_indexing", False)
            self._btn_index.configure(state="disabled" if is_indexing else "normal")

        # Statut
        status_map = {
            "not_started": "Non démarrée",
            "indexing": "En cours…",
            "completed": "Terminée",
            "error": "Erreur",
        }
        status_label = status_map.get(status_code, status_code)
        color_map = {
            "not_started": "#888888",
            "indexing": "#1565C0",
            "completed": "#2E7D32",
            "error": "#C62828",
        }
        self._lbl_status.configure(
            text=f"Statut : {status_label}",
            text_color=color_map.get(status_code, "#555555"),
        )

        # Progression
        progress = status_info.get("progress", 0)
        if status_code == "indexing":
            self._lbl_progress.configure(text=f"Progression : {progress:.0f} %")
        elif status_code == "completed":
            self._lbl_progress.configure(text="Progression : 100 %")
        else:
            self._lbl_progress.configure(text="Progression : —")

        # Fichiers indexés
        files_count = "—"
        if self.model.cpt_indexer and hasattr(self.model.cpt_indexer, "indexed_data"):
            count = len(self.model.cpt_indexer.indexed_data)
            if count > 0:
                files_count = str(count)
        self._lbl_files.configure(text=f"Fichiers indexés : {files_count}")

        # Dernière indexation
        last_dt = getattr(self.model, "last_indexing_completed", None)
        if last_dt:
            formatted = last_dt.strftime("%d/%m/%Y %H:%M")
            self._lbl_last.configure(text=f"Dernière indexation : {formatted}")
        else:
            self._lbl_last.configure(text="Dernière indexation : —")
