import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Union

from units import get_plot_axis_config, PLOT_PAIRS, DEFAULT_PLOT_PAIR



@dataclass
class CPTPlotConfig:
    """Configuration pour l'affichage des graphiques CPT."""

    # 1. Configuration des colonnes (Mapping DataFrame)
    # Accepte soit un nom de colonne (str) soit un numéro de colonne (int, commence à 1)
    col_depth: Union[str, int] = 1
    col_qc: Union[str, int] = 2
    col_qst: Union[str, int] = 3

    # 2. Configuration des limites d'axes
    depth_auto_select: bool = True
    depth_max_manual: Optional[float] = None
    qc_max: Optional[float] = None   # None = derive de plot_pair
    qst_max: Optional[float] = None  # None = derive de plot_pair

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
    xlabel_qc: Optional[str] = None   # None = derive de plot_pair
    xlabel_qst: Optional[str] = None  # None = derive de plot_pair
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

    # 9. Reechantillonnage (downsampling uniquement, pas d'interpolation)
    resample_interval: Optional[float] = None  # En metres. None = pas de reechantillonnage

    # 10. Paire d'unites graphiques
    plot_pair: str = DEFAULT_PLOT_PAIR  # "MPa_kN" ou "kg_kg"

    def __post_init__(self):
        """Validation et initialisation post-creation."""
        # Deriver les parametres depuis la paire si non explicites
        axis_cfg = get_plot_axis_config(self.plot_pair)

        if self.qc_max is None:
            self.qc_max = axis_cfg["qc_max"]
        if self.qst_max is None:
            self.qst_max = axis_cfg["qst_max"]
        if self.xlabel_qc is None:
            self.xlabel_qc = axis_cfg["qc_label"]
        if self.xlabel_qst is None:
            self.xlabel_qst = axis_cfg["qst_label"]

        # Stocker la config d'axes pour usage dans le plot
        self._axis_cfg = axis_cfg

        # Validation des limites
        if self.qc_max <= 0:
            raise ValueError("qc_max doit etre > 0")
        if self.qst_max <= 0:
            raise ValueError("qst_max doit etre > 0")

        # Si qc_annotation_threshold n'est pas defini, utiliser qc_max
        if self.qc_annotation_threshold is None:
            self.qc_annotation_threshold = self.qc_max

        # Validation des marges
        if not (0 < self.adjust_right <= 1):
            raise ValueError("adjust_right doit etre entre 0 et 1")
        if not (0 < self.adjust_top <= 1):
            raise ValueError("adjust_top doit etre entre 0 et 1")
        if not (0 <= self.adjust_bottom < 1):
            raise ValueError("adjust_bottom doit etre entre 0 et 1")
        if not (0 <= self.adjust_left < 1):
            raise ValueError("adjust_left doit etre entre 0 et 1")

        # Validation reechantillonnage
        if self.resample_interval is not None and self.resample_interval <= 0:
            raise ValueError("resample_interval doit etre > 0 ou None")

        # Validation des colonnes (numeros doivent etre >= 1)
        for col_name, col_value in [('col_depth', self.col_depth),
                                     ('col_qc', self.col_qc),
                                     ('col_qst', self.col_qst)]:
            if isinstance(col_value, int) and col_value < 1:
                raise ValueError(f"{col_name} : le numero de colonne doit etre >= 1 (recu: {col_value})")

    def get_depth_limit(self, max_depth_data: float) -> float:
        """
        Calcule la limite de profondeur selon les conventions du bureau.
        Selectionne automatiquement parmi [20, 25, 30, 35, 40] pour englober les donnees.
        """
        if not self.depth_auto_select:
            return self.depth_max_manual if self.depth_max_manual else max_depth_data

        depth_options = [20, 25, 30, 35, 40]

        for depth_limit in depth_options:
            if max_depth_data <= depth_limit:
                return depth_limit

        return np.ceil(max_depth_data / 5) * 5



# Configuration par defaut (correspond au prototype original, sans reechantillonnage)
DEFAULT_CONFIG = CPTPlotConfig()


# Configuration pour rapport (reechantillonnage tous les 20 cm)
REPORT_CONFIG = CPTPlotConfig(
    resample_interval=0.20,  # 20 cm
    figure_dpi=300
)



