"""
units.py

Module central de gestion des unites pour les donnees CPT (qc et Qst).

Utilise Pint pour toutes les conversions.
Conventions :
- Entree : MPa / kN (standard) ou kg / kg (historique, interprete comme kgf)
- Interne : DaN/m2 (qc) et DaN (Qst)
- Sortie graphique : (MPa, kN) ou (kg/cm2, kg)

g = 9.81 m/s2 (convention geotechnique).
Surface de pointe (TIP_AREA) : par defaut 10 cm2, configurable.
"""

import warnings
import numpy as np
import pint

# ──────────────────────── Registre Pint unique ────────────────────────

ureg = pint.UnitRegistry()

# Definir daN (decanewton) = 10 N
ureg.define("daN = 10 * newton")

# Definir kgf (kilogramme-force) base sur g = 9.81
ureg.define("kgf = 9.81 * newton")

# Raccourcis de Quantity
Q_ = ureg.Quantity


# ──────────────────────── Constantes ────────────────────────

G_MS2 = 9.81  # acceleration gravitationnelle conventionnelle

# Surface de pointe par defaut (10 cm2)
DEFAULT_TIP_AREA_CM2 = 10.0

# Facteur de conversion kgf -> daN (pre-calcule via Pint)
# 1 kgf = 9.81 N = 0.981 daN
KGF_TO_DAN = float(Q_(1, "kgf").to("daN").magnitude)


def make_tip_area(tip_area_cm2: float = DEFAULT_TIP_AREA_CM2) -> pint.Quantity:
    """Construit la Quantity Pint pour la surface de pointe."""
    return Q_(tip_area_cm2, "cm**2")


# ──────────────────────── Detection automatique ────────────────────────

# Plages par defaut pour la detection automatique
DEFAULT_DETECTION_RANGES = {
    "qc_mpa_max": 70.0,      # si percentile <= 70 => MPa
    "qc_kg_max": 7000.0,     # si percentile <= 7000 => kg
    "qst_kn_max": 600.0,     # si percentile <= 600 => kN
    "qst_kg_max": 60000.0,   # si percentile <= 60000 => kg
    "percentile": 99.0,      # percentile utilise pour le seuil
}


def _safe_percentile(values, percentile: float) -> float:
    """Calcule un percentile en ignorant NaN et valeurs non finies."""
    clean = np.asarray(values, dtype=float)
    clean = clean[np.isfinite(clean)]
    if len(clean) == 0:
        return 0.0
    return float(np.percentile(np.abs(clean), percentile))


def detect_qc_unit(values, settings: dict = None) -> str:
    """
    Detecte l'unite de qc a partir des valeurs brutes.

    Retourne "MPa" ou "kg".
    En cas d'ambiguite, retourne "MPa" (fallback) avec un avertissement.

    Parametres
    ----------
    values : array-like
        Valeurs brutes de qc.
    settings : dict, optional
        Plages de detection personnalisees (cles : qc_mpa_max, qc_kg_max, percentile).
    """
    cfg = {**DEFAULT_DETECTION_RANGES, **(settings or {})}
    p = _safe_percentile(values, cfg["percentile"])

    if p <= cfg["qc_mpa_max"]:
        return "MPa"
    elif p <= cfg["qc_kg_max"]:
        return "kg"
    else:
        warnings.warn(
            f"Detection qc ambigue : P{cfg['percentile']:.0f} = {p:.1f}, "
            f"hors des plages MPa (<={cfg['qc_mpa_max']}) et kg (<={cfg['qc_kg_max']}). "
            f"Fallback vers MPa.",
            stacklevel=2,
        )
        return "MPa"


def detect_qst_unit(values, settings: dict = None) -> str:
    """
    Detecte l'unite de Qst a partir des valeurs brutes.

    Retourne "kN" ou "kg".
    En cas d'ambiguite, retourne "kN" (fallback) avec un avertissement.

    Parametres
    ----------
    values : array-like
        Valeurs brutes de Qst.
    settings : dict, optional
        Plages de detection personnalisees (cles : qst_kn_max, qst_kg_max, percentile).
    """
    cfg = {**DEFAULT_DETECTION_RANGES, **(settings or {})}
    p = _safe_percentile(values, cfg["percentile"])

    if p <= cfg["qst_kn_max"]:
        return "kN"
    elif p <= cfg["qst_kg_max"]:
        return "kg"
    else:
        warnings.warn(
            f"Detection Qst ambigue : P{cfg['percentile']:.0f} = {p:.1f}, "
            f"hors des plages kN (<={cfg['qst_kn_max']}) et kg (<={cfg['qst_kg_max']}). "
            f"Fallback vers kN.",
            stacklevel=2,
        )
        return "kN"


# ──────────────────────── Conversions vers interne ────────────────────────

