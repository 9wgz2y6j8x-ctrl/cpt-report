import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Union



@dataclass
class CPTPlotConfig:
    """Configuration pour l'affichage des graphiques CPT."""
    
    # 1. Configuration des colonnes (Mapping DataFrame)
    # Accepte soit un nom de colonne (str) soit un numéro de colonne (int, commence à 1)
    col_depth: Union[str, int] = 1
    col_qc: Union[str, int] = 2
    col_qst: Union[str, int] = 3
    #col_depth: Union[str, int] = 'penetration length'
    #col_qc: Union[str, int] = 'Résistance à la pointe'
    #col_qst: Union[str, int] = 'Force de Frottement totale'
    
    # 2. Configuration des limites d'axes
    depth_auto_select: bool = True
    depth_max_manual: Optional[float] = None
    qc_max: float = 17.0
    qst_max: float = 85.0
    
    # 3. Configuration des courbes (Styles)
    qc_color: str = 'b'
    qc_linewidth: float = 1.60
    qst_color: str = 'orange'
    qst_linewidth: float = 0.55
    
    # 4. Configuration des annotations
    show_annotations: bool = True
    qc_annotation_threshold: Optional[float] = None  # None = use qc_max
    annotation_interval: float = 0.2
    annotation_fontsize: int = 6
    annotation_format: str = '.1f'
    
    # 5. Configuration des labels et titres
    xlabel_qc: str = 'qc [MPa]'
    xlabel_qst: str = 'Qst [kN]'
    ylabel: str = 'Profondeur [m]'
    title_main: str = 'SONDAGE AU PENETROMETRE STATIQUE (CPT)'
    show_titles: bool = True
    label_fontsize: int = 9
    title_fontsize: int = 10
    tick_label_fontsize: int = 8
    
    # 6. Configuration de la figure
    figure_width: float = 10.0
    figure_height: float = 12.0
    figure_dpi: int = 200
    
    # 7. Configuration des marges et layout
    adjust_right: float = 0.85
    adjust_top: float = 0.90
    adjust_bottom: float = 0.10
    adjust_left: float = 0.12
    
    # 8. Watermark
    watermark_text: Optional[str] = None
    
    # 9. Rééchantillonnage (downsampling uniquement, pas d'interpolation)
    resample_interval: Optional[float] = None  # En mètres. None = pas de rééchantillonnage
    
    def __post_init__(self):
        """Validation et initialisation post-création."""
        # Validation des limites
        if self.qc_max <= 0:
            raise ValueError("qc_max doit être > 0")
        if self.qst_max <= 0:
            raise ValueError("qst_max doit être > 0")
        
        # Si qc_annotation_threshold n'est pas défini, utiliser qc_max
        if self.qc_annotation_threshold is None:
            self.qc_annotation_threshold = self.qc_max
        
        # Validation des marges
        if not (0 < self.adjust_right <= 1):
            raise ValueError("adjust_right doit être entre 0 et 1")
        if not (0 < self.adjust_top <= 1):
            raise ValueError("adjust_top doit être entre 0 et 1")
        if not (0 <= self.adjust_bottom < 1):
            raise ValueError("adjust_bottom doit être entre 0 et 1")
        if not (0 <= self.adjust_left < 1):
            raise ValueError("adjust_left doit être entre 0 et 1")
        
        # Validation rééchantillonnage
        if self.resample_interval is not None and self.resample_interval <= 0:
            raise ValueError("resample_interval doit être > 0 ou None")
        
        # Validation des colonnes (numéros doivent être >= 1)
        for col_name, col_value in [('col_depth', self.col_depth), 
                                     ('col_qc', self.col_qc), 
                                     ('col_qst', self.col_qst)]:
            if isinstance(col_value, int) and col_value < 1:
                raise ValueError(f"{col_name} : le numéro de colonne doit être >= 1 (reçu: {col_value})")
    
    def get_depth_limit(self, max_depth_data: float) -> float:
        """
        Calcule la limite de profondeur selon les conventions du bureau.
        Sélectionne automatiquement parmi [20, 25, 30, 35, 40] pour englober les données.
        
        Args:
            max_depth_data: Profondeur maximale dans les données
            
        Returns:
            Limite de profondeur sélectionnée
        """
        if not self.depth_auto_select:
            return self.depth_max_manual if self.depth_max_manual else max_depth_data
        
        # Conventions du bureau
        depth_options = [20, 25, 30, 35, 40]
        
        for depth_limit in depth_options:
            if max_depth_data <= depth_limit:
                return depth_limit
        
        # Si > 40m, utiliser la profondeur max des données arrondie au multiple de 5 supérieur
        return np.ceil(max_depth_data / 5) * 5