def _resolve_column_name(df: pd.DataFrame, col_spec: Union[str, int], col_label: str) -> str:
    """
    Resout une specification de colonne (nom ou numero) en nom de colonne reel.
    """
    if isinstance(col_spec, str):
        if col_spec not in df.columns:
            raise ValueError(
                f"{col_label} : colonne '{col_spec}' introuvable dans le DataFrame. "
                f"Colonnes disponibles : {list(df.columns)}"
            )
        return col_spec

    elif isinstance(col_spec, int):
        if col_spec < 1:
            raise ValueError(
                f"{col_label} : le numero de colonne doit etre >= 1 (recu: {col_spec})"
            )
        if col_spec > len(df.columns):
            raise ValueError(
                f"{col_label} : numero de colonne {col_spec} hors limites. "
                f"Le DataFrame contient {len(df.columns)} colonne(s). "
                f"Colonnes : {list(df.columns)}"
            )
        column_name = df.columns[col_spec - 1]
        return column_name

    else:
        raise TypeError(
            f"{col_label} : type invalide {type(col_spec).__name__}. "
            f"Attendu : str (nom de colonne) ou int (numero de colonne)"
        )



def _detect_sampling_interval(depths: pd.Series) -> float:
    """Detecte l'intervalle d'echantillonnage moyen des donnees."""
    if len(depths) < 2:
        return 0.01

    diffs = depths.diff().dropna()
    diffs_filtered = diffs[diffs <= 1.0]

    if len(diffs_filtered) == 0:
        return 0.01

    median_interval = diffs_filtered.median()
    return median_interval



def _resample_cpt_data(df: pd.DataFrame, config: CPTPlotConfig,
                       col_depth_resolved: str, col_qc_resolved: str,
                       col_qst_resolved: str) -> pd.DataFrame:
    """
    Reechantillonne les donnees CPT par selection de points existants (downsampling uniquement).
    """
    if config.resample_interval is None:
        return df.copy()

    df_sorted = df.sort_values(by=col_depth_resolved).copy()
    current_interval = _detect_sampling_interval(df_sorted[col_depth_resolved])

    if config.resample_interval < current_interval * 0.9:
        raise ValueError(
            f"Impossible de reechantillonner a {config.resample_interval}m : "
            f"intervalle actuel detecte = {current_interval:.3f}m. "
            f"Le reechantillonnage ne peut qu'augmenter l'intervalle (downsampling uniquement)."
        )

    if config.resample_interval <= current_interval * 1.1:
        return df_sorted

    depth_min = df_sorted[col_depth_resolved].min()
    depth_max = df_sorted[col_depth_resolved].max()

    depth_start = np.floor(depth_min / config.resample_interval) * config.resample_interval
    target_depths = np.arange(depth_start, depth_max + config.resample_interval,
                              config.resample_interval)

    selected_indices = []

    for target_depth in target_depths:
        distances = np.abs(df_sorted[col_depth_resolved] - target_depth)
        closest_idx = distances.idxmin()
        if distances[closest_idx] <= config.resample_interval * 0.5:
            selected_indices.append(closest_idx)

    if len(selected_indices) == 0:
        return df_sorted

    selected_indices = sorted(set(selected_indices))
    df_resampled = df_sorted.loc[selected_indices].copy()

    return df_resampled



