"""
report_generator.py

Module de generation de rapports Excel pour les essais CPT.

Produit un fichier Excel par numero de dossier, avec une feuille par essai.
Chaque feuille contient les colonnes de calcul (titres + unites + donnees).
Pour cette iteration, seule la colonne Profondeur est remplie ; les autres
colonnes sont presentes (en-tetes + unites) mais laissees vides.
"""

import os
import re
import math
import logging
from typing import List, Dict, Any, Optional, Callable

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from tabular_reader import load_cpt_dataframe
from cpt_plot import CPTPlotConfig, _resolve_column_name

logger = logging.getLogger(__name__)


# ──────── Colonnes du rapport ────────

REPORT_COLUMNS = [
    "Prof.",
    "Cote",
    "qc",
    "q'0",
    "Qst",
    "\u03c6'",       # φ'
    "\u03c6u",       # φu
    "Padm, 1",
    "Padm, 2",
    "C",
    "Nq",
    "N\u03B3",       # Nγ
]

REPORT_UNITS_TEMPLATE = [
    "[m]",
    "[m]",
    "[kg/cm\u00b2]",   # [kg/cm²]
    "[kg/cm\u00b2]",   # [kg/cm²]
    "[kg]",
    "[\u00b0]",         # [°]
    "[\u00b0]",         # [°]
    "[kg/cm\u00b2]",   # [kg/cm²]
    "[kg/cm\u00b2]",   # [kg/cm²]
    "[/] \u03b1={alpha}",  # [/] α=<valeur>  — sera formatte
    "[/]",
    "[/]",
]


# ──────── Sanitization des noms de feuilles Excel ────────

# Caracteres interdits dans les noms de feuilles Excel
_EXCEL_FORBIDDEN = re.compile(r'[\[\]:*?/\\]')
_MAX_SHEET_NAME = 31


def _sanitize_sheet_name(name: str) -> str:
    """Nettoie un nom pour qu'il soit valide comme nom de feuille Excel.

    - Remplace les caracteres interdits par '_'
    - Tronque a 31 caracteres
    - Supprime les espaces en debut/fin
    """
    name = _EXCEL_FORBIDDEN.sub("_", name).strip()
    if not name:
        name = "Essai"
    return name[:_MAX_SHEET_NAME]


def _deduplicate_sheet_names(names: List[str]) -> List[str]:
    """Garantit l'unicite des noms de feuilles.

    Si deux noms identiques existent, ajoute un suffixe (_2, _3, ...).
    Respecte la limite de 31 caracteres.
    """
    seen: Dict[str, int] = {}
    result = []

    for name in names:
        lower = name.lower()
        if lower in seen:
            seen[lower] += 1
            suffix = f"_{seen[lower]}"
            # Tronquer pour laisser la place au suffixe
            max_base = _MAX_SHEET_NAME - len(suffix)
            deduped = name[:max_base] + suffix
            result.append(deduped)
        else:
            seen[lower] = 1
            result.append(name)

    return result


# ──────── Reechantillonnage ────────

def _resample_depths(
    depths: np.ndarray,
    step_m: float,
    prof_arrondie: float,
) -> np.ndarray:
    """Produit la liste des profondeurs reechantillonnees.

    Parametres
    ----------
    depths : np.ndarray
        Profondeurs triees issues des donnees (brutes ou filtrees).
    step_m : float
        Pas de reechantillonnage en metres (ex. 0.20).
    prof_arrondie : float
        Derniere profondeur a inclure (arrondie depuis la vue Calculer).

    Retours
    -------
    np.ndarray
        Profondeurs selectionnees apres reechantillonnage.

    Strategie
    ---------
    - Genere une grille reguliere : 0.00, step_m, 2*step_m, ..., prof_arrondie.
    - Pour chaque point de la grille, selectionne la profondeur reelle la plus
      proche si elle est dans une tolerance de step_m/2.
    - Si le pas reel des donnees est plus grand que le pas demande (upsampling
      interdit), on conserve les profondeurs originales et on log un warning.
    - La derniere profondeur (prof_arrondie) est toujours incluse, meme si
      absente des donnees.
    """
    if len(depths) < 2:
        return depths

    # Detecter le pas reel median des donnees
    diffs = np.diff(depths)
    data_step = float(np.median(diffs))

    # Si le pas reel est plus grand que le pas demande -> pas de sous-echantillonnage possible
    if data_step > step_m * 1.5:
        logger.warning(
            "Pas reel des donnees (%.4f m) superieur au pas demande (%.4f m). "
            "Les profondeurs originales sont conservees.",
            data_step, step_m,
        )
        # Ajouter prof_arrondie si elle n'est pas deja presente
        if prof_arrondie is not None and (len(depths) == 0 or abs(depths[-1] - prof_arrondie) > 1e-6):
            return np.append(depths, prof_arrondie)
        return depths

    # Generer la grille cible
    n_steps = int(round(prof_arrondie / step_m))
    target_depths = np.round(np.arange(0, n_steps + 1) * step_m, 6)

    # S'assurer que prof_arrondie est le dernier point
    if len(target_depths) == 0 or abs(target_depths[-1] - prof_arrondie) > 1e-6:
        target_depths = np.append(target_depths, prof_arrondie)

    # Selectionner les profondeurs : pour chaque cible, prendre la plus proche
    # dans les donnees reelles (tolerance = step_m / 2)
    tolerance = step_m / 2.0
    selected = []

    for target in target_depths:
        dists = np.abs(depths - target)
        idx = np.argmin(dists)
        if dists[idx] <= tolerance:
            selected.append(float(depths[idx]))
        else:
            # Pas de donnee proche -> inclure la profondeur cible quand meme
            # (utile surtout pour prof_arrondie qui peut depasser les donnees)
            selected.append(float(target))

    # Garantir que la derniere profondeur est exactement prof_arrondie
    if len(selected) > 0 and prof_arrondie is not None:
        selected[-1] = float(prof_arrondie)

    return np.array(selected)


