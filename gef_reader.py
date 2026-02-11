import pandas as pd
from pathlib import Path
from typing import Union, Dict, Tuple
import chardet


class GefFileError(Exception):
    """Exception personnalisée pour les erreurs liées au parsing des fichiers GEF."""


def detect_file_encoding(filepath: Path) -> str:
    """
    Détecte automatiquement l'encodage d'un fichier.

    Paramètres
    ----------
    filepath : Path
        Chemin vers le fichier

    Retours
    -------
    str
        Encodage détecté
    """
    try:
        with filepath.open('rb') as f:
            raw_data = f.read(10000)  # Lire les premiers 10KB pour la détection

        detected = chardet.detect(raw_data)
        encoding = detected.get('encoding', 'latin-1')

        # Vérifier que l'encodage détecté fonctionne
        with filepath.open('r', encoding=encoding, errors='replace') as f:
            f.read(1000)  # Test de lecture

        return encoding
    except Exception:
        return 'latin-1'  # Fallback sûr


def read_file_with_fallback_encoding(filepath: Path) -> Tuple[list, str]:
    """
    Lit un fichier en testant plusieurs encodages dans l'ordre de priorité.

    Paramètres
    ----------
    filepath : Path
        Chemin vers le fichier

    Retours
    -------
    Tuple[list, str]
        (lignes du fichier, encodage utilisé)
    """
    # Liste des encodages à tester par ordre de priorité
    encodings_to_try = [
        detect_file_encoding(filepath),  # Encodage auto-détecté en premier
        'utf-8',
        'latin-1',
        'cp1252',
        'iso-8859-1',
        'windows-1252'
    ]

    # Supprimer les doublons tout en conservant l'ordre
    seen = set()
    encodings_to_try = [x for x in encodings_to_try if not (x in seen or seen.add(x))]

    for encoding in encodings_to_try:
        try:
            with filepath.open('r', encoding=encoding, errors='replace') as f:
                lignes = f.readlines()
            return lignes, encoding
        except Exception:
            continue

    # Si tous les encodages échouent, forcer latin-1 avec remplacement des erreurs
    try:
        with filepath.open('r', encoding='latin-1', errors='replace') as f:
            lignes = f.readlines()
        return lignes, 'latin-1'
    except Exception as e:
        raise GefFileError(f"Impossible de lire le fichier même avec l'encodage de fallback : {e}")


def read_gef_to_dataframe(filepath: Union[str, Path]) -> pd.DataFrame:
    """
    Lit un fichier GEF-CPT et retourne les données dans un DataFrame pandas.
    Version robuste qui gère automatiquement les problèmes d'encodage.

    Paramètres
    ----------
    filepath : str ou Path
        Chemin complet du fichier GEF (.gef).

    Retours
    -------
    df : pandas.DataFrame
        Tableau contenant les données d'essai CPT avec les noms de colonnes extraits automatiquement.

    Exceptions
    ----------
    GefFileError
        Si le fichier est introuvable, mal formé, ou si les colonnes ne peuvent pas être déterminées.
    """

    filepath = Path(filepath)

    if not filepath.exists():
        raise GefFileError(f"Le fichier n'existe pas : {filepath}")

    # --- Lecture robuste avec détection d'encodage ---
    try:
        lignes, detected_encoding = read_file_with_fallback_encoding(filepath)
        print(f"📄 Fichier lu avec l'encodage : {detected_encoding}")
    except Exception as e:
        raise GefFileError(f"Impossible de lire le fichier {filepath} : {e}")

    # --- Trouver la ligne #EOH= ---
    debut_data = None
    for i, ligne in enumerate(lignes):
        if ligne.strip().startswith("#EOH"):
            debut_data = i + 1
            break
    if debut_data is None:
        raise GefFileError("Balise #EOH= introuvable dans le fichier.")

    # --- Extraire les infos colonnes (#COLUMNINFO) ---
    noms_colonnes: Dict[int, str] = {}
    for ligne in lignes:
        if ligne.startswith("#COLUMNINFO"):
            try:
                _, contenu = ligne.split("=", 1)  # Split seulement sur le premier =
                parts = [p.strip() for p in contenu.split(",")]
                index = int(parts[0]) - 1  # base 0
                nom = parts[2] if len(parts) >= 3 else f"col_{index+1}"
                noms_colonnes[index] = nom
            except Exception:
                continue  # ignorer les lignes mal formées

    if not noms_colonnes:
        raise GefFileError("Aucune information de colonne (#COLUMNINFO) trouvée.")

    # --- Charger les données numériques avec le bon encodage ---
    encodings_for_pandas = [detected_encoding, 'latin-1', 'cp1252', 'utf-8']

    df = None
    for encoding in encodings_for_pandas:
        try:
            df = pd.read_csv(
                filepath,
                sep=r"\s+",
                skiprows=debut_data,
                header=None,
                comment="#",
                engine="python",
                encoding=encoding,
                encoding_errors='replace',  # Paramètre moderne pour gérer les erreurs d'encodage
                on_bad_lines='skip'        # Ignorer les lignes mal formées
            )
            print(f"📊 Données lues avec l'encodage : {encoding}")
            break
        except Exception as e:
            continue

    if df is None:
        raise GefFileError("Impossible de charger les données tabulaires même avec les encodages de fallback.")

    # Nettoyer le DataFrame : supprimer les lignes vides et les colonnes entièrement vides
    df = df.dropna(how='all')  # Supprimer les lignes entièrement vides
    df = df.loc[:, df.notna().any()]  # Supprimer les colonnes entièrement vides

    # Vérifier cohérence colonnes
    if df.shape[1] < len(noms_colonnes):
        print(f"⚠️  Avertissement : {df.shape[1]} colonnes lues mais {len(noms_colonnes)} attendues.")
        # Ajuster les noms de colonnes aux colonnes disponibles
        noms_colonnes_ajustes = {k: v for k, v in noms_colonnes.items() if k < df.shape[1]}
        df.rename(columns=noms_colonnes_ajustes, inplace=True)
    else:
        df.rename(columns=noms_colonnes, inplace=True)

    return df