def plot_cpt(df: pd.DataFrame, config: CPTPlotConfig = None) -> tuple:
    """
    Affiche un graphique CPT avec configuration flexible.

    Le graphique s'adapte automatiquement a la paire d'unites selectionnee
    (MPa/kN ou kg/cm2/kg) via config.plot_pair. Les labels, limites d'axes,
    et ticks sont derives de la paire choisie.

    Args:
        df: DataFrame contenant les donnees CPT (deja converties dans l'unite
            de la paire graphique choisie)
        config: Configuration du graphique (utilise DEFAULT_CONFIG si None)

    Returns:
        tuple: (fig, ax1, ax2) - Figure et axes matplotlib
    """
    if config is None:
        config = DEFAULT_CONFIG

    if df.empty:
        raise ValueError("Le DataFrame est vide")

    # Resolution des noms de colonnes
    try:
        col_depth_resolved = _resolve_column_name(df, config.col_depth, "col_depth")
        col_qc_resolved = _resolve_column_name(df, config.col_qc, "col_qc")
        col_qst_resolved = _resolve_column_name(df, config.col_qst, "col_qst")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Erreur lors de la resolution des colonnes : {e}")

    # Reechantillonnage si necessaire
    df_plot = _resample_cpt_data(df, config, col_depth_resolved, col_qc_resolved, col_qst_resolved)

    # Calcul de la limite de profondeur
    max_depth_data = df_plot[col_depth_resolved].max()
    depth_limit = config.get_depth_limit(max_depth_data)

    # Recuperer la configuration d'axes
    axis_cfg = config._axis_cfg

    # Creer la figure et les axes
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

    # Configuration des grilles
    ax1.grid(False)
    ax1.yaxis.grid(True, linestyle='--', linewidth=0.65, color='lightgray', dashes=(4, 7))
    ax2.xaxis.grid(True, which='minor', linestyle='--', linewidth=0.65, color='lightgray', dashes=(4, 7))
    ax2.xaxis.grid(True, which='major', linestyle='--', linewidth=0.65, color='lightgray', dashes=(4, 7))

    # Set Y-axis limits and ticks
    ax1.set_ylim(depth_limit, 0)
    ax1.yaxis.set_major_locator(MultipleLocator(1))

    # Configuration des ticks pour ax1 (qst) - derives de la paire
    ax1.xaxis.set_major_locator(MultipleLocator(axis_cfg["qst_major"]))
    ax1.xaxis.set_minor_locator(MultipleLocator(axis_cfg["qst_minor"]))
    ax1.xaxis.set_tick_params(which='minor', labelbottom=False)

    # Configuration des ticks pour ax2 (qc) - derives de la paire
    ax2.xaxis.set_major_locator(MultipleLocator(axis_cfg["qc_major"]))
    ax2.xaxis.set_minor_locator(MultipleLocator(axis_cfg["qc_minor"]))

    # Set specific ticks and labels for qc axis
    qc_major = axis_cfg["qc_major"]
    qc_ticks = list(np.arange(0, config.qc_max + qc_major * 0.5, qc_major))
    if config.qc_max not in qc_ticks:
        qc_ticks.append(config.qc_max)
    ax2.set_xticks(qc_ticks)
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

    # Trace des courbes
    p1, = ax1.plot(df_plot[col_qst_resolved], df_plot[col_depth_resolved],
                   color=config.qst_color, linewidth=config.qst_linewidth)
    p2, = ax2.plot(df_plot[col_qc_resolved], df_plot[col_depth_resolved],
                   color=config.qc_color, linewidth=config.qc_linewidth)

    # Annotations pour valeurs qc depassant le seuil
    if config.show_annotations:
        mask = df_plot[col_qc_resolved] > config.qc_annotation_threshold
        exceeded_data = df_plot[mask][[col_qc_resolved, col_depth_resolved]].copy()

        if not exceeded_data.empty:
            last_annotated_depth = -float('inf')

            for _, row in exceeded_data.iterrows():
                current_depth = row[col_depth_resolved]

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

    # Titres (si actives)
    if config.show_titles:
        plt.annotate(config.title_main,
                    xy=(0.0, 1.08), xycoords='axes fraction',
                    ha='left', va='center', fontsize=config.title_fontsize)
        plt.annotate("Observations (eau/eboulement)",
                    xy=(0.82, -0.05), xycoords='axes fraction',
                    ha='center', va='center', fontsize=config.title_fontsize)

    # Watermark (si defini)
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
    # Exemple 1: Config par defaut (MPa/kN)
    try:
        fig, ax1, ax2 = plot_cpt(df, DEFAULT_CONFIG)
        plt.show()
    except NameError:
        print("Erreur : Le DataFrame 'df' n'est pas defini.")
    except Exception as e:
        print(f"Erreur lors du trace: {e}")


    # Exemple 2: Config en kg/cm2/kg
    try:
        kg_config = CPTPlotConfig(plot_pair="kg_kg")
        fig, ax1, ax2 = plot_cpt(df, kg_config)
        plt.show()
    except NameError:
        print("Erreur : Le DataFrame 'df' n'est pas defini.")
    except Exception as e:
        print(f"Erreur lors du trace: {e}")
