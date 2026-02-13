"""
Vue d'accueil affichée au lancement de l'application.
Affiche une icône loupe et un texte d'onboarding.
"""

import os
import customtkinter as ctk

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
    """

    def __init__(self, parent, model, presenter):
        super().__init__(parent, fg_color="#F2F2F2", corner_radius=0)
        self.model = model
        self.presenter = presenter

        # Conserver une référence à l'image pour éviter le garbage collection
        self._loupe_image = None

        self._build_ui()

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