# Configuration par défaut (correspond au prototype original, sans rééchantillonnage)
DEFAULT_CONFIG = CPTPlotConfig()


# Configuration pour rapport (rééchantillonnage tous les 20 cm)
REPORT_CONFIG = CPTPlotConfig(
    resample_interval=0.20,  # 20 cm
    figure_dpi=300
)



def _resolve_column_name(df: pd.DataFrame, col_spec: Union[str, int], col_label: str) -> str:
    """
    Résout une spécification de colonne (nom ou numéro) en nom de colonne réel.
    
    Args:
        df: DataFrame contenant les données
        col_spec: Spécification de colonne (str = nom, int = numéro commençant à 1)
        col_label: Label descriptif pour les messages d'erreur (ex: "col_depth")
        
    Returns:
        Nom réel de la colonne dans le DataFrame
        
    Raises:
        ValueError: Si la colonne n'existe pas ou si le numéro est hors limites
        TypeError: Si col_spec n'est ni str ni int
    """
    # Cas 1: col_spec est une string (nom de colonne)
    if isinstance(col_spec, str):
        if col_spec not in df.columns:
            raise ValueError(
                f"{col_label} : colonne '{col_spec}' introuvable dans le DataFrame. "
                f"Colonnes disponibles : {list(df.columns)}"
            )
        return col_spec
    
    # Cas 2: col_spec est un int (numéro de colonne, commence à 1)
    elif isinstance(col_spec, int):
        # Validation : numéro >= 1
        if col_spec < 1:
            raise ValueError(
                f"{col_label} : le numéro de colonne doit être >= 1 (reçu: {col_spec})"
            )
        
        # Validation : numéro <= nombre de colonnes
        if col_spec > len(df.columns):
            raise ValueError(
                f"{col_label} : numéro de colonne {col_spec} hors limites. "
                f"Le DataFrame contient {len(df.columns)} colonne(s). "
                f"Colonnes : {list(df.columns)}"
            )
        
        # Convertir le numéro (base 1) en index (base 0) et récupérer le nom
        column_name = df.columns[col_spec - 1]
        return column_name
    
    # Cas 3: type invalide
    else:
        raise TypeError(
            f"{col_label} : type invalide {type(col_spec).__name__}. "
            f"Attendu : str (nom de colonne) ou int (numéro de colonne)"
        )



def _detect_sampling_interval(depths: pd.Series) -> float:
    """
    Détecte l'intervalle d'échantillonnage moyen des données.
    
    Args:
        depths: Série pandas des profondeurs
        
    Returns:
        Intervalle moyen en mètres
    """
    if len(depths) < 2:
        return 0.01  # Défaut 1 cm
    
    # Calculer les différences entre profondeurs successives
    diffs = depths.diff().dropna()
    
    # Filtrer les valeurs aberrantes (écarts > 1m qui indiqueraient des données manquantes)
    diffs_filtered = diffs[diffs <= 1.0]
    
    if len(diffs_filtered) == 0:
        return 0.01
    
    # Calculer la médiane (plus robuste que la moyenne)
    median_interval = diffs_filtered.median()
    
    return median_interval



def _resample_cpt_data(df: pd.DataFrame, config: CPTPlotConfig, 
                       col_depth_resolved: str, col_qc_resolved: str, 
                       col_qst_resolved: str) -> pd.DataFrame:
    """
    Rééchantillonne les données CPT par sélection de points existants (downsampling uniquement).
    Aucune interpolation : sélectionne les points réels les plus proches des profondeurs cibles.
    
    Args:
        df: DataFrame original
        config: Configuration contenant les paramètres de rééchantillonnage
        col_depth_resolved: Nom réel de la colonne profondeur
        col_qc_resolved: Nom réel de la colonne qc
        col_qst_resolved: Nom réel de la colonne qst
        
    Returns:
        DataFrame rééchantillonné (ou original si pas de rééchantillonnage)
        
    Raises:
        ValueError: Si l'intervalle demandé est plus petit que l'intervalle actuel
    """
    # Si pas de rééchantillonnage demandé, retourner les données originales
    if config.resample_interval is None:
        return df.copy()
    
    # Trier par profondeur pour être sûr
    df_sorted = df.sort_values(by=col_depth_resolved).copy()
    
    # Détecter l'intervalle actuel
    current_interval = _detect_sampling_interval(df_sorted[col_depth_resolved])
    
    # Vérifier qu'on ne demande pas un intervalle plus petit (= interpolation interdite)
    if config.resample_interval < current_interval * 0.9:  # 10% de tolérance
        raise ValueError(
            f"Impossible de rééchantillonner à {config.resample_interval}m : "
            f"intervalle actuel détecté = {current_interval:.3f}m. "
            f"Le rééchantillonnage ne peut qu'augmenter l'intervalle (downsampling uniquement)."
        )
    
    # Si l'intervalle demandé est <= à l'intervalle actuel, pas besoin de rééchantillonner
    if config.resample_interval <= current_interval * 1.1:  # 10% de tolérance
        return df_sorted
    
    # Créer les profondeurs cibles (0, 0.2, 0.4, ...)
    depth_min = df_sorted[col_depth_resolved].min()
    depth_max = df_sorted[col_depth_resolved].max()
    
    # Arrondir depth_min au multiple de resample_interval inférieur ou égal
    depth_start = np.floor(depth_min / config.resample_interval) * config.resample_interval
    
    # Créer la grille de profondeurs cibles
    target_depths = np.arange(depth_start, depth_max + config.resample_interval, 
                              config.resample_interval)
    
    # Pour chaque profondeur cible, trouver l'indice du point réel le plus proche
    selected_indices = []
    
    for target_depth in target_depths:
        # Calculer la distance absolue entre la cible et tous les points réels
        distances = np.abs(df_sorted[col_depth_resolved] - target_depth)
        
        # Trouver l'indice du point le plus proche
        closest_idx = distances.idxmin()
        
        # Vérifier que ce point est suffisamment proche (tolérance = 50% de l'intervalle demandé)
        if distances[closest_idx] <= config.resample_interval * 0.5:
            selected_indices.append(closest_idx)
    
    # Si aucun point trouvé, retourner les données originales
    if len(selected_indices) == 0:
        return df_sorted
    
    # Sélectionner uniquement les points retenus (sans doublons)
    selected_indices = sorted(set(selected_indices))
    df_resampled = df_sorted.loc[selected_indices].copy()
    
    return df_resampled



