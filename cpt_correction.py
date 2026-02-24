"""
cpt_correction.py

Correction des mesures CPT (qc corrige et Qst corrige).
Refactorise depuis le prototype VBA historique.
Les formules de calcul sont strictement identiques au code original.

Unites internes : DaN/m2 (qc) et DaN (Qst).
"""

import math
import numpy as np
import pandas as pd
from dataclasses import dataclass


# ── Constante de conversion ──────────────────────────────────────────────────

KGF_TO_DAN = 9.81 / 10.0  # 1 kgf = 9.81 N = 0.981 daN


# ── Parametres machine ───────────────────────────────────────────────────────

@dataclass
class ParamsAppareilCPT:
    """Parametres physiques de l'appareil CPT necessaires aux corrections."""
    section_pointe_m2: float        # Surface de la pointe en m2
    poids_tige_kg: float            # Poids d'une tige en kg (selon section)
    poids_tube_kg: float            # Poids d'un tube en kg (selon section)
    delta_petit_mano_kg: float      # Delta petit manometre en kg
    delta_grand_mano_kg: float      # Delta grand manometre en kg
    nb_tubes_avant_sol: int         # Nombre de tubes avant le sol


# ── Fonctions utilitaires ────────────────────────────────────────────────────

def _selectionner_delta_mano_dan(
    pression_brute_danm2: np.ndarray,
    capa_petit_mano_danm2: float,
    delta_petit_mano_kg: float,
    delta_grand_mano_kg: float,
) -> np.ndarray:
    """Selectionne le delta de manometre (en DaN) selon la pression mesuree.

    Si |pression| <= capacite du petit manometre, utilise delta_petit,
    sinon utilise delta_grand.
    """
    return np.where(
        np.abs(pression_brute_danm2) <= capa_petit_mano_danm2,
        delta_petit_mano_kg * KGF_TO_DAN,
        delta_grand_mano_kg * KGF_TO_DAN,
    )


def _compter_tiges(profondeur: pd.Series, nb_tubes_avant_sol: int) -> pd.Series:
    """Compte le nombre de tiges a chaque profondeur.

    Chaque tige fait 1 metre. A une profondeur d :
        n_tiges = nb_tubes_avant_sol + ceil(d)  pour d > 0
        n_tiges = nb_tubes_avant_sol             pour d = 0
    """
    depths = profondeur.to_numpy().astype(float)
    n = np.where(
        depths > 0,
        nb_tubes_avant_sol + np.ceil(depths).astype(int),
        nb_tubes_avant_sol,
    )
    return pd.Series(n, index=profondeur.index, name="n_tiges")


# ── Fonctions de correction ──────────────────────────────────────────────────

def calculer_qc_corrige(
    rpointe_danm2: pd.Series,
    n_tiges: pd.Series,
    params: ParamsAppareilCPT,
) -> pd.Series:
    """
    Corrige la resistance a la pointe qc.

    Formule :
        qc = (rPointe * s + poids_tiges + delta_mano) / s

    Parametres
    ----------
    rpointe_danm2 : Resistance a la pointe brute [DaN/m2]
    n_tiges       : Nombre de tiges a cette profondeur [-]
    params        : Parametres physiques de l'appareil

    Retourne
    --------
    pd.Series : qc corrige [DaN/m2]
    """
    s = params.section_pointe_m2
    capa_petit_mano_danm2 = 1000.0 * KGF_TO_DAN / s

    poids_tiges_dan = n_tiges * params.poids_tige_kg * KGF_TO_DAN

    delta_dan = _selectionner_delta_mano_dan(
        pression_brute_danm2=rpointe_danm2.to_numpy(),
        capa_petit_mano_danm2=capa_petit_mano_danm2,
        delta_petit_mano_kg=params.delta_petit_mano_kg,
        delta_grand_mano_kg=params.delta_grand_mano_kg,
    )

    qc_danm2 = (rpointe_danm2.to_numpy() * s + poids_tiges_dan + delta_dan) / s

    return pd.Series(qc_danm2, index=rpointe_danm2.index, name="qc_corrige_danm2")


def calculer_qst_corrige(
    rtotale_danm2: pd.Series,
    qc_corrige_danm2: pd.Series,
    n_tiges: pd.Series,
    params: ParamsAppareilCPT,
) -> pd.Series:
    """
    Corrige le frottement lateral total Qst.

    Formule :
        Qst = rTotale * s - qc_corrige * s + poids_tubes + delta_mano

    Note : utilise qc CORRIGE (pas rPointe brute) pour garantir la coherence
           de la partition F_totale = F_pointe + F_frottement apres corrections.

    Cas particulier :
        rTotale = 0 -> Qst = 0 (pas de mesure de frottement disponible).
        Qst clampe a 0 (physiquement impossible negatif).

    Parametres
    ----------
    rtotale_danm2    : Resistance totale brute [DaN/m2]
    qc_corrige_danm2 : qc corrige par calculer_qc_corrige() [DaN/m2]
    n_tiges          : Nombre de tiges a cette profondeur [-]
    params           : Parametres physiques de l'appareil

    Retourne
    --------
    pd.Series : Qst corrige [DaN]
    """
    s = params.section_pointe_m2
    capa_petit_mano_danm2 = 1000.0 * KGF_TO_DAN / s

    poids_tubes_dan = n_tiges * params.poids_tube_kg * KGF_TO_DAN

    delta_dan = _selectionner_delta_mano_dan(
        pression_brute_danm2=rtotale_danm2.to_numpy(),
        capa_petit_mano_danm2=capa_petit_mano_danm2,
        delta_petit_mano_kg=params.delta_petit_mano_kg,
        delta_grand_mano_kg=params.delta_grand_mano_kg,
    )

    rtotale = rtotale_danm2.to_numpy()
    qc = qc_corrige_danm2.to_numpy()

    qst_dan = rtotale * s - qc * s + poids_tubes_dan + delta_dan
    qst_dan = np.where(rtotale == 0, 0.0, qst_dan)
    qst_dan = np.maximum(qst_dan, 0.0)

    return pd.Series(qst_dan, index=rtotale_danm2.index, name="qst_corrige_dan")