def qc_to_internal(values, unit: str, tip_area_cm2: float = DEFAULT_TIP_AREA_CM2):
    """
    Convertit les valeurs brutes de qc vers l'unite interne DaN/m2.

    Parametres
    ----------
    values : array-like
        Valeurs brutes de qc.
    unit : str
        "MPa" ou "kg" (interprete comme kgf).
    tip_area_cm2 : float
        Surface de pointe en cm2 (necessaire pour la conversion kg -> pression).

    Retourne
    --------
    numpy.ndarray
        Magnitudes en DaN/m2 (float).
    """
    arr = np.asarray(values, dtype=float)

    if unit == "MPa":
        # MPa -> DaN/m2
        # 1 MPa = 1e6 Pa = 1e6 N/m2
        # 1 DaN = 10 N, donc 1 DaN/m2 = 10 N/m2
        # => 1 MPa = 1e6 / 10 = 1e5 DaN/m2
        factor = float((Q_(1, "MPa")).to("daN / m**2").magnitude)
        return arr * factor

    elif unit == "kg":
        # "kg" en entree = kgf (usage historique)
        # qc en kgf = force. Pression = force / surface de pointe
        # kgf -> daN : 1 kgf = 9.81 N = 0.981 daN
        # Surface : tip_area_cm2 cm2 -> m2
        tip_area_m2 = float(Q_(tip_area_cm2, "cm**2").to("m**2").magnitude)
        kgf_to_dan = float(Q_(1, "kgf").to("daN").magnitude)
        # pression en daN/m2 = (valeur_kgf * kgf_to_daN) / tip_area_m2
        return arr * kgf_to_dan / tip_area_m2

    else:
        raise ValueError(f"Unite qc inconnue : {unit!r}. Attendu 'MPa' ou 'kg'.")


def qst_to_internal(values, unit: str):
    """
    Convertit les valeurs brutes de Qst vers l'unite interne DaN.

    Parametres
    ----------
    values : array-like
        Valeurs brutes de Qst.
    unit : str
        "kN" ou "kg" (interprete comme kgf).

    Retourne
    --------
    numpy.ndarray
        Magnitudes en DaN (float).
    """
    arr = np.asarray(values, dtype=float)

    if unit == "kN":
        # kN -> DaN : 1 kN = 1000 N = 100 DaN
        factor = float(Q_(1, "kN").to("daN").magnitude)
        return arr * factor

    elif unit == "kg":
        # "kg" en entree = kgf
        # 1 kgf = 9.81 N = 0.981 daN
        factor = float(Q_(1, "kgf").to("daN").magnitude)
        return arr * factor

    else:
        raise ValueError(f"Unite Qst inconnue : {unit!r}. Attendu 'kN' ou 'kg'.")


# ──────────────────────── Conversions interne -> graphique ────────────────────────

# Paires de sortie graphique supportees
PLOT_PAIRS = {
    "MPa_kN": {
        "label": "MPa / kN",
        "qc_label": "qc [MPa]",
        "qst_label": "Qst [kN]",
    },
    "kg_kg": {
        "label": "kg/cm\u00b2 / kg",
        "qc_label": "qc [kg/cm\u00b2]",
        "qst_label": "Qst [kgf]",
    },
}

DEFAULT_PLOT_PAIR = "MPa_kN"


def internal_to_plot(qc_dan_m2, qst_dan, pair: str = DEFAULT_PLOT_PAIR,
                     tip_area_cm2: float = DEFAULT_TIP_AREA_CM2):
    """
    Convertit les valeurs internes (DaN/m2, DaN) vers les unites graphiques.

    Parametres
    ----------
    qc_dan_m2 : array-like
        qc en DaN/m2.
    qst_dan : array-like
        Qst en DaN.
    pair : str
        "MPa_kN" ou "kg_kg".
    tip_area_cm2 : float
        Surface de pointe en cm2 (pour reconversion vers kg/cm2).

    Retourne
    --------
    tuple (qc_plot, qst_plot, qc_label, qst_label)
        qc_plot, qst_plot : numpy.ndarray de magnitudes float.
        qc_label, qst_label : str pour les labels d'axes.
    """
    qc_arr = np.asarray(qc_dan_m2, dtype=float)
    qst_arr = np.asarray(qst_dan, dtype=float)

    if pair not in PLOT_PAIRS:
        raise ValueError(f"Paire graphique inconnue : {pair!r}. "
                         f"Choix : {list(PLOT_PAIRS.keys())}")

    info = PLOT_PAIRS[pair]

    if pair == "MPa_kN":
        # DaN/m2 -> MPa
        # 1 DaN/m2 = 10 N/m2 = 10 Pa = 10e-6 MPa = 1e-5 MPa
        factor_qc = float(Q_(1, "daN / m**2").to("MPa").magnitude)
        qc_plot = qc_arr * factor_qc

        # DaN -> kN
        # 1 DaN = 10 N = 0.01 kN
        factor_qst = float(Q_(1, "daN").to("kN").magnitude)
        qst_plot = qst_arr * factor_qst

    elif pair == "kg_kg":
        # DaN/m2 -> kgf/cm2
        # Pression interne en DaN/m2. On veut kgf/cm2.
        # 1 DaN = 10 N ; 1 kgf = 9.81 N => 1 DaN = 10/9.81 kgf
        # 1 m2 = 10000 cm2
        # DaN/m2 -> kgf/cm2 = (10/9.81) / 10000 = 1/(9810) ???
        # Mieux : via Pint
        # On sait que 1 daN/m2 = X kgf/cm2
        factor_qc = float(Q_(1, "daN / m**2").to("kgf / cm**2").magnitude)
        qc_plot = qc_arr * factor_qc

        # DaN -> kgf
        factor_qst = float(Q_(1, "daN").to("kgf").magnitude)
        qst_plot = qst_arr * factor_qst

    return qc_plot, qst_plot, info["qc_label"], info["qst_label"]