# ──────── Recuperation des donnees filtrables ────────

def _get_dataframe_for_essai(
    file_path: str,
    file_data: dict,
    cleaning_entries: Optional[Dict[str, Any]] = None,
) -> Optional[pd.DataFrame]:
    """Retourne le DataFrame a utiliser pour un essai.

    Utilise les donnees filtrees si disponibles, sinon les donnees brutes.

    Parametres
    ----------
    file_path : str
        Chemin du fichier d'essai.
    file_data : dict
        Donnees du fichier (pour load_cpt_dataframe).
    cleaning_entries : dict, optional
        Mapping {file_path: CPTFileEntry} depuis la vue Filtrer.

    Retours
    -------
    pd.DataFrame ou None
    """
    # Verifier si des donnees filtrees existent
    if cleaning_entries and file_path in cleaning_entries:
        entry = cleaning_entries[file_path]
        if entry.is_filtered and entry.df_filtered is not None:
            logger.info("Utilisation des donnees filtrees pour %s", file_path)
            return entry.df_filtered

    # Sinon, charger les donnees brutes
    try:
        df = load_cpt_dataframe(file_data)
        if df.empty:
            logger.warning("DataFrame vide pour %s", file_path)
            return None
        return df
    except Exception as exc:
        logger.error("Erreur de chargement pour %s : %s", file_path, exc)
        return None


# ──────── Styles Excel ────────

_FONT_HEADER = Font(name="Arial", size=12, bold=True)
_FONT_DATA = Font(name="Courier New", size=11)
_FILL_HEADER = PatternFill(start_color="D6DCE4", end_color="D6DCE4", fill_type="solid")
_BORDER_BOTTOM = Border(bottom=Side(style="thin", color="000000"))
_COL_WIDTH = 12.5
_NUM_COLS = 12


