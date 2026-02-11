"""
cpt_cleaning_mockup_v2.py

Interface de nettoyage des valeurs aberrantes CPT.
Navigation clavier optimisée pour traiter des centaines d'essais.

Navigation:
- Flèches Haut/Bas : Défiler entre les sondages
- Espace : Activer/Désactiver le filtrage automatique
"""

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from typing import Optional
from scipy.ndimage import median_filter

# Configuration
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Palette raffinée avec moins de blanc
COLORS = {
    "bg": "#E8EDF2",              # Fond général
    "card": "#F5F7FA",            # Cartes
    "sidebar": "#DFE4E9",         # Sidebar
    "accent": "#0115B8",          # Bleu accent
    "success": "#16A34A",         # Vert (filtré)
    "text_primary": "#1A1A1A",    # Texte principal
    "text_secondary": "#6B7280",  # Texte secondaire
    "text_tertiary": "#9CA3AF",   # Texte tertiaire
    "selected_bg": "#C7D7E8",     # Sélection
    "divider": "#CBD5E1",         # Séparateurs
    # Graphique
    "qc_raw": "#94A3B8",
    "fs_raw": "#CBD5E1",
    "qc_filtered": "#0115B8",
    "fs_filtered": "#F59E0B",
}

FONTS = {
    "title": ("Verdana", 18, "bold"),
    "subtitle": ("Verdana", 13, "bold"),
    "header_job": ("Verdana", 13, "bold"),      # Job number en gras
    "header_test": ("Verdana", 13),             # Test number normal
    "header_file": ("Verdana", 12),             # Filename plus petit
    "list_item": ("Verdana", 11),
    "list_item_bold": ("Verdana", 11, "bold"),
    "body": ("Verdana", 12),
    "small": ("Verdana", 10),
    "tiny": ("Verdana", 9),
}


# ============================================================================
# FONCTION D'AFFICHAGE SIMULÉE
# ============================================================================

def plot_cpt_diagram(ax_qc, ax_fs, df, color_qc="#0115B8", color_fs="#F59E0B", 
                     alpha=1.0, linewidth=1.5, label_suffix=""):
    """Simule votre fonction d'affichage de diagramme CPT."""
    line_qc = ax_qc.plot(
        df['qc'], df['depth'], 
        color=color_qc, linewidth=linewidth, alpha=alpha,
        label=f'qc{label_suffix}',
        zorder=2 if alpha == 1.0 else 1
    )[0]
    
    line_fs = ax_fs.plot(
        df['fs'], df['depth'], 
        color=color_fs, linewidth=linewidth, alpha=alpha,
        label=f'fs{label_suffix}', linestyle='--',
        zorder=2 if alpha == 1.0 else 1
    )[0]
    
    return line_qc, line_fs


# ============================================================================
# DONNÉES CPT
# ============================================================================

class CPTData:
    """Classe pour générer et stocker des données CPT."""
    
    def __init__(self, file_id: str, filename: str, job_number: str, 
                 test_number: str, location: str):
        self.id = file_id
        self.filename = filename
        self.job_number = job_number
        self.test_number = test_number
        self.location = location
        self.is_filtered = False
        
        self._generate_data()
        
    def _generate_data(self):
        """Génère des données CPT avec pics."""
        np.random.seed(hash(self.id) % 2**32)
        
        depth = np.linspace(0, 20, 200)
        
        # qc base
        qc_base = 5 + np.cumsum(np.random.uniform(-0.15, 0.25, 200))
        qc_base = np.clip(qc_base, 2, 25)
        
        # Pics
        n_spikes = np.random.randint(4, 9)
        spike_indices = np.random.choice(range(20, 180), size=n_spikes, replace=False)
        qc_spikes = qc_base.copy()
        for idx in spike_indices:
            qc_spikes[idx] += np.random.uniform(8, 18)
        
        qc_raw = qc_spikes + np.random.normal(0, 0.3, 200)
        
        # fs corrélé
        fs_raw = qc_raw * np.random.uniform(0.03, 0.06) + np.random.normal(0, 0.02, 200)
        fs_raw = np.clip(fs_raw, 0.01, None)
        
        # DataFrames
        self.df_raw = pd.DataFrame({'depth': depth, 'qc': qc_raw, 'fs': fs_raw})
        
        # Version filtrée
        qc_filtered = median_filter(qc_raw, size=5)
        fs_filtered = median_filter(fs_raw, size=5)
        self.df_filtered = pd.DataFrame({'depth': depth, 'qc': qc_filtered, 'fs': fs_filtered})


