"""
tabular_reader.py

Lecture de fichiers tabulaires (CSV, XLS, XLSX) pour import CPT.
Fournit :
- détection automatique du séparateur CSV et du caractère décimal
- détection heuristique de la présence d'un en-tête
- lecture Excel (choix de feuille)
- normalisation vers un DataFrame standard (depth_m, qc_mpa, qst_kn)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union


# ---------------------------------------------------------------------------
# Détection CSV : séparateur + décimal
# ---------------------------------------------------------------------------

_CANDIDATE_SEPS = [";", ",", "\t"]
_CANDIDATE_DECIMALS = [".", ","]


def detect_csv_params(filepath: str, n_lines: int = 20) -> Dict[str, str]:
    """
    Détecte le séparateur et le caractère décimal d'un fichier CSV.

    Retourne {"sep": ..., "decimal": ...}.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = [f.readline() for _ in range(n_lines)]
    lines = [l for l in lines if l.strip()]

    if not lines:
        return {"sep": ";", "decimal": "."}

    # Choisir le séparateur qui donne le nombre de colonnes le plus constant > 1
    best_sep = ";"
    best_score = -1
    for sep in _CANDIDATE_SEPS:
        counts = [len(l.split(sep)) for l in lines]
        if not counts:
            continue
        ncols = counts[0]
        if ncols < 2:
            continue
        # Score = ncols × homogénéité (toutes les lignes ont le même nombre)
        uniformity = sum(1 for c in counts if c == ncols) / len(counts)
        score = ncols * uniformity
        if score > best_score:
            best_score = score
            best_sep = sep

    # Déterminer le caractère décimal
    # Si le séparateur est "," alors le décimal est forcément "."
    if best_sep == ",":
        return {"sep": ",", "decimal": "."}

    # Sinon tester si "," apparaît dans des contextes numériques (ex: "1,5")
    sample = " ".join(lines)
    # Compter les virgules qui ressemblent à des décimales (digit,digit)
    import re
    comma_decimal_count = len(re.findall(r"\d,\d", sample))
    dot_decimal_count = len(re.findall(r"\d\.\d", sample))

    decimal = "," if comma_decimal_count > dot_decimal_count else "."
    return {"sep": best_sep, "decimal": decimal}


# ---------------------------------------------------------------------------
# Détection d'en-tête
# ---------------------------------------------------------------------------

def _is_numeric_value(val) -> bool:
    """Vérifie si une valeur peut être interprétée comme un nombre."""
    if pd.isna(val):
        return False
    try:
        s = str(val).strip().replace(",", ".")
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def detect_has_header(df_raw: pd.DataFrame) -> bool:
    """
    Heuristique : si la première ligne du DataFrame (lu sans header) est
    majoritairement non-numérique alors que la 2e l'est, c'est un header.
    """
    if df_raw.empty or len(df_raw) < 2:
        return False

    first_row = df_raw.iloc[0]
    second_row = df_raw.iloc[1]

    num_first = sum(_is_numeric_value(v) for v in first_row)
    num_second = sum(_is_numeric_value(v) for v in second_row)

    total = len(first_row)
    if total == 0:
        return False

    # La première ligne est un header si elle est nettement moins numérique
    ratio_first = num_first / total
    ratio_second = num_second / total

    # Si la 1re ligne a < 50 % de valeurs numériques et la 2e en a > 50 %
    if ratio_first < 0.5 and ratio_second >= 0.5:
        return True
    # Cas limite : même si la 1re a quelques numériques, si la 2e est
    # clairement plus numérique, considérer comme header
    if ratio_first < ratio_second and ratio_first < 0.6:
        return True

    return False


# ---------------------------------------------------------------------------
# Lecture de fichier tabulaire (CSV / Excel)
# ---------------------------------------------------------------------------

def get_excel_sheet_names(filepath: str) -> List[str]:
    """Retourne la liste des noms de feuilles d'un fichier Excel."""
    xls = pd.ExcelFile(filepath)
    return xls.sheet_names


def read_tabular_raw(
    filepath: str,
    sheet_name: Optional[str] = None,
    csv_sep: Optional[str] = None,
    csv_decimal: Optional[str] = None,
) -> Tuple[pd.DataFrame, bool, Dict]:
    """
    Lit un fichier CSV ou Excel et retourne :
    - df : DataFrame brut (toujours lu SANS header pandas pour analyse)
    - has_header : True si la première ligne semble être un en-tête
    - info : dict avec métadonnées ("sheet_name", "csv_sep", "csv_decimal")

    Le DataFrame retourné a des colonnes numériques (0, 1, 2, ...).
    Si has_header=True, la première ligne du df contient les noms ; elle
    peut être consommée par l'appelant pour construire le mapping.
    """
    ext = Path(filepath).suffix.lower()
    info: Dict = {}

    if ext == ".csv":
        if csv_sep is None or csv_decimal is None:
            detected = detect_csv_params(filepath)
            csv_sep = csv_sep or detected["sep"]
            csv_decimal = csv_decimal or detected["decimal"]
        info["csv_sep"] = csv_sep
        info["csv_decimal"] = csv_decimal

        df = pd.read_csv(
            filepath,
            sep=csv_sep,
            decimal=csv_decimal,
            header=None,
            encoding="utf-8",
            encoding_errors="replace",
            on_bad_lines="skip",
            dtype=str,  # tout en string pour analyse
        )
    elif ext in (".xls", ".xlsx"):
        if sheet_name is None:
            sheets = get_excel_sheet_names(filepath)
            sheet_name = sheets[0] if sheets else 0
        info["sheet_name"] = sheet_name

        df = pd.read_excel(
            filepath,
            sheet_name=sheet_name,
            header=None,
            dtype=str,
        )
    else:
        raise ValueError(f"Extension non supportée : {ext}")

    # Supprimer lignes/colonnes entièrement vides
    df = df.dropna(how="all").reset_index(drop=True)
    df = df.loc[:, df.notna().any()]
    df.columns = list(range(len(df.columns)))

    has_header = detect_has_header(df)
    info["has_header"] = has_header

    return df, has_header, info