# Version alternative sans dépendance externe chardet
def read_gef_to_dataframe_simple(filepath: Union[str, Path]) -> pd.DataFrame:
    """
    Version simplifiée sans dépendance chardet.
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise GefFileError(f"Le fichier n'existe pas : {filepath}")

    # --- Lecture avec encodages multiples ---
    encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

    lignes = None
    used_encoding = None

    for encoding in encodings_to_try:
        try:
            with filepath.open('r', encoding=encoding, errors='replace') as f:
                lignes = f.readlines()
            used_encoding = encoding
            break
        except Exception:
            continue

    if lignes is None:
        raise GefFileError("Impossible de lire le fichier avec tous les encodages testés.")

    print(f"📄 Fichier lu avec l'encodage : {used_encoding}")

    # --- Trouver la ligne #EOH= ---
    debut_data = None
    for i, ligne in enumerate(lignes):
        if ligne.strip().startswith("#EOH"):
            debut_data = i + 1
            break
    if debut_data is None:
        raise GefFileError("Balise #EOH= introuvable dans le fichier.")

    # --- Extraire les infos colonnes (#COLUMNINFO) ---
    noms_colonnes: Dict[int, str] = {}
    for ligne in lignes:
        if ligne.startswith("#COLUMNINFO"):
            try:
                _, contenu = ligne.split("=", 1)
                parts = [p.strip() for p in contenu.split(",")]
                index = int(parts[0]) - 1
                nom = parts[2] if len(parts) >= 3 else f"col_{index+1}"
                noms_colonnes[index] = nom
            except Exception:
                continue

    if not noms_colonnes:
        raise GefFileError("Aucune information de colonne (#COLUMNINFO) trouvée.")

    # --- Charger les données numériques ---
    df = None
    for encoding in encodings_to_try:
        try:
            df = pd.read_csv(
                filepath,
                sep=r"\s+",
                skiprows=debut_data,
                header=None,
                comment="#",
                engine="python",
                encoding=encoding,
                encoding_errors='replace',
                on_bad_lines='skip'
            )
            break
        except Exception:
            continue

    if df is None:
        raise GefFileError("Impossible de charger les données même avec les encodages de fallback.")

    # Nettoyer et renommer
    df = df.dropna(how='all')
    df = df.loc[:, df.notna().any()]

    noms_colonnes_ajustes = {k: v for k, v in noms_colonnes.items() if k < df.shape[1]}
    df.rename(columns=noms_colonnes_ajustes, inplace=True)

    return df



# Exemple d'utilisation
if __name__ == "__main__":
    # Utiliser la version avec chardet (plus robuste)
    try:
        df = read_gef_to_dataframe(cpt_test_file_gef)
        print("✅ Données chargées avec succès")
        print(df.head())
    except GefFileError as e:
        print(f"Erreur : {e}")

    # Ou utiliser la version simple sans dépendance externe
    """try:
        df = read_gef_to_dataframe_simple(cpt_test_file_gef)
        print("✅ Données chargées avec succès (version simple)")
        print(df.head())
    except GefFileError as e:
        print(f"Erreur : {e}")
    """