def _format_worksheet(ws) -> None:
    """Applique le formatage standard a une feuille de rapport.

    - Largeur de colonnes : 12,5 pour les 12 colonnes
    - Police : Courier New 11 partout, Arial 12 gras pour la ligne 1
    - Trame de fond bleu-gris pale sur les lignes 1 et 2
    - Bordure inferieure entre la ligne 2 et la ligne 3
    """
    # Largeur des colonnes
    for col_idx in range(1, _NUM_COLS + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = _COL_WIDTH

    # Ligne 1 : Arial 12 gras + fond bleu-gris
    for col_idx in range(1, _NUM_COLS + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = _FONT_HEADER
        cell.fill = _FILL_HEADER

    # Ligne 2 : Courier New 11 + fond bleu-gris + bordure inferieure
    for col_idx in range(1, _NUM_COLS + 1):
        cell = ws.cell(row=2, column=col_idx)
        cell.font = _FONT_DATA
        cell.fill = _FILL_HEADER
        cell.border = _BORDER_BOTTOM

    # Lignes de donnees : Courier New 11 + format 0,00 pour la colonne 1
    for row in ws.iter_rows(min_row=3, max_col=_NUM_COLS):
        for cell in row:
            cell.font = _FONT_DATA
            if cell.column == 1 and cell.value is not None:
                cell.number_format = '0.00'


# ──────── Generation Excel ────────

def generate_excel_reports(
    essais: List[Dict[str, Any]],
    settings_manager,
    cleaning_entries: Optional[Dict[str, Any]] = None,
    raw_data_manager=None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, str]:
    """Genere les fichiers Excel de rapport, un par numero de dossier.

    Parametres
    ----------
    essais : list[dict]
        Liste des essais depuis TraiterView.get_ordered_essais().
        Chaque dict contient : file_path, job, test, alpha, prof_arrondie, ...
    settings_manager : SettingsManager
        Gestionnaire de reglages (pour le pas de reechantillonnage et le dossier
        de sortie).
    cleaning_entries : dict, optional
        Mapping {file_path: CPTFileEntry} depuis la vue Filtrer pour acceder
        aux donnees filtrees.
    raw_data_manager : RawDataManager, optional
        Gestionnaire des donnees brutes (pour acceder aux file_data complets).
    progress_callback : callable, optional
        Fonction(current, total, message) pour le suivi de progression.

    Retours
    -------
    dict
        Mapping {numero_dossier: chemin_fichier_excel} des fichiers generes.

    Raises
    ------
    ValueError
        Si le dossier de sortie n'est pas configure.
    """
    # Recuperer les reglages
    dossier_resultats = settings_manager.get("dossiers_travail", "dossier_resultats")
    if not dossier_resultats or not dossier_resultats.strip():
        raise ValueError(
            "Le dossier d'enregistrement des resultats n'est pas configure. "
            "Veuillez le definir dans Reglages > Dossiers de travail."
        )

    step_cm = settings_manager.get("rapport", "reechantillonnage_cm") or 20
    step_m = step_cm / 100.0

    # Grouper les essais par numero de dossier
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for essai in essais:
        job = essai.get("job", "").strip() or "Sans dossier"
        groups.setdefault(job, []).append(essai)

    total_essais = len(essais)
    current = 0
    generated_files: Dict[str, str] = {}

    for job_number, job_essais in groups.items():
        # Nom du fichier Excel
        safe_job = re.sub(r'[<>:"/\\|?*]', '_', job_number)
        filename = f"{safe_job}-Annexe resultats CPT.xlsx"
        filepath = os.path.join(dossier_resultats, filename)

        # Creer le classeur
        wb = Workbook()
        # Supprimer la feuille par defaut
        wb.remove(wb.active)

        # Preparer les noms de feuilles
        raw_names = []
        for essai in job_essais:
            test_name = essai.get("test", "").strip() or "Essai"
            raw_names.append(_sanitize_sheet_name(test_name))

        sheet_names = _deduplicate_sheet_names(raw_names)

        for i, essai in enumerate(job_essais):
            current += 1
            sheet_name = sheet_names[i]

            if progress_callback:
                progress_callback(
                    current, total_essais,
                    f"Dossier {job_number} - {sheet_name}"
                )

            ws = wb.create_sheet(title=sheet_name)

            # Ecrire les en-tetes (ligne 1 : titres)
            for col_idx, col_title in enumerate(REPORT_COLUMNS, start=1):
                ws.cell(row=1, column=col_idx, value=col_title)

            # Ecrire les unites (ligne 2)
            alpha_val = essai.get("alpha", 1.5)
            # Formater alpha : "1.5" -> "1,5" (notation francaise)
            alpha_str = f"{alpha_val:.1f}".replace(".", ",") if alpha_val != int(alpha_val) else str(int(alpha_val))

            for col_idx, unit_template in enumerate(REPORT_UNITS_TEMPLATE, start=1):
                unit = unit_template.format(alpha=alpha_str)
                ws.cell(row=2, column=col_idx, value=unit)

            # Charger les donnees
            file_path = essai.get("file_path", "")
            file_data = None
            if raw_data_manager:
                file_data = raw_data_manager.get_file(file_path)
            if file_data is None:
                file_data = {"file_path": file_path}

            df = _get_dataframe_for_essai(file_path, file_data, cleaning_entries)
            if df is None:
                logger.warning(
                    "Impossible de charger les donnees pour %s, feuille laissee vide.",
                    file_path,
                )
                continue

            # Resoudre la colonne de profondeur
            try:
                cfg = CPTPlotConfig()
                col_depth = _resolve_column_name(df, cfg.col_depth, "col_depth")
            except Exception as exc:
                logger.error(
                    "Colonne de profondeur introuvable pour %s : %s",
                    file_path, exc,
                )
                continue

            # Extraire et trier les profondeurs
            depths = df[col_depth].dropna().values.astype(float)
            depths = np.sort(depths)

            # Profondeur arrondie (depuis la vue Calculer)
            prof_arrondie = essai.get("prof_arrondie")
            if prof_arrondie is None:
                prof_arrondie = float(depths[-1]) if len(depths) > 0 else 0.0

            # Reechantillonner
            resampled = _resample_depths(depths, step_m, prof_arrondie)

            # Ecrire la colonne Profondeur (colonne 1, a partir de la ligne 3)
            for row_idx, depth_val in enumerate(resampled, start=3):
                ws.cell(row=row_idx, column=1, value=round(depth_val, 2))

            # ── Formatage de la feuille ──
            _format_worksheet(ws)

        # Sauvegarder le classeur
        try:
            os.makedirs(dossier_resultats, exist_ok=True)
            wb.save(filepath)
            generated_files[job_number] = filepath
            logger.info("Fichier Excel genere : %s", filepath)
        except OSError as exc:
            logger.error(
                "Erreur d'ecriture du fichier %s : %s", filepath, exc
            )
            raise

    return generated_files