def plot_cpt(df: pd.DataFrame, config: CPTPlotConfig = None) -> tuple:
    """
    Affiche un graphique CPT avec configuration flexible.
    
    Args:
        df: DataFrame contenant les données CPT
        config: Configuration du graphique (utilise DEFAULT_CONFIG si None)
        
    Returns:
        tuple: (fig, ax1, ax2) - Figure et axes matplotlib
        
    Raises:
        ValueError: Si les colonnes requises sont manquantes ou si rééchantillonnage impossible
        TypeError: Si les spécifications de colonnes sont invalides
    """
    if config is None:
        config = DEFAULT_CONFIG
    
    # Vérification des données vides (avant résolution des colonnes)
    if df.empty:
        raise ValueError("Le DataFrame est vide")
    
    # Résolution des noms de colonnes (conversion numéro → nom si nécessaire)
    try:
        col_depth_resolved = _resolve_column_name(df, config.col_depth, "col_depth")
        col_qc_resolved = _resolve_column_name(df, config.col_qc, "col_qc")
        col_qst_resolved = _resolve_column_name(df, config.col_qst, "col_qst")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Erreur lors de la résolution des colonnes : {e}")
    
    # Rééchantillonnage si nécessaire (downsampling uniquement, pas d'interpolation)
    df_plot = _resample_cpt_data(df, config, col_depth_resolved, col_qc_resolved, col_qst_resolved)
    
    # Calcul de la limite de profondeur
    max_depth_data = df_plot[col_depth_resolved].max()
    depth_limit = config.get_depth_limit(max_depth_data)
    
    # Créer la figure et les axes
    fig, ax1 = plt.subplots(
        figsize=(config.figure_width, config.figure_height),
        dpi=config.figure_dpi
    )
    ax2 = ax1.twiny()
    
    # Configuration de l'axe secondaire
    ax2.spines['top'].set_position(('outward', 0))
    ax2.xaxis.set_ticks_position('top')
    ax2.xaxis.set_label_position('top')
    
    # Inverser l'axe Y
    ax1.invert_yaxis()
    
    # Configuration des grilles (hardcodée comme demandé)
    ax1.grid(False)
    ax1.yaxis.grid(True, linestyle='--', linewidth=0.65, color='lightgray', dashes=(4, 7))
    ax2.xaxis.grid(True, which='minor', linestyle='--', linewidth=0.65, color='lightgray', dashes=(4, 7))
    ax2.xaxis.grid(True, which='major', linestyle='--', linewidth=0.65, color='lightgray', dashes=(4, 7))
    
    # Set Y-axis limits and ticks
    ax1.set_ylim(depth_limit, 0)
    ax1.yaxis.set_major_locator(MultipleLocator(1))
    
    # Configuration des ticks for ax1 (qst) - hardcodée
    ax1.xaxis.set_major_locator(MultipleLocator(25))
    ax1.xaxis.set_minor_locator(MultipleLocator(5))
    ax1.xaxis.set_tick_params(which='minor', labelbottom=False)
    
    # Configuration des ticks for ax2 (qc) - hardcodée
    ax2.xaxis.set_major_locator(MultipleLocator(5))
    ax2.xaxis.set_minor_locator(MultipleLocator(1))
    
    # Set specific ticks and labels for qc axis
    qc_ticks = list(range(0, int(config.qc_max) + 1, 5))
    if config.qc_max not in qc_ticks:
        qc_ticks.append(config.qc_max)
    ax2.set_xticks(qc_ticks)
    # Formater les labels en entier (sans .0) si ce sont des nombres ronds
    qc_labels = [int(tick) if tick == int(tick) else tick for tick in qc_ticks]
    ax2.set_xticklabels(qc_labels, fontweight='bold')
    
    # Taille des ticks
    ax1.tick_params(axis='x', which='major', labelsize=config.tick_label_fontsize)
    ax1.tick_params(axis='y', which='major', labelsize=config.tick_label_fontsize)
    ax2.tick_params(axis='x', which='major', labelsize=config.tick_label_fontsize)
    
    # Labels des axes
    ax1.set_xlabel(config.xlabel_qst, fontweight='light', 
                   fontsize=config.label_fontsize, labelpad=5)
    ax2.set_xlabel(config.xlabel_qc, fontweight='light', 
                   fontsize=config.label_fontsize, labelpad=5)
    ax1.set_ylabel(config.ylabel, fontweight='light', 
                   fontsize=config.label_fontsize, labelpad=5)
    
    # Set X-axis limits
    ax1.set_xlim(0, config.qst_max)
    ax2.set_xlim(0, config.qc_max)
    
    # Tracé des courbes (utilisation des noms résolus)
    p1, = ax1.plot(df_plot[col_qst_resolved], df_plot[col_depth_resolved],
                   color=config.qst_color, linewidth=config.qst_linewidth)
    p2, = ax2.plot(df_plot[col_qc_resolved], df_plot[col_depth_resolved],
                   color=config.qc_color, linewidth=config.qc_linewidth)
    
    # Annotations pour valeurs qc dépassant le seuil (optimisé)
    if config.show_annotations:
        # Vectorisation: filtrer les valeurs dépassant le seuil
        mask = df_plot[col_qc_resolved] > config.qc_annotation_threshold
        exceeded_data = df_plot[mask][[col_qc_resolved, col_depth_resolved]].copy()
        
        if not exceeded_data.empty:
            last_annotated_depth = -float('inf')
            
            for _, row in exceeded_data.iterrows():
                current_depth = row[col_depth_resolved]
                
                # Vérifier l'intervalle minimum
                if current_depth - last_annotated_depth >= config.annotation_interval:
                    value_str = f"{row[col_qc_resolved]:{config.annotation_format}}"
                    ax2.annotate(value_str,
                                (config.qc_max, current_depth),
                                textcoords="offset points",
                                xytext=(5, 0),
                                ha='left', va='center', 
                                fontsize=config.annotation_fontsize,
                                color='black',
                                fontfamily='sans-serif', 
                                fontweight='bold')
                    last_annotated_depth = current_depth
    
    # Titres (si activés)
    if config.show_titles:
        plt.annotate(config.title_main, 
                    xy=(0.0, 1.08), xycoords='axes fraction',
                    ha='left', va='center', fontsize=config.title_fontsize)
        plt.annotate("Observations (eau/éboulement)", 
                    xy=(0.82, -0.05), xycoords='axes fraction',
                    ha='center', va='center', fontsize=config.title_fontsize)
    
    # Watermark (si défini)
    if config.watermark_text:
        fig.text(0.5, 0.5, config.watermark_text,
                fontsize=50, color='gray', alpha=0.2,
                ha='center', va='center', rotation=45)
    
    # Ajustement des marges
    plt.subplots_adjust(
        right=config.adjust_right,
        top=config.adjust_top,
        bottom=config.adjust_bottom,
        left=config.adjust_left
    )
    
    return fig, ax1, ax2



# ============================================================================
# EXEMPLES D'UTILISATION
# ============================================================================


if __name__ == "__main__":
    # Exemple 1: Config par défaut avec noms de colonnes (comportement original)
    try:
        fig, ax1, ax2 = plot_cpt(df, DEFAULT_CONFIG)
        plt.show()
    except NameError:
        print("Erreur : Le DataFrame 'df' n'est pas défini.")
    except Exception as e:
        print(f"Erreur lors du tracé: {e}")
    

    # Exemple 2: Utilisation pour rapport (rééchantillonnage 20 cm)
    try:
        fig, ax1, ax2 = plot_cpt(df, REPORT_CONFIG)
        plt.show()
    except NameError:
        print("Erreur : Le DataFrame 'df' n'est pas défini.")
    except Exception as e:
        print(f"Erreur lors du tracé: {e}")
