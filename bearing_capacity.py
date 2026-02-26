"""
bearing_capacity.py

Calcul de la pression admissible sous semelle de fondation a partir
des resultats d'essais CPT.

Reproduit exactement les formules VBA de l'ancienne application :
  - Brinch Hansen
  - Caquot & Kerisel
  - Meyerhof
  - De Beer adapte (methode INISMa / Sanglerat)

Toutes les fonctions internes travaillent en DaN/m².
La conversion finale en kgf/cm² est faite dans
``calculer_pressions_admissibles``.

Note : g = 9.81 m/s² (valeur physique reelle). La valeur de g
s'annule dans la chaine de calcul complete (q et gamma sont
proportionnels a g, et la conversion finale divise par g), donc
le resultat en kgf/cm² est independant de g.
"""

import math
from typing import Optional, Tuple

PI = math.pi

# Acceleration gravitationnelle [m/s²]
_G = 9.81


# ──────── Fonctions auxiliaires (methode De Beer / INISMa) ────────

def _f_phip_phiu(phiu: float, phip: float) -> float:
    """Facteur F(phi_u, phi') de la methode de De Beer.

    Reproduit exactement la fonction VBA ``FPhipPhiu``.

    Parametres
    ----------
    phiu : angle de frottement brut [rad]
    phip : angle de frottement effectif [rad]
    """
    terme1 = (1.0 + math.sin(phip)) ** (math.tan(phiu) / math.tan(phip))
    terme2 = math.exp((PI + phip - phiu) * math.tan(phiu))
    terme3 = (1.0 + math.sin(phiu)) / (math.sin(phiu) * math.cos(phiu))
    return terme1 * terme2 * terme3


def _vpg(phiu: float) -> float:
    """Facteur Vpg de la methode de De Beer.

    Reproduit exactement la fonction VBA ``Vpg``.

    Parametre
    ---------
    phiu : angle de frottement brut [rad]
    """
    t = math.tan(phiu)
    t_half = math.tan(PI / 4 + phiu / 2)

    terme1 = (1.0 + t_half ** 2) / (1.0 + 9.0 * t ** 2)
    terme2 = (3.0 * t * t_half - 1.0) * math.exp(1.5 * PI * t)
    terme3 = 3.0 * t + t_half
    terme4 = 2.0 * math.exp(1.5 * PI * t) * (t_half ** 2)
    terme5 = -2.0 * t_half

    return (1.0 / 8.0) * (terme1 * (terme2 + terme3) + terme4 + terme5)


# ──────── Methode De Beer adaptee (INISMa) ────────

def _pression_inisma(
    profondeur: float,
    phip: float,
    phiu: float,
    qp: float,
    q0p: float,
    b: float,
    rho_sec: float,
    rho_sat: float,
    niveau_nappe: Optional[float],
) -> Tuple[float, float, float]:
    """Pression admissible selon la methode de De Beer (INISMa / Sanglerat).

    Reproduit exactement la fonction VBA ``PressionInisma``.

    Parametres
    ----------
    profondeur : profondeur [m]
    phip : angle de frottement effectif phi' [rad]
    phiu : angle de frottement brut phi_u [rad]
    qp : contrainte au niveau de la fondation [DaN/m²]
    q0p : contrainte naturelle effective [DaN/m²]
    b : largeur de semelle [m]
    rho_sec : masse volumique sol sec [kg/m³]
    rho_sat : masse volumique sol sature [kg/m³]
    niveau_nappe : profondeur de la nappe [m] ou None

    Retours
    -------
    (pression, nq, vpg_val)
        pression : pression brute [DaN/m²] (avant division par coeff securite)
        nq : facteur Nq de De Beer [-]
        vpg_val : facteur Vpg [-]
    """
    nq_val = 0.0
    vpg_val = 0.0

    # Gamma : poids volumique dejauge sous la nappe, sec au-dessus
    nappe_set = niveau_nappe is not None
    if nappe_set and profondeur > niveau_nappe:
        gamma = (rho_sat - 1000.0) * (_G / 10.0)
    else:
        gamma = rho_sec * (_G / 10.0)

    if phiu < 0.001:
        # Pas d'angle de frottement -> pression nulle
        return (0.0, nq_val, vpg_val)

    terme1 = _f_phip_phiu(phiu, phip)
    nq_val = (
        terme1 * math.tan(phip)
        * ((qp / q0p) ** (math.tan(phiu) / math.tan(phip)))
        - math.tan(phip) / math.tan(phiu)
        + 1.0
    )
    terme2 = q0p * nq_val
    vpg_val = _vpg(phiu)
    terme4 = vpg_val * gamma * b

    pression = terme2 + terme4
    return (pression, nq_val, vpg_val)