def extract_header_names(df_raw: pd.DataFrame) -> List[str]:
    """Extrait les noms de colonnes depuis la première ligne du DataFrame brut."""
    if df_raw.empty:
        return []
    return [str(v).strip() for v in df_raw.iloc[0]]


def build_data_df(df_raw: pd.DataFrame, has_header: bool) -> pd.DataFrame:
    """
    Construit un DataFrame numérique à partir du DataFrame brut string.
    Si has_header=True, la première ligne est retirée (c'est l'en-tête).
    """
    if has_header:
        df = df_raw.iloc[1:].copy().reset_index(drop=True)
    else:
        df = df_raw.copy()

    # Convertir en numérique (les virgules décimales sont gérées par remplacement)
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.replace(",", ".", regex=False)
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ---------------------------------------------------------------------------
# Statistiques pour l'aperçu
# ---------------------------------------------------------------------------

def compute_preview_stats(df_numeric: pd.DataFrame, col_names: Optional[List[str]] = None) -> Dict:
    """
    Calcule les statistiques d'aperçu pour l'assistant d'import.
    """
    stats: Dict = {
        "n_rows": len(df_numeric),
        "n_cols": len(df_numeric.columns),
        "columns": {},
    }

    for i, col in enumerate(df_numeric.columns):
        label = col_names[i] if col_names and i < len(col_names) else f"Col {i + 1}"
        series = df_numeric[col]
        stats["columns"][i] = {
            "label": label,
            "n_nan": int(series.isna().sum()),
            "min": float(series.min()) if series.notna().any() else None,
            "max": float(series.max()) if series.notna().any() else None,
            "is_numeric": series.notna().any(),
        }

    return stats


# ---------------------------------------------------------------------------
# Normalisation vers le format pipeline CPT
# ---------------------------------------------------------------------------

def normalize_tabular_dataframe(
    df_numeric: pd.DataFrame,
    col_depth_idx: int,
    col_qc_idx: int,
    col_qst_idx: int,
    is_qt: bool = False,
) -> pd.DataFrame:
    """
    Normalise un DataFrame tabulaire vers le format attendu par le pipeline CPT.

    Paramètres
    ----------
    df_numeric : DataFrame numérique
    col_depth_idx : index (0-based) de la colonne profondeur
    col_qc_idx : index (0-based) de la colonne qc (MPa)
    col_qst_idx : index (0-based) de la colonne Qst ou Qt (kN)
    is_qt : si True, la colonne 3 est Qt et on calcule Qst = Qt - qc

    Retourne un DataFrame avec 3 colonnes nommées identiquement aux colonnes
    par défaut des fichiers GEF (index 1-based : col 1=depth, 2=qc, 3=qst).
    On utilise des noms génériques pour que CPTPlotConfig(col_depth=1, col_qc=2, col_qst=3)
    fonctionne directement.
    """
    depth = df_numeric.iloc[:, col_depth_idx].astype(float)
    qc = df_numeric.iloc[:, col_qc_idx].astype(float)
    q3 = df_numeric.iloc[:, col_qst_idx].astype(float)

    if is_qt:
        qst = q3 - qc
    else:
        qst = q3

    df_norm = pd.DataFrame({
        "depth_m": depth,
        "qc_mpa": qc,
        "qst_kn": qst,
    })

    # Nettoyage : supprimer lignes avec NaN, trier par profondeur
    df_norm = df_norm.dropna(subset=["depth_m", "qc_mpa", "qst_kn"])
    df_norm = df_norm.sort_values("depth_m").reset_index(drop=True)

    return df_norm


# ---------------------------------------------------------------------------
# Fonction unifiée de chargement CPT (GEF ou tabulaire)
# ---------------------------------------------------------------------------

def load_cpt_dataframe(file_data: dict) -> pd.DataFrame:
    """
    Charge un DataFrame CPT normalisé à partir de file_data.

    - source_type="gef" : lecture via read_gef_to_dataframe()
    - source_type="tabular" : lecture CSV/Excel + mapping + conversion Qt si demandé

    Le DataFrame retourné est directement compatible avec CPTPlotConfig par défaut
    (col 1 = depth, col 2 = qc, col 3 = qst).
    """
    source_type = file_data.get("source_type", "gef")
    file_path = file_data["file_path"]

    if source_type == "gef":
        from gef_reader import read_gef_to_dataframe
        return read_gef_to_dataframe(file_path)

    # --- Tabulaire ---
    mapping = file_data.get("tabular_mapping", {})
    has_header = file_data.get("has_header", False)
    sheet_name = file_data.get("sheet_name", None)
    csv_sep = file_data.get("csv_sep", None)
    csv_decimal = file_data.get("csv_decimal", None)

    df_raw, _, _ = read_tabular_raw(
        file_path,
        sheet_name=sheet_name,
        csv_sep=csv_sep,
        csv_decimal=csv_decimal,
    )

    df_numeric = build_data_df(df_raw, has_header)

    col_depth_idx = mapping.get("depth", 0)
    col_qc_idx = mapping.get("qc", 1)
    col_qst_idx = mapping.get("qst", 2)
    is_qt = mapping.get("is_qt", False)

    df_norm = normalize_tabular_dataframe(
        df_numeric,
        col_depth_idx=col_depth_idx,
        col_qc_idx=col_qc_idx,
        col_qst_idx=col_qst_idx,
        is_qt=is_qt,
    )

    return df_norm
