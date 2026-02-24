from dataclasses import dataclass
from typing import Optional

# =============================================================================
# CONSTANTES PHYSIQUES
# =============================================================================

G = 9.81          # Accélération gravitationnelle [m/s²]
RHO_EAU = 1000.0  # Masse volumique de l'eau [kg/m³]

@dataclass
class ProfilSol:
    """
    Décrit les propriétés physiques du sol pour le calcul des contraintes.

    Attributes
    ----------
    masse_volumique_naturelle : float
        Masse volumique du sol AU-DESSUS de la nappe phréatique [kg/m³].
        Représente le sol en état naturel (humide mais non saturé).
        Valeurs typiques : 1700 à 2100 kg/m³.

    masse_volumique_saturee : float
        Masse volumique du sol EN DESSOUS de la nappe phréatique [kg/m³].
        Le sol est supposé totalement saturé sous la nappe.
        Valeurs typiques : 1900 à 2200 kg/m³.
        Doit être ≥ masse_volumique_naturelle.

    niveau_nappe : float | None
        Profondeur de la nappe phréatique par rapport au terrain naturel [m].
        Si None, le calcul ignore la poussée d'Archimède.
        Doit être ≥ 0 si fourni.
    """
    masse_volumique_naturelle: float
    masse_volumique_saturee:   float
    niveau_nappe:              Optional[float] = None

    def __post_init__(self):
        if self.masse_volumique_naturelle <= 0:
            raise ValueError("La masse volumique naturelle doit être positive.")
        if self.masse_volumique_saturee < self.masse_volumique_naturelle:
            raise ValueError("La masse volumique saturée doit être ≥ à la masse volumique naturelle.")
        if self.niveau_nappe is not None and self.niveau_nappe < 0:
            raise ValueError("Le niveau de nappe doit être une profondeur positive.")

def contrainte_effective_verticale(
    profondeur: float,
    sol: ProfilSol,
) -> float:
    """
    Calcule la contrainte effective verticale σ′_v à une profondeur donnée.

    Principe physique
    -----------------
    Sans nappe (ou au-dessus de la nappe)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        σ′_v = z × ρ_nat / 10 000        [kgf/cm²]

    Avec nappe (en dessous du niveau de nappe)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        1. De z=0 à z=z_nappe  →  couche non saturée, poids naturel
        2. De z=z_nappe à z    →  couche saturée, poids DÉJAUGÉ
                                   ρ′ = ρ_sat - ρ_eau (principe d'Archimède)

        σ′_v = [z_nappe × ρ_nat + (z - z_nappe) × (ρ_sat - ρ_eau)] / 10 000

    Unités et cohérence dimensionnelle
    -----------------------------------
    - z       [m]
    - ρ       [kg/m³]
    - Produit  z × ρ = [m × kg/m³] = [kg/m²]
    - 1 kg/m² = 0,0001 kgf/cm²  (car 1 m² = 10 000 cm²)
    - Donc la division par 10 000 donne directement des [kgf/cm²]

    Note : la gravité g s'annule complètement dans la conversion finale.
    On l'évite ici par souci de clarté.
    ...
    """
    if profondeur < 0:
        raise ValueError(f"La profondeur doit être positive (reçu : {profondeur} m).")

    nappe_presente = sol.niveau_nappe is not None
    sous_la_nappe  = nappe_presente and (profondeur >= sol.niveau_nappe)

    if sous_la_nappe:
        # --- Couche 1 : du terrain naturel jusqu'à la nappe (sol non saturé) ---
        z_nappe = sol.niveau_nappe
        pression_au_dessus_nappe = z_nappe * sol.masse_volumique_naturelle

        # --- Couche 2 : de la nappe jusqu'à la profondeur cible (sol déjaugé) ---
        epaisseur_sous_nappe = profondeur - z_nappe
        rho_dejauge          = sol.masse_volumique_saturee - RHO_EAU  # Archimède
        pression_sous_nappe  = epaisseur_sous_nappe * rho_dejauge

        # --- Somme et conversion [kg/m²] → [kgf/cm²] ---
        sigma_v = (pression_au_dessus_nappe + pression_sous_nappe) / 10_000

    else:
        # --- Pas de nappe (ou au-dessus) : poids naturel simple ---
        sigma_v = (profondeur * sol.masse_volumique_naturelle) / 10_000

    return sigma_v