# ============================================================================
# WIDGETS
# ============================================================================

class FileListItem(ctk.CTkFrame):
    """Item de liste avec indicateur de statut."""
    
    def __init__(self, parent, cpt_data: CPTData, index: int, on_click):
        super().__init__(parent, fg_color="transparent", corner_radius=6, height=58)
        self.cpt_data = cpt_data
        self.index = index
        self.on_click = on_click
        self.pack_propagate(False)
        
        # Pastille statut (plus grande)
        self.status_dot = ctk.CTkLabel(
            self, text="●", font=("Arial", 24),
            text_color="#9CA3AF", width=28
        )
        self.status_dot.pack(side="left", padx=(12, 8))
        
        # Conteneur texte
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Info principale : Job Number + Test Number
        main_info = f"{cpt_data.job_number} - {cpt_data.test_number}"
        self.main_label = ctk.CTkLabel(
            text_frame, text=main_info, 
            font=FONTS["list_item_bold"],
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.main_label.pack(anchor="w", fill="x")
        
        # Info secondaire : Nom du fichier
        self.filename_label = ctk.CTkLabel(
            text_frame, text=cpt_data.filename, 
            font=FONTS["tiny"], 
            text_color=COLORS["text_secondary"], anchor="w"
        )
        self.filename_label.pack(anchor="w", fill="x", pady=(2, 0))
        
        # Localisation
        location_short = cpt_data.location[:35] + "..." if len(cpt_data.location) > 35 else cpt_data.location
        self.location_label = ctk.CTkLabel(
            text_frame, text=location_short,
            font=FONTS["tiny"],
            text_color=COLORS["text_secondary"], anchor="w"
        )
        self.location_label.pack(anchor="w", fill="x")
        
        # Bindings sur tous les éléments
        for widget in [self, self.status_dot, text_frame, 
                       self.main_label, self.filename_label, self.location_label]:
            widget.bind("<Button-1>", lambda e, idx=index: self.on_click(idx))
        
    def set_selected(self, selected: bool):
        if selected:
            self.configure(fg_color=COLORS["selected_bg"])
        else:
            self.configure(fg_color="transparent")
            
    def update_status(self):
        """Pastille : verte si filtré, grise sinon."""
        if self.cpt_data.is_filtered:
            self.status_dot.configure(text_color=COLORS["success"])
        else:
            self.status_dot.configure(text_color="#9CA3AF")


# ============================================================================
# VUE PRINCIPALE
# ============================================================================

class CPTCleaningView(ctk.CTkFrame):
    """Vue de nettoyage des valeurs aberrantes."""
    
    def __init__(self, parent, cpt_files, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)
        
        self.cpt_files = cpt_files
        self.current_index = -1
        self.list_items = []
        
        # Layout (sidebar plus large)
        self.grid_columnconfigure(0, weight=0, minsize=380)  # Plus large
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self._create_sidebar()
        self._create_chart_area()
        
        # Bindings clavier
        self.after(200, self._setup_bindings)
        
        # Sélection initiale
        if self.cpt_files:
            self.after(100, lambda: self._select_item(0))
    
    def _setup_bindings(self):
        root = self.winfo_toplevel()
        root.bind("<Up>", lambda e: self._navigate(-1))
        root.bind("<Down>", lambda e: self._navigate(1))
        root.bind("<space>", lambda e: self.filter_switch.toggle())
        self.focus_set()
    
    def _create_sidebar(self):
        """Sidebar avec liste."""
        sidebar = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 1))
        
        # Header (hauteur fixe 75)
        header = ctk.CTkFrame(sidebar, fg_color=COLORS["accent"], height=75, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="Nettoyage des valeurs aberrantes", 
            font=FONTS["title"], text_color="white"
        ).pack(pady=(14, 5), padx=20, anchor="w")
        
        self.progress_label = ctk.CTkLabel(
            header, text=f"0 sur {len(self.cpt_files)} traités", 
            font=FONTS["small"], text_color="white"
        )
        self.progress_label.pack(padx=20, anchor="w")
        
        # Liste
        list_frame = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent",
            scrollbar_button_color="#A0A8B0"
        )
        list_frame.pack(fill="both", expand=True, padx=8, pady=12)
        
        for idx, cpt in enumerate(self.cpt_files):
            item = FileListItem(list_frame, cpt, idx, self._on_item_clicked)
            item.pack(fill="x", pady=3)
            self.list_items.append(item)
        
        # Légende
        legend = ctk.CTkFrame(sidebar, fg_color=COLORS["card"], height=70, corner_radius=8)
        legend.pack(fill="x", side="bottom", padx=10, pady=10)
        legend.pack_propagate(False)
        
        ctk.CTkLabel(
            legend, text="Légende", font=FONTS["small"], 
            text_color=COLORS["text_primary"]
        ).pack(anchor="w", padx=12, pady=(8, 4))
        
        legend_items = ctk.CTkFrame(legend, fg_color="transparent")
        legend_items.pack(fill="x", padx=12)
        
        ctk.CTkLabel(
            legend_items, text="● Non traité", font=FONTS["tiny"], 
            text_color="#9CA3AF"
        ).pack(side="left", padx=(0, 12))
        
        ctk.CTkLabel(
            legend_items, text="● Filtré", font=FONTS["tiny"], 
            text_color=COLORS["success"]
        ).pack(side="left")
    
    def _create_chart_area(self):
        """Zone graphique principale."""
        chart_area = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        chart_area.grid(row=0, column=1, sticky="nsew")
        
        # Toolbar (hauteur 75 pour alignement, pas de padding haut/gauche/droite)
        toolbar = ctk.CTkFrame(chart_area, fg_color=COLORS["card"], height=75, corner_radius=0)
        toolbar.pack(fill="x", padx=0, pady=(0, 0))
        toolbar.pack_propagate(False)
        
        # Frame interne pour le contenu
        toolbar_content = ctk.CTkFrame(toolbar, fg_color="transparent")
        toolbar_content.pack(fill="both", expand=True)
        
        # Infos en une seule ligne (gauche)
        info_line = ctk.CTkFrame(toolbar_content, fg_color="transparent")
        info_line.pack(side="left", fill="y", padx=20, pady=0, expand=True)
        info_line.pack_propagate(True)
        
        # Container horizontal pour les infos
        info_container = ctk.CTkFrame(info_line, fg_color="transparent")
        info_container.pack(anchor="w", pady=26)  # Centrage vertical
        
        # Job Number (bleu accent, gras)
        self.job_label = ctk.CTkLabel(
            info_container, text="49.530", 
            font=FONTS["header_job"], 
            text_color=COLORS["accent"]
        )
        self.job_label.pack(side="left")
        
        # Séparateur
        ctk.CTkLabel(
            info_container, text=" - ", 
            font=FONTS["header_test"], 
            text_color=COLORS["text_secondary"]
        ).pack(side="left")
        
        # Test Number (texte primaire, normal)
        self.test_label = ctk.CTkLabel(
            info_container, text="CPT-1000", 
            font=FONTS["header_test"], 
            text_color=COLORS["text_primary"]
        )
        self.test_label.pack(side="left")
        
        # Séparateur
        ctk.CTkLabel(
            info_container, text=" - ", 
            font=FONTS["header_file"], 
            text_color=COLORS["text_tertiary"]
        ).pack(side="left")
        
        # Filename (gris tertiaire, plus petit)
        self.filename_label = ctk.CTkLabel(
            info_container, text="CPT-1000_Sondage_A.GEF", 
            font=FONTS["header_file"], 
            text_color=COLORS["text_tertiary"]
        )
        self.filename_label.pack(side="left")
        
        # Switch filtre (droite)
        controls = ctk.CTkFrame(toolbar_content, fg_color="transparent")
        controls.pack(side="right", padx=20, pady=0)
        
        # Container pour centrage vertical
        switch_container = ctk.CTkFrame(controls, fg_color="transparent")
        switch_container.pack(pady=18)
        
        self.filter_var = ctk.BooleanVar(value=False)
        self.filter_switch = ctk.CTkSwitch(
            switch_container, text="FILTRAGE AUTO", font=FONTS["list_item_bold"],
            command=self._on_filter_toggled, variable=self.filter_var,
            progress_color=COLORS["success"], switch_width=58, switch_height=30
        )
        self.filter_switch.pack()
        
        # Zone graphique
        chart_frame = ctk.CTkFrame(chart_area, fg_color=COLORS["card"], corner_radius=8)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Matplotlib
        self.fig = Figure(figsize=(10, 8), dpi=100, facecolor=COLORS["card"])
        self.fig.subplots_adjust(left=0.08, right=0.92, top=0.96, bottom=0.08)
        
        # Axe principal qc
        self.ax_qc = self.fig.add_subplot(111)
        self.ax_qc.set_xlabel("qc (MPa)", fontweight='bold', fontsize=11, color=COLORS["qc_filtered"])
        self.ax_qc.set_ylabel("Profondeur (m)", fontweight='bold', fontsize=11)
        self.ax_qc.grid(True, linestyle=':', alpha=0.4, linewidth=0.8)
        self.ax_qc.invert_yaxis()
        self.ax_qc.tick_params(axis='x', labelcolor=COLORS["qc_filtered"])
        
        # Axe secondaire fs
        self.ax_fs = self.ax_qc.twiny()
        self.ax_fs.set_xlabel("fs (MPa)", fontweight='bold', fontsize=11, color=COLORS["fs_filtered"])
        self.ax_fs.tick_params(axis='x', labelcolor=COLORS["fs_filtered"])
        
        # Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
    
    def _select_item(self, index: int):
        """Sélectionne un fichier et redessine."""
        if index < 0 or index >= len(self.cpt_files):
            return
        
        # Désélection
        if self.current_index != -1:
            self.list_items[self.current_index].set_selected(False)
        
        # Nouvelle sélection
        self.current_index = index
        cpt = self.cpt_files[index]
        self.list_items[index].set_selected(True)
        
        # Mise à jour des labels du header (une seule ligne)
        self.job_label.configure(text=cpt.job_number)
        self.test_label.configure(text=cpt.test_number)
        self.filename_label.configure(text=cpt.filename)
        
        # Mise à jour du compteur
        filtered_count = sum(1 for c in self.cpt_files if c.is_filtered)
        self.progress_label.configure(text=f"{filtered_count} sur {len(self.cpt_files)} traités")
        
        # Sync switch
        self.filter_var.set(cpt.is_filtered)
        
        # Redessiner
        self._update_chart()
    
    def _update_chart(self):
        """Redessine le graphique avec superposition si filtré."""
        if self.current_index == -1:
            return
        
        cpt = self.cpt_files[self.current_index]
        
        # Clear
        self.ax_qc.clear()
        self.ax_fs.clear()
        
        # Reconfiguration axes
        self.ax_qc.set_xlabel("qc (MPa)", fontweight='bold', fontsize=11, color=COLORS["qc_filtered"])
        self.ax_qc.set_ylabel("Profondeur (m)", fontweight='bold', fontsize=11)
        self.ax_qc.grid(True, linestyle=':', alpha=0.4, linewidth=0.8)
        self.ax_qc.invert_yaxis()
        self.ax_qc.tick_params(axis='x', labelcolor=COLORS["qc_filtered"])
        
        self.ax_fs.set_xlabel("fs (MPa)", fontweight='bold', fontsize=11, color=COLORS["fs_filtered"])
        self.ax_fs.tick_params(axis='x', labelcolor=COLORS["fs_filtered"])
        
        if cpt.is_filtered:
            # Mode filtré : brut transparent + filtré opaque
            plot_cpt_diagram(
                self.ax_qc, self.ax_fs, cpt.df_raw,
                color_qc=COLORS["qc_raw"], color_fs=COLORS["fs_raw"],
                alpha=0.35, linewidth=1.2, label_suffix=" (brut)"
            )
            
            plot_cpt_diagram(
                self.ax_qc, self.ax_fs, cpt.df_filtered,
                color_qc=COLORS["qc_filtered"], color_fs=COLORS["fs_filtered"],
                alpha=1.0, linewidth=2.0, label_suffix=" (filtré)"
            )
        else:
            # Mode brut uniquement
            plot_cpt_diagram(
                self.ax_qc, self.ax_fs, cpt.df_raw,
                color_qc=COLORS["qc_filtered"], color_fs=COLORS["fs_filtered"],
                alpha=1.0, linewidth=1.8, label_suffix=""
            )
        
        # Légende
        lines_qc, labels_qc = self.ax_qc.get_legend_handles_labels()
        lines_fs, labels_fs = self.ax_fs.get_legend_handles_labels()
        self.ax_qc.legend(lines_qc + lines_fs, labels_qc + labels_fs, 
                         loc='lower right', fontsize=9, framealpha=0.95)
        
        self.canvas.draw()
    
    def _on_filter_toggled(self):
        """Toggle filtre."""
        if self.current_index == -1:
            return
        cpt = self.cpt_files[self.current_index]
        cpt.is_filtered = self.filter_var.get()
        self.list_items[self.current_index].update_status()
        
        # Mise à jour du compteur
        filtered_count = sum(1 for c in self.cpt_files if c.is_filtered)
        self.progress_label.configure(text=f"{filtered_count} sur {len(self.cpt_files)} traités")
        
        self._update_chart()
    
    def _navigate(self, delta: int):
        """Navigation clavier."""
        new_index = self.current_index + delta
        if 0 <= new_index < len(self.cpt_files):
            self._select_item(new_index)
    
    def _on_item_clicked(self, index: int):
        """Callback clic sur item."""
        self._select_item(index)