# ──────── Brinch Hansen ────────

def _brinch_hansen(
    phi: float,
    q: float,
    b: float,
    profondeur: float,
    rho_sec: float,
    rho_sat: float,
    niveau_nappe: Optional[float],
) -> float:
    """Pression admissible selon Brinch Hansen.

    Reproduit exactement la fonction VBA ``BrinchHansen``.

    Parametres
    ----------
    phi : angle de frottement [rad] (phi_u)
    q : contrainte naturelle effective [DaN/m²]
    b : largeur de semelle [m]
    profondeur : profondeur [m]
    rho_sec : masse volumique sol sec [kg/m³]
    rho_sat : masse volumique sol sature [kg/m³]
    niveau_nappe : profondeur de la nappe [m] ou None

    Retours
    -------
    float : pression brute [DaN/m²]
    """
    nq = math.exp(PI * math.tan(phi)) * (math.tan(PI / 4 + phi / 2) ** 2)
    ng = 1.5 * (nq - 1.0) * math.tan(phi)

    sous_nappe = niveau_nappe is not None and profondeur >= niveau_nappe
    if sous_nappe:
        gamma = rho_sat * (_G / 10.0)
    else:
        gamma = rho_sec * (_G / 10.0)

    return q * nq + gamma * b * ng


# ──────── Caquot & Kerisel ────────

def _caquot_kerisel(
    phi: float,
    q: float,
    b: float,
    profondeur: float,
    rho_sec: float,
    rho_sat: float,
    niveau_nappe: Optional[float],
) -> float:
    """Pression admissible selon Caquot & Kerisel.

    Reproduit exactement la fonction VBA ``CaquotKerisel``.

    Parametres
    ----------
    phi : angle de frottement [rad] (phi_u)
    q : contrainte naturelle effective [DaN/m²]
    b : largeur de semelle [m]
    profondeur : profondeur [m]
    rho_sec : masse volumique sol sec [kg/m³]
    rho_sat : masse volumique sol sature [kg/m³]
    niveau_nappe : profondeur de la nappe [m] ou None

    Retours
    -------
    float : pression brute [DaN/m²]
    """
    kp = math.tan(PI / 4 + phi / 2) ** 2
    nq = math.exp(PI * math.tan(phi)) * (math.tan(PI / 4 + phi / 2) ** 2)
    ng = (
        (math.cos(PI / 4 - phi / 2))
        / (2.0 * math.sin(PI / 4 + phi / 2) ** 2)
        * (kp - math.sin(PI / 4 - phi / 2))
    )

    sous_nappe = niveau_nappe is not None and profondeur >= niveau_nappe
    if sous_nappe:
        gamma = rho_sat * (_G / 10.0)
    else:
        gamma = rho_sec * (_G / 10.0)

    return q * nq + gamma * b * ng


# ──────── Meyerhof ────────

def _meyerhof(
    phi: float,
    q: float,
    b: float,
    profondeur: float,
    rho_sec: float,
    rho_sat: float,
    niveau_nappe: Optional[float],
) -> float:
    """Pression admissible selon Meyerhof.

    Reproduit exactement la fonction VBA ``Meyerhof``.

    Parametres
    ----------
    phi : angle de frottement [rad] (phi_u)
    q : contrainte naturelle effective [DaN/m²]
    b : largeur de semelle [m]
    profondeur : profondeur [m]
    rho_sec : masse volumique sol sec [kg/m³]
    rho_sat : masse volumique sol sature [kg/m³]
    niveau_nappe : profondeur de la nappe [m] ou None

    Retours
    -------
    float : pression brute [DaN/m²]
    """
    nq = math.exp(PI * math.tan(phi)) * (math.tan(PI / 4 + phi / 2) ** 2)
    ng = (nq - 1.0) * math.tan(1.4 * phi)

    sous_nappe = niveau_nappe is not None and profondeur >= niveau_nappe
    if sous_nappe:
        gamma = rho_sat * (_G / 10.0)
    else:
        gamma = rho_sec * (_G / 10.0)

    return q * nq + gamma * b * ng


