"""
friction_angle.py

Calcul de l'angle de frottement interne a partir des essais CPT.
Refactorise depuis le prototype VBA historique (phip_phiu).

Deux angles sont produits :
  - phi_prime (phi') : angle pour sols granulaires, clampe a min 30 deg
  - phi_u           : angle brut en degres (sols fins / intermediaires)

Methode : resolution par bisection de l'equation vbd = f(phi),
avec basculement de formule selon que phi < ou >= 30 deg.
"""

import math


# ── Constantes ───────────────────────────────────────────────────────────────

PI = math.pi
PRECISION = 1e-6       # seuil de convergence bisection [rad]
MAX_ITERATIONS = 1000  # garde-fou contre boucle infinie


# ── Facteur de portance Nq (Reissner / Prandtl) ─────────────────────────────

def _nq(phi: float) -> float:
    """Nq(phi) = exp(2*pi*tan(phi)) * tan^2(pi/4 + phi/2).

    Parametre
    ---------
    phi : angle de frottement interne [rad]
    """
    return math.exp(2 * PI * math.tan(phi)) * (math.tan(PI / 4 + phi / 2) ** 2)


# ── Fonctions cibles (ce que la bisection cherche a egaler) ─────────────────

def _vbd_formule_phiu(phi: float) -> float:
    """Formule cible pour sols fins / intermediaires (phi <= 30 deg).

    vbd = 1.3 * ((Nq - 1) * tan(30 deg) / tan(phi) + 1)
    """
    if phi <= 0:
        return 0.0
    nq = _nq(phi)
    t3 = math.tan(PI / 6) / math.tan(phi)   # tan(30 deg) / tan(phi)
    return 1.3 * ((nq - 1) * t3 + 1)


def _vbd_formule_phip(phi: float) -> float:
    """Formule cible pour sols granulaires (phi > 30 deg), cohesion nulle.

    vbd = 1.3 * Nq(phi)
    """
    return 1.3 * _nq(phi)


# ── Bisection generique ─────────────────────────────────────────────────────

def _bisection(
    target: float,
    func,
    phi_min: float = 0.0,
    phi_max: float = PI / 2,
) -> float:
    """Trouve phi dans [phi_min, phi_max] tel que func(phi) ~ target.

    Replique la logique recursive VBA (PhiuIt / PhipIt) de facon
    iterative pour eviter les depassements de pile.
    """
    for _ in range(MAX_ITERATIONS):
        phi_mid = (phi_min + phi_max) / 2.0
        val = func(phi_mid)

        if abs(val - target) <= PRECISION:
            return phi_mid

        if val > target:
            phi_max = phi_mid
        else:
            phi_min = phi_mid

    return (phi_min + phi_max) / 2.0   # meilleure estimation


# ── Calcul de phi ────────────────────────────────────────────────────────────

def calculer_phi(vbd_val: float) -> float:
    """Calcule l'angle de frottement phi [rad] a partir du rapport vbd.

    Logique (replique exacte du VBA) :
      1. Resolution par bisection avec la formule PhiuIt (Nc + Nq)
      2. Si phi >= 30 deg -> recommencer avec PhipIt (Nq seul)

    Parametre
    ---------
    vbd_val : rapport qc / sigma'v0 [-]

    Retourne
    --------
    phi [rad]
    """
    if vbd_val <= 0:
        return 0.0

    # Etape 1 : formule sols fins / intermediaires
    phi = _bisection(vbd_val, _vbd_formule_phiu)

    # Etape 2 : bascule sur formule granulaire si phi >= 30 deg
    if phi >= PI / 6:
        phi = _bisection(vbd_val, _vbd_formule_phip)

    return phi


# ── Interface haut-niveau pour le rapport ────────────────────────────────────

def calculer_angles_frottement(
    qc_val: float,
    q0_val: float,
) -> tuple:
    """Calcule phi' et phi_u a partir de qc et q'0 (memes unites).

    Parametres
    ----------
    qc_val : resistance a la pointe corrigee [unite quelconque]
    q0_val : contrainte effective verticale [meme unite que qc_val]

    Retourne
    --------
    (phi_prime, phi_u) : tuple[float, float]
        phi_prime : angle clampe a min 30 deg [deg]  -> colonne 6
        phi_u     : angle brut [deg]                  -> colonne 7
        Retourne (None, None) si le calcul est impossible.
    """
    if q0_val <= 0 or qc_val <= 0:
        return (None, None)

    vbd_val = qc_val / q0_val
    phi_rad = calculer_phi(vbd_val)

    phi_u = math.degrees(phi_rad)
    phi_prime = phi_u if phi_rad > PI / 6 else 30.0

    return (phi_prime, phi_u)
