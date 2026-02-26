"""
report_generator.py

Module de generation de rapports Excel pour les essais CPT.

Produit un fichier Excel par numero de dossier, avec une feuille par essai.
Chaque feuille contient les colonnes de calcul (titres + unites + donnees).

Colonnes remplies :
  - Prof.  : profondeur reechantillonnee
  - Cote   : cote de depart - profondeur
  - qc     : resistance a la pointe corrigee [kg/cm2]
  - q'0    : contrainte naturelle effective [kg/cm2]
  - Qst    : frottement lateral total corrige [kg]
  - phi'   : angle de frottement effectif [deg] (min 30 deg)
  - phi_u  : angle de frottement brut [deg]
  - Padm,1 : pression admissible sous semelle 1 [kg/cm2]
  - Padm,2 : pression admissible sous semelle 2 [kg/cm2]

Les colonnes qc et Qst necessitent la selection d'une machine dans la
vue Calculer ; sans machine, elles restent vides (ainsi que phi', phi_u,
Padm1 et Padm2 qui dependent de qc).
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
from cpt_correction import (
    ParamsAppareilCPT,
    calculer_qc_corrige,
    calculer_qst_corrige,
    _compter_tiges,
)
from units import qc_to_internal, qst_to_internal, internal_to_plot
from friction_angle import calculer_angles_frottement
from bearing_capacity import calculer_pressions_admissibles

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
    "[kg/cm\u00b2] B={b1}",   # [kg/cm²] B=<largeur1>  — sera formatte
    "[kg/cm\u00b2] B={b2}",   # [kg/cm²] B=<largeur2>  — sera formatte
    "[/] \u03b1={alpha}",      # [/] α=<valeur>  — sera formatte
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


# ──────── Contrainte naturelle effective (q'0) ────────

_RHO_EAU = 1000.0  # Masse volumique de l'eau [kg/m³]


def _contrainte_effective_verticale(
    profondeur: float,
    rho_sec: float,
    rho_sat: float,
    niveau_nappe: Optional[float],
) -> float:
    """Calcule la contrainte effective verticale sigma'_v a une profondeur donnee.

    Parametres
    ----------
    profondeur : float
        Profondeur par rapport au terrain naturel [m]. Doit etre >= 0.
    rho_sec : float
        Masse volumique du sol au-dessus de la nappe [kg/m³].
    rho_sat : float
        Masse volumique du sol sature en-dessous de la nappe [kg/m³].
    niveau_nappe : float | None
        Profondeur de la nappe [m]. None = pas de nappe.

    Retours
    -------
    float
        Contrainte effective verticale [kgf/cm²].

    Principe :
      - Au-dessus de la nappe (ou sans nappe) : sigma'_v = z * rho_sec / 10 000
      - En-dessous de la nappe :
            sigma'_v = [z_nappe * rho_sec + (z - z_nappe) * (rho_sat - rho_eau)] / 10 000
    """
    if profondeur <= 0:
        return 0.0

    nappe_presente = niveau_nappe is not None and niveau_nappe >= 0
    sous_la_nappe = nappe_presente and (profondeur >= niveau_nappe)

    if sous_la_nappe:
        z_nappe = niveau_nappe
        pression_au_dessus = z_nappe * rho_sec
        rho_dejauge = rho_sat - _RHO_EAU
        pression_en_dessous = (profondeur - z_nappe) * rho_dejauge
        return (pression_au_dessus + pression_en_dessous) / 10_000
    else:
        return (profondeur * rho_sec) / 10_000


def _resolve_niveau_nappe(observations: Optional[dict]) -> Optional[float]:
    """Determine le niveau de nappe a utiliser pour un essai.

    Priorite : fin_chantier > fin_essai > None (sans nappe).

    Parametres
    ----------
    observations : dict | None
        Donnees du store d'observations pour un essai.
        Structure attendue : {"hole_obs": {"Niveau d'eau": {"fin_essai": str, "fin_chantier": str}}, ...}

    Retours
    -------
    float | None
        Profondeur de la nappe [m], ou None si aucune donnee valide.
    """
    if not observations:
        return None

    hole_obs = observations.get("hole_obs", {})
    niveau_eau = hole_obs.get("Niveau d'eau", {})

    # Priorite 1 : fin de chantier
    fin_chantier = niveau_eau.get("fin_chantier", "").strip()
    if fin_chantier:
        try:
            val = float(fin_chantier.replace(",", "."))
            if val >= 0:
                return val
        except (ValueError, TypeError):
            pass

    # Priorite 2 : fin d'essai
    fin_essai = niveau_eau.get("fin_essai", "").strip()
    if fin_essai:
        try:
            val = float(fin_essai.replace(",", "."))
            if val >= 0:
                return val
        except (ValueError, TypeError):
            pass

    return None


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


# ──────── Construction des parametres de correction ────────

def _build_correction_params(
    essai: Dict[str, Any],
    settings_manager,
    raw_data_manager=None,
) -> Optional[ParamsAppareilCPT]:
    """Construit les ParamsAppareilCPT depuis l'essai et la config machine.

    Retourne None si la machine n'est pas selectionnee ou introuvable.
    """
    machine_name = essai.get("machine", "").strip()
    if not machine_name:
        return None

    machines = settings_manager.get_machines()
    machine_cfg = next(
        (m for m in machines if m.get("nom") == machine_name), None
    )
    if machine_cfg is None:
        logger.warning(
            "Machine '%s' introuvable dans la configuration.", machine_name
        )
        return None

    section = essai.get("section", "Grande")
    if section == "Petite":
        poids_tige_kg = machine_cfg.get("poids_tige_petite_section", 0.0)
        poids_tube_kg = machine_cfg.get("poids_tube_petite_section", 0.0)
    else:
        poids_tige_kg = machine_cfg.get("poids_tige_grande_section", 0.0)
        poids_tube_kg = machine_cfg.get("poids_tube_grande_section", 0.0)

    tip_area_cm2 = settings_manager.get("unites", "tip_area_cm2") or 10.0
    section_pointe_m2 = tip_area_cm2 * 1e-4  # cm2 -> m2

    return ParamsAppareilCPT(
        section_pointe_m2=section_pointe_m2,
        poids_tige_kg=poids_tige_kg,
        poids_tube_kg=poids_tube_kg,
        delta_petit_mano_kg=essai.get("delta_petit", 0),
        delta_grand_mano_kg=essai.get("delta_grand", 0),
        nb_tubes_avant_sol=machine_cfg.get("nb_tubes_avant_sol", 0),
    )


def _compute_corrections(
    df: pd.DataFrame,
    col_depth: str,
    params: ParamsAppareilCPT,
    unit_qc: str,
    unit_qst: str,
    tip_area_cm2: float,
) -> Optional[Dict[str, np.ndarray]]:
    """Calcule qc corrige et Qst corrige pour un DataFrame d'essai.

    Retourne un dict avec les cles :
        'depths'   : profondeurs valides triees
        'qc_out'   : qc corrige en kg/cm2
        'qst_out'  : Qst corrige en kg

    Retourne None en cas d'erreur.
    """
    cfg = CPTPlotConfig()
    try:
        col_qc = _resolve_column_name(df, cfg.col_qc, "col_qc")
        col_qst = _resolve_column_name(df, cfg.col_qst, "col_qst")
    except Exception as exc:
        logger.warning("Colonnes qc/Qst introuvables : %s", exc)
        return None

    # Extraire les donnees valides (profondeur non NaN)
    mask = df[col_depth].notna()
    df_valid = df.loc[mask].copy()
    df_valid = df_valid.sort_values(by=col_depth).reset_index(drop=True)

    if df_valid.empty:
        return None

    valid_depths = df_valid[col_depth].values.astype(float)
    valid_qc = df_valid[col_qc].fillna(0).values.astype(float)
    valid_qst = df_valid[col_qst].fillna(0).values.astype(float)

    # Convertir en unites internes (DaN/m2 et DaN)
    qc_internal = qc_to_internal(valid_qc, unit_qc, tip_area_cm2)
    qst_internal = qst_to_internal(valid_qst, unit_qst)

    # Compter les tiges par profondeur
    depth_series = pd.Series(valid_depths)
    qc_series = pd.Series(qc_internal)
    qst_series = pd.Series(qst_internal)

    n_tiges = _compter_tiges(depth_series, params.nb_tubes_avant_sol)

    # Calculer qc corrige
    qc_corrige = calculer_qc_corrige(qc_series, n_tiges, params)

    # Reconstruire rtotale pour le calcul de Qst
    rtotale_danm2 = qc_series + qst_series / params.section_pointe_m2

    # Calculer Qst corrige
    qst_corrige = calculer_qst_corrige(
        rtotale_danm2, qc_corrige, n_tiges, params
    )

    # Convertir en unites de sortie (kg/cm2 et kgf)
    qc_out, qst_out, _, _ = internal_to_plot(
        qc_corrige.values, qst_corrige.values,
        pair="kg_kg", tip_area_cm2=tip_area_cm2,
    )

    return {
        "depths": valid_depths,
        "qc_out": qc_out,
        "qst_out": qst_out,
    }


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

    # Lignes de donnees : Courier New 11 + format numerique
    for row in ws.iter_rows(min_row=3, max_col=_NUM_COLS):
        for cell in row:
            cell.font = _FONT_DATA
            if cell.value is not None:
                if cell.column in (1, 2, 3, 4, 5, 6, 7, 8, 9):
                    cell.number_format = '0.00'


# ──────── Generation Excel ────────

def generate_excel_reports(
    essais: List[Dict[str, Any]],
    settings_manager,
    cleaning_entries: Optional[Dict[str, Any]] = None,
    raw_data_manager=None,
    cotes: Optional[Dict[str, float]] = None,
    observations: Optional[Dict[str, dict]] = None,
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
    cotes : dict, optional
        Mapping {file_path: cote_de_depart} depuis la vue Cotes.
        Si absent ou si un essai n'a pas de cote, cote_de_depart = 0.
    observations : dict, optional
        Mapping {file_path: store_dict} depuis la vue Observations.
        Chaque store_dict contient les niveaux d'eau (hole_obs) et annotations.
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

    # Masses volumiques depuis les reglages
    rho_sec = settings_manager.get("parametres_calcul", "masse_volumique_sol_sec") or 1800
    rho_sat = settings_manager.get("parametres_calcul", "masse_volumique_sol_sature") or 2000

    # Parametres de calcul de portance
    methode_portance = (
        settings_manager.get("parametres_calcul", "methode_calcul_portance")
        or "De Beer (adapté)"
    )
    largeur_semelle_1 = (
        settings_manager.get("parametres_calcul", "largeur_semelle_fondation_1")
        or 0.6
    )
    largeur_semelle_2 = (
        settings_manager.get("parametres_calcul", "largeur_semelle_fondation_2")
        or 1.5
    )
    coeff_securite = (
        settings_manager.get("parametres_calcul", "coefficient_securite")
        or 2
    )

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
            # Formater le coefficient de securite : "2.0" -> "2", "1.5" -> "1,5" (notation francaise)
            coeff_sec_str = (
                f"{coeff_securite:.1f}".replace(".", ",")
                if coeff_securite != int(coeff_securite)
                else str(int(coeff_securite))
            )
            # Formater les largeurs de semelles en cm pour l'affichage
            b1_cm = int(round(largeur_semelle_1 * 100))
            b2_cm = int(round(largeur_semelle_2 * 100))

            for col_idx, unit_template in enumerate(REPORT_UNITS_TEMPLATE, start=1):
                unit = unit_template.format(
                    alpha=coeff_sec_str, b1=f"{b1_cm}cm", b2=f"{b2_cm}cm",
                )
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

            # Ecrire la colonne Cote (colonne 2) : cote = cote_de_depart - prof
            cote_depart = (cotes or {}).get(file_path, 0.0)
            for row_idx, depth_val in enumerate(resampled, start=3):
                ws.cell(row=row_idx, column=2, value=round(cote_depart - depth_val, 2))

            # ── Contrainte naturelle q'0 (colonne 4) ──
            obs_store = (observations or {}).get(file_path)
            niveau_nappe = _resolve_niveau_nappe(obs_store)

            q0_values = []
            for row_idx, depth_val in enumerate(resampled, start=3):
                q0 = _contrainte_effective_verticale(
                    depth_val, rho_sec, rho_sat, niveau_nappe,
                )
                ws.cell(row=row_idx, column=4, value=round(q0, 2))
                q0_values.append(q0)

            # ── Correction qc et Qst ──
            correction_params = _build_correction_params(
                essai, settings_manager, raw_data_manager,
            )

            if correction_params is not None:
                tip_area_cm2 = (
                    settings_manager.get("unites", "tip_area_cm2") or 10.0
                )
                unit_qc = "MPa"
                unit_qst = "kN"
                if raw_data_manager:
                    unit_qc = raw_data_manager.get_unit(file_path, "unit_qc")
                    unit_qst = raw_data_manager.get_unit(file_path, "unit_qst")

                corrections = _compute_corrections(
                    df, col_depth, correction_params,
                    unit_qc, unit_qst, tip_area_cm2,
                )

                if corrections is not None:
                    corr_depths = corrections["depths"]
                    qc_out = corrections["qc_out"]
                    qst_out = corrections["qst_out"]

                    # Pour chaque profondeur reechantillonnee, trouver la
                    # valeur corrigee la plus proche
                    for row_idx, depth_val in enumerate(resampled, start=3):
                        idx = int(np.argmin(np.abs(corr_depths - depth_val)))
                        qc_val = float(qc_out[idx])
                        ws.cell(
                            row=row_idx, column=3,
                            value=round(qc_val, 2),
                        )
                        ws.cell(
                            row=row_idx, column=5,
                            value=round(float(qst_out[idx]), 2),
                        )

                        # ── Angles de frottement phi' (col 6) et phi_u (col 7) ──
                        q0_val = q0_values[row_idx - 3]
                        phi_prime, phi_u = calculer_angles_frottement(qc_val, q0_val)
                        if phi_prime is not None:
                            ws.cell(row=row_idx, column=6, value=round(phi_prime, 2))
                        if phi_u is not None:
                            ws.cell(row=row_idx, column=7, value=round(phi_u, 2))

                        # ── Pressions admissibles Padm1 (col 8) et Padm2 (col 9) ──
                        if phi_prime is not None and phi_u is not None and q0_val > 0:
                            padm1, padm2 = calculer_pressions_admissibles(
                                methode=methode_portance,
                                profondeur=depth_val,
                                q0_kgcm2=q0_val,
                                phip_deg=phi_prime,
                                phiu_deg=phi_u,
                                largeur_semelle_1_m=largeur_semelle_1,
                                largeur_semelle_2_m=largeur_semelle_2,
                                coeff_securite=coeff_securite,
                                rho_sec=rho_sec,
                                rho_sat=rho_sat,
                                niveau_nappe=niveau_nappe,
                                qc_kgcm2=qc_val,
                            )
                            ws.cell(row=row_idx, column=8, value=round(padm1, 2))
                            ws.cell(row=row_idx, column=9, value=round(padm2, 2))
            else:
                machine_name = essai.get("machine", "").strip()
                if not machine_name:
                    logger.info(
                        "Aucune machine selectionnee pour %s, colonnes qc/Qst "
                        "laissees vides.",
                        file_path,
                    )

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