# ──────── Fonctions Nq / Ng dediees ────────


def calculer_nq(
    methode: str,
    phiu_deg: float,
    phip_deg: float = 0.0,
    q0_kgcm2: float = 0.0,
) -> float:
    """Retourne le facteur Nq correspondant a la *methode* choisie.

    Pour les methodes Brinch Hansen, Caquot-Kerisel et Meyerhof la
    formule classique Nq(phi_u) est utilisee.
    Pour la methode De Beer (INISMa) le Nq specifique a cette methode
    est calcule (depend aussi de phi' et de q'0).

    Parametres
    ----------
    methode : nom de la methode
        "De Beer (adapté)", "Brinch Hansen", "Caquot Kérisel", "Meyerhof"
    phiu_deg : angle de frottement brut [deg]
    phip_deg : angle de frottement effectif [deg] (INISMa uniquement)
    q0_kgcm2 : contrainte naturelle effective [kgf/cm²] (INISMa uniquement)
    """
    phiu = math.radians(phiu_deg)

    if phiu < 0.001:
        return 0.0

    if methode in ("Brinch Hansen", "Caquot Kérisel", "Meyerhof"):
        return math.exp(PI * math.tan(phiu)) * (math.tan(PI / 4 + phiu / 2) ** 2)

    # De Beer (adapté) / INISMa
    phip = math.radians(phip_deg)
    if phip < 0.001:
        return 0.0

    q = q0_kgcm2 * 1000.0 * _G
    qp = q  # meme convention que calculer_pressions_admissibles
    q0p = q

    terme1 = _f_phip_phiu(phiu, phip)
    nq_val = (
        terme1 * math.tan(phip)
        * ((qp / q0p) ** (math.tan(phiu) / math.tan(phip)))
        - math.tan(phip) / math.tan(phiu)
        + 1.0
    )
    return nq_val


def calculer_ng(methode: str, phiu_deg: float) -> float:
    """Retourne le facteur Ng (gamma) correspondant a la *methode* choisie.

    Pour les methodes Brinch Hansen, Caquot-Kerisel et Meyerhof la
    formule propre a chaque methode est utilisee.
    Pour la methode De Beer (INISMa) le facteur Vpg est retourne.

    Parametres
    ----------
    methode : nom de la methode
        "De Beer (adapté)", "Brinch Hansen", "Caquot Kérisel", "Meyerhof"
    phiu_deg : angle de frottement brut [deg]
    """
    phiu = math.radians(phiu_deg)

    if phiu < 0.001:
        return 0.0

    if methode == "Brinch Hansen":
        nq = math.exp(PI * math.tan(phiu)) * (math.tan(PI / 4 + phiu / 2) ** 2)
        return 1.5 * (nq - 1.0) * math.tan(phiu)

    if methode == "Caquot Kérisel":
        kp = math.tan(PI / 4 + phiu / 2) ** 2
        return (
            math.cos(PI / 4 - phiu / 2)
            / (2.0 * math.sin(PI / 4 + phiu / 2) ** 2)
            * (kp - math.sin(PI / 4 - phiu / 2))
        )

    if methode == "Meyerhof":
        nq = math.exp(PI * math.tan(phiu)) * (math.tan(PI / 4 + phiu / 2) ** 2)
        return (nq - 1.0) * math.tan(1.4 * phiu)

    # De Beer (adapté) / INISMa -> facteur Vpg
    return _vpg(phiu)


# ──────── Interface haut-niveau ────────

# Facteur de conversion DaN/m² -> kgf/cm²
# 1 DaN = 10 N, 1 kgf = g N, 1 m² = 10000 cm²
# => 1 DaN/m² = (10/g) kgf/m² = (10/g)/10000 kgf/cm² = 10/(10000*g)
_CONV_DAN_M2_TO_KGF_CM2 = 10.0 / (10000.0 * _G)