# ──────────────────────── Conversion inverse : interne -> raw ────────────────────────

def internal_qc_to_raw(qc_dan_m2, unit: str, tip_area_cm2: float = DEFAULT_TIP_AREA_CM2):
    """
    Reconvertit des valeurs internes qc (DaN/m2) vers l'unite brute.

    Utilise pour retrouver les valeurs raw a partir de l'interne.
    """
    arr = np.asarray(qc_dan_m2, dtype=float)

    if unit == "MPa":
        factor = float(Q_(1, "daN / m**2").to("MPa").magnitude)
        return arr * factor

    elif unit == "kg":
        # Inverse de qc_to_internal pour "kg"
        tip_area_m2 = float(Q_(tip_area_cm2, "cm**2").to("m**2").magnitude)
        dan_to_kgf = float(Q_(1, "daN").to("kgf").magnitude)
        # raw_kgf = (qc_dan_m2 * tip_area_m2) / kgf_to_dan
        # = qc_dan_m2 * tip_area_m2 * dan_to_kgf
        return arr * tip_area_m2 * dan_to_kgf

    else:
        raise ValueError(f"Unite qc inconnue : {unit!r}.")


def internal_qst_to_raw(qst_dan, unit: str):
    """
    Reconvertit des valeurs internes Qst (DaN) vers l'unite brute.
    """
    arr = np.asarray(qst_dan, dtype=float)

    if unit == "kN":
        factor = float(Q_(1, "daN").to("kN").magnitude)
        return arr * factor

    elif unit == "kg":
        factor = float(Q_(1, "daN").to("kgf").magnitude)
        return arr * factor

    else:
        raise ValueError(f"Unite Qst inconnue : {unit!r}.")


# ──────────────────────── Axes / ticks pour le graphique ────────────────────────

def get_plot_axis_config(pair: str = DEFAULT_PLOT_PAIR):
    """
    Retourne la configuration des axes pour une paire graphique donnee.

    Retourne
    --------
    dict avec :
        qc_max, qst_max : limites d'axes par defaut
        qc_major, qc_minor : ticks majeurs/mineurs pour qc
        qst_major, qst_minor : ticks majeurs/mineurs pour Qst
        qc_label, qst_label : labels d'axes
    """
    if pair == "MPa_kN":
        return {
            "qc_max": 17.0,
            "qst_max": 85.0,
            "qc_major": 5,
            "qc_minor": 1,
            "qst_major": 25,
            "qst_minor": 5,
            "qc_label": PLOT_PAIRS["MPa_kN"]["qc_label"],
            "qst_label": PLOT_PAIRS["MPa_kN"]["qst_label"],
        }
    elif pair == "kg_kg":
        return {
            "qc_max": 170.0,
            "qst_max": 8500.0,
            "qc_major": 50,
            "qc_minor": 10,
            "qst_major": 2500,
            "qst_minor": 500,
            "qc_label": PLOT_PAIRS["kg_kg"]["qc_label"],
            "qst_label": PLOT_PAIRS["kg_kg"]["qst_label"],
        }
    else:
        raise ValueError(f"Paire graphique inconnue : {pair!r}")


# ──────────────────────── Detection des unites d'un fichier ────────────────────────

def detect_file_units(file_data: dict, settings: dict = None) -> dict:
    """
    Charge les donnees brutes d'un fichier CPT et detecte les unites qc et Qst.

    Parametres
    ----------
    file_data : dict
        Dictionnaire contenant au minimum 'file_path'.
    settings : dict, optional
        Section 'unites' des reglages (plages de detection).

    Retourne
    --------
    dict avec cles : 'unit_qc' ("MPa" ou "kg"), 'unit_qst' ("kN" ou "kg")
    """
    from tabular_reader import load_cpt_dataframe

    try:
        df = load_cpt_dataframe(file_data)
    except Exception:
        return {"unit_qc": "MPa", "unit_qst": "kN"}

    if df.empty or len(df.columns) < 3:
        return {"unit_qc": "MPa", "unit_qst": "kN"}

    # Recuperer les colonnes qc et qst (col 2 et 3 en base 1)
    qc_col = df.columns[1] if len(df.columns) > 1 else None
    qst_col = df.columns[2] if len(df.columns) > 2 else None

    unit_qc = "MPa"
    unit_qst = "kN"

    if qc_col is not None:
        unit_qc = detect_qc_unit(df[qc_col].dropna().values, settings)

    if qst_col is not None:
        unit_qst = detect_qst_unit(df[qst_col].dropna().values, settings)

    return {"unit_qc": unit_qc, "unit_qst": unit_qst}
