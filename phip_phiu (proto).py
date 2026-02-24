import math
import pandas as pd

# ============================================================
# CONSTANTES (à adapter si les valeurs VBA diffèrent)
# ============================================================
PI            = math.pi
PRECISION     = 1e-6   # seuil de convergence bisection
MAX_ITERATIONS = 1000  # garde-fou contre boucle infinie


# ============================================================
# FACTEUR DE PORTANCE Nq — Reissner / Prandtl
# ============================================================
def _nq(phi: float) -> float:
    """
    Nq(φ) = exp(2π·tan φ) · tan²(π/4 + φ/2)

    Paramètre
    ---------
    phi : angle de frottement interne [rad]
    """
    return math.exp(2 * PI * math.tan(phi)) * (math.tan(PI / 4 + phi / 2) ** 2)


# ============================================================
# FONCTIONS CIBLES (ce que les itérations cherchent à égaler)
# ============================================================
def _vbd_formule_phiu(phi: float) -> float:
    """
    Formule cible pour sols fins/intermédiaires (φ ≤ 30°).
    vbd = 1.3 · ((Nq - 1) · tan(30°)/tan(φ) + 1)

    Le terme (Nq-1)·cot(φ) est le Nc standard ; ici multiplié
    par tan(30°) ≈ 0.577 — normalisation propre à la méthode.
    """
    if phi <= 0:
        return 0.0
    nq  = _nq(phi)
    t3  = math.tan(PI / 6) / math.tan(phi)   # tan(30°) / tan(φ)
    return 1.3 * ((nq - 1) * t3 + 1)


def _vbd_formule_phip(phi: float) -> float:
    """
    Formule cible pour sols granulaires (φ > 30°), cohésion nulle.
    vbd = 1.3 · Nq(φ)
    """
    return 1.3 * _nq(phi)


# ============================================================
# BISECTION GÉNÉRIQUE (remplace la récursion VBA)
# ============================================================
def _bisection(
    target  : float,
    func,
    phi_min : float = 0.0,
    phi_max : float = PI / 2,
) -> float:
    """
    Trouve φ ∈ [phi_min, phi_max] tel que func(φ) ≈ target.

    Réplique la logique récursive VBA (PhiuIt / PhipIt) de façon
    itérative — évite les risques de dépassement de pile.
    """
    for _ in range(MAX_ITERATIONS):
        phi_mid = (phi_min + phi_max) / 2.0
        val     = func(phi_mid)

        if abs(val - target) <= PRECISION:
            return phi_mid

        if val > target:
            phi_max = phi_mid
        else:
            phi_min = phi_mid

    return (phi_min + phi_max) / 2.0   # meilleure estimation après MAX_ITERATIONS


# ============================================================
# vbd — rapport de normalisation
# ============================================================
def vbd(qc_danm2: float, contrainte_danm2: float) -> float:
    """
    Rapport normalisé résistance de pointe / contrainte effective.

    Paramètres
    ----------
    qc_danm2         : résistance de pointe corrigée [DaN/m²]
    contrainte_danm2 : contrainte effective verticale [DaN/m²]

    Retourne
    --------
    vbd = qc / σ'v0  [-]
    """
    if contrainte_danm2 == 0:
        return 0.0
    return qc_danm2 / contrainte_danm2


# ============================================================
# CALCUL DE φ — logique principale
# ============================================================
def calculer_phi(vbd_val: float) -> float:
    """
    Calcule l'angle de frottement φ [rad] à partir du rapport vbd.

    Logique (réplique exacte du VBA) :
    1. Résolution par bisection avec la formule PhiuIt (Nc+Nq)
    2. Si φ ≥ 30° → recommencer avec PhipIt (Nq seul)

    Paramètre
    ---------
    vbd_val : rapport qc / σ'v0 [-]

    Retourne
    --------
    phi [rad]
    """
    if vbd_val <= 0:
        return 0.0

    # Étape 1 : formule sols fins / intermédiaires
    phi = _bisection(vbd_val, _vbd_formule_phiu)

    # Étape 2 : bascule sur formule granulaire si φ ≥ 30°
    if phi >= PI / 6:
        phi = _bisection(vbd_val, _vbd_formule_phip)

    return phi


# ============================================================
# INTERFACE DATAFRAME — traitement vectorisé
# ============================================================
def calculer_angle_frottement(
    df                  : pd.DataFrame,
    col_qc_danm2        : str,
    col_contrainte_danm2: str,
) -> pd.DataFrame:
    """
    Calcule φ pour chaque ligne CPT du DataFrame.

    Paramètres
    ----------
    df                   : DataFrame CPT (une ligne = une profondeur)
    col_qc_danm2         : colonne qc corrigé [DaN/m²]
    col_contrainte_danm2 : colonne contrainte effective [DaN/m²]

    Retourne
    --------
    df enrichi de :
      phi_rad      – φ brut [rad]
      phi_deg_raw  – φ brut [°]              → col 7 du VBA
      phi_deg      – φ [°] avec min = 30°   → col 6 du VBA
    """
    result = df.copy()

    result["phi_rad"] = result.apply(
        lambda row: calculer_phi(
            vbd(row[col_qc_danm2], row[col_contrainte_danm2])
        ),
        axis=1,
    )

    result["phi_deg_raw"] = result["phi_rad"].apply(math.degrees)

    result["phi_deg"] = result["phi_rad"].apply(
        lambda phi: math.degrees(phi) if phi > PI / 6 else 30.0
    )

    return result
