# ── Fonctions de correction ───────────────────────────────────────────────────

def calculer_qc_corrige(
    rpointe_danm2: pd.Series,
    n_tiges:       pd.Series,
    params:        ParamsAppareilCPT,
) -> pd.Series:
    """
    Corrige la résistance à la pointe qc.

    Formule :
        qc = (rPointe × s + poids_tiges + delta_mano) / s

    Paramètres
    ----------
    rpointe_danm2 : Résistance à la pointe brute [DaN/m²]
    n_tiges       : Nombre de tiges à cette profondeur [-]
    params        : Paramètres physiques de l'appareil

    Retourne
    --------
    pd.Series : qc corrigé [DaN/m²]
    """
    s = params.section_pointe_m2
    capa_petit_mano_danm2 = 1000.0 * KGF_TO_DAN / s

    poids_tiges_dan = n_tiges * params.poids_tige_kg * KGF_TO_DAN

    delta_dan = _selectionner_delta_mano_dan(
        pression_brute_danm2  = rpointe_danm2.to_numpy(),
        capa_petit_mano_danm2 = capa_petit_mano_danm2,
        delta_petit_mano_kg   = params.delta_petit_mano_kg,
        delta_grand_mano_kg   = params.delta_grand_mano_kg,
    )

    qc_danm2 = (rpointe_danm2.to_numpy() * s + poids_tiges_dan + delta_dan) / s

    return pd.Series(qc_danm2, index=rpointe_danm2.index, name="qc_corrige_danm2")


def calculer_qst_corrige(
    rtotale_danm2:    pd.Series,
    qc_corrige_danm2: pd.Series,
    n_tiges:          pd.Series,
    params:           ParamsAppareilCPT,
) -> pd.Series:
    """
    Corrige le frottement latéral total Qst.

    Formule :
        Qst = rTotale × s − qc_corrigé × s + poids_tubes + delta_mano

    Note : utilise qc CORRIGÉ (pas rPointe brute) pour garantir la cohérence
           de la partition F_totale = F_pointe + F_frottement après corrections.

    Cas particulier :
        rTotale = 0 → Qst = 0 (pas de mesure de frottement disponible).
        Qst clampé à 0 (physiquement impossible négatif).

    Paramètres
    ----------
    rtotale_danm2    : Résistance totale brute [DaN/m²]
    qc_corrige_danm2 : qc corrigé par calculer_qc_corrige() [DaN/m²]
    n_tiges          : Nombre de tiges à cette profondeur [-]
    params           : Paramètres physiques de l'appareil

    Retourne
    --------
    pd.Series : Qst corrigé [DaN]
    """
    s = params.section_pointe_m2
    capa_petit_mano_danm2 = 1000.0 * KGF_TO_DAN / s

    poids_tubes_dan = n_tiges * params.poids_tube_kg * KGF_TO_DAN

    delta_dan = _selectionner_delta_mano_dan(
        pression_brute_danm2  = rtotale_danm2.to_numpy(),
        capa_petit_mano_danm2 = capa_petit_mano_danm2,
        delta_petit_mano_kg   = params.delta_petit_mano_kg,
        delta_grand_mano_kg   = params.delta_grand_mano_kg,
    )

    rtotale = rtotale_danm2.to_numpy()
    qc      = qc_corrige_danm2.to_numpy()

    qst_dan = rtotale * s - qc * s + poids_tubes_dan + delta_dan
    qst_dan = np.where(rtotale == 0, 0.0, qst_dan)
    qst_dan = np.maximum(qst_dan, 0.0)

    return pd.Series(qst_dan, index=rtotale_danm2.index, name="qst_corrige_dan")


# ── Fonction d'orchestration ──────────────────────────────────────────────────

def corriger_mesures_cpt(
    profondeur:    pd.Series,
    rpointe_danm2: pd.Series,
    qst_brut_dan:  pd.Series,
    params:        ParamsAppareilCPT,
) -> pd.DataFrame:
    """
    Orchestre la correction complète des mesures CPT.

    Reconstruction de rtotale
    -------------------------
        rtotale [DaN/m²] = rPointe [DaN/m²] + qst_brut [DaN] / section [m²]

    Retourne
    --------
    pd.DataFrame avec colonnes :
        profondeur_m        [m]
        n_tiges             [-]
        qc_corrige_danm2    [DaN/m²]
        qst_corrige_dan     [DaN]
    """
    rtotale_danm2 = rpointe_danm2 + qst_brut_dan / params.section_pointe_m2

    n_tiges = _compter_tiges(profondeur, params.type_appareil)

    qc_corrige  = calculer_qc_corrige(rpointe_danm2, n_tiges, params)
    qst_corrige = calculer_qst_corrige(rtotale_danm2, qc_corrige, n_tiges, params)

    return pd.DataFrame({
        "profondeur_m":     profondeur.to_numpy(),
        "n_tiges":          n_tiges.to_numpy(),
        "qc_corrige_danm2": qc_corrige.to_numpy(),
        "qst_corrige_dan":  qst_corrige.to_numpy(),
    })