def calculer_pressions_admissibles(
    methode: str,
    profondeur: float,
    q0_kgcm2: float,
    phip_deg: float,
    phiu_deg: float,
    largeur_semelle_1_m: float,
    largeur_semelle_2_m: float,
    coeff_securite: float,
    rho_sec: float,
    rho_sat: float,
    niveau_nappe: Optional[float],
    qc_kgcm2: float = 0.0,
) -> Tuple[float, float]:
    """Calcule les pressions admissibles padm1 et padm2.

    Reproduit exactement la boucle principale VBA ``CalculPortance``.

    Parametres
    ----------
    methode : nom de la methode de calcul
        "De Beer (adapté)", "Brinch Hansen", "Caquot Kérisel", "Meyerhof"
    profondeur : profondeur [m]
    q0_kgcm2 : contrainte naturelle effective q'0 [kgf/cm²]
    phip_deg : angle de frottement effectif phi' [deg]
    phiu_deg : angle de frottement brut phi_u [deg]
    largeur_semelle_1_m : largeur de la semelle 1 [m]
    largeur_semelle_2_m : largeur de la semelle 2 [m]
    coeff_securite : coefficient de securite (par défaut, devrait être 2)
    rho_sec : masse volumique du sol sec [kg/m³]
    rho_sat : masse volumique du sol sature [kg/m³]
    niveau_nappe : profondeur de la nappe [m] ou None
    qc_kgcm2 : resistance a la pointe corrigee [kgf/cm²] (pour le fallback)

    Retours
    -------
    (padm1, padm2) : pressions admissibles [kgf/cm²]
    """
    # Convertir les angles en radians
    phiu = math.radians(phiu_deg)
    phip = math.radians(phip_deg)

    # Convertir q'0 de kgf/cm² en DaN/m² pour les formules
    # 1 kgf/cm² = (g/10) DaN/cm² = (g/10) * 10000 DaN/m² = 1000*g DaN/m²
    q = q0_kgcm2 * 1000.0 * _G
    qp = q  # Pas de difference de niveau apres travaux

    if methode == "Brinch Hansen":
        p1 = _brinch_hansen(
            phiu, q, largeur_semelle_1_m, profondeur,
            rho_sec, rho_sat, niveau_nappe,
        )
        p2 = _brinch_hansen(
            phiu, q, largeur_semelle_2_m, profondeur,
            rho_sec, rho_sat, niveau_nappe,
        )

    elif methode == "Caquot Kérisel":
        p1 = _caquot_kerisel(
            phiu, q, largeur_semelle_1_m, profondeur,
            rho_sec, rho_sat, niveau_nappe,
        )
        p2 = _caquot_kerisel(
            phiu, q, largeur_semelle_2_m, profondeur,
            rho_sec, rho_sat, niveau_nappe,
        )

    elif methode == "Meyerhof":
        p1 = _meyerhof(
            phiu, q, largeur_semelle_1_m, profondeur,
            rho_sec, rho_sat, niveau_nappe,
        )
        p2 = _meyerhof(
            phiu, q, largeur_semelle_2_m, profondeur,
            rho_sec, rho_sat, niveau_nappe,
        )

    else:
        # "De Beer (adapté)" = methode INISMa (defaut)
        p1, _, _ = _pression_inisma(
            profondeur, phip, phiu, qp, q,
            largeur_semelle_1_m,
            rho_sec, rho_sat, niveau_nappe,
        )
        p2, _, _ = _pression_inisma(
            profondeur, phip, phiu, qp, q,
            largeur_semelle_2_m,
            rho_sec, rho_sat, niveau_nappe,
        )

    # Conversion DaN/m² -> kgf/cm² et application du coefficient de securite
    padm1 = p1 / coeff_securite * _CONV_DAN_M2_TO_KGF_CM2
    padm2 = p2 / coeff_securite * _CONV_DAN_M2_TO_KGF_CM2

    # Fallback VBA : si padm1 < 0.1, prendre qc/10
    if padm1 < 0.1:
        padm1 = qc_kgcm2 / 10.0
    # Fallback VBA : si padm2 < 0.1, prendre padm1
    if padm2 < 0.1:
        padm2 = padm1

    return (padm1, padm2)