# ============================================================================
# APPLICATION DE TEST
# ============================================================================

class MockupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Nettoyage des valeurs aberrantes - CPT")
        self.geometry("1500x870")
        
        # Centrage
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 750
        y = (self.winfo_screenheight() // 2) - 435
        self.geometry(f"1500x870+{x}+{y}")
        
        # Génération données
        locations = [
            "Bruxelles, Avenue Louise 234",
            "Liège, Rue des Guillemins 45",
            "Anvers, Meir 178",
            "Gand, Korenmarkt 23",
            "Charleroi, Boulevard Tirou 89",
            "Namur, Rue de Fer 12",
            "Mons, Grand Place 56"
        ]
        
        cpt_files = []
        for i in range(22):
            cpt = CPTData(
                file_id=f"file_{i:03d}",
                filename=f"CPT-{1000+i}_Sondage_{chr(65+i%26)}.GEF",
                job_number=f"49.{530+i//4}",
                test_number=f"CPT-{1000+i}",
                location=locations[i % len(locations)]
            )
            cpt_files.append(cpt)
        
        # Vue
        self.cleaning_view = CPTCleaningView(self, cpt_files)
        self.cleaning_view.pack(fill="both", expand=True)


if __name__ == "__main__":
    app = MockupApp()
    app.mainloop()
