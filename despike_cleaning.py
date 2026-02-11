import pandas as pd
import numpy as np

def hampel_peak_filter_aggressive(df, columns=None, window_size=5, k=1.5, method='linear', multi_pass=True, verbose=True):
    """
    Filtre de Hampel plus agressif pour éliminer les gros pics persistants.

    Améliorations par rapport à la version standard :
    1. Seuil k plus bas par défaut (1.5 au lieu de 3.0)
    2. Approche multi-passes optionnelle pour éliminer les outliers persistants
    3. Diagnostics détaillés pour comprendre pourquoi certains pics ne partent pas

    Paramètres:
    -----------
    df : pandas.DataFrame
        DataFrame d'entrée contenant les données à filtrer
    columns : list, optional
        Indices des colonnes à filtrer. Default: [2, 3]
    window_size : int, optional
        Demi-taille de la fenêtre symétrique. Default: 5
    k : float, optional
        Seuil multiplicateur pour la MAD. Plus faible = plus agressif.
        Default: 1.5 (très agressif, au lieu de 3.0 standard)
    method : str, optional
        Méthode d'interpolation. Default: 'linear'
    multi_pass : bool, optional
        Effectuer plusieurs passes pour éliminer les outliers persistants. Default: True
    verbose : bool, optional
        Afficher les diagnostics détaillés. Default: True

    Retourne:
    ---------
    pandas.DataFrame
        DataFrame avec les outliers interpolés
    dict
        Statistiques détaillées du filtrage
    """

    if columns is None:
        columns = [2, 3]  # Colonnes 3 et 4 par défaut (indices 2 et 3)

    # Validation des paramètres
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Le premier argument doit être un pandas DataFrame")
    if df.empty:
        raise ValueError("Le DataFrame ne peut pas être vide")
    if window_size <= 0:
        raise ValueError("window_size doit être positif")
    if k <= 0:
        raise ValueError("k doit être positif")
    if not isinstance(columns, (list, tuple, np.ndarray)):
        raise TypeError("columns doit être une liste, tuple ou array d'indices")
    if len(columns) == 0:
        raise ValueError("La liste de colonnes ne peut pas être vide")

    max_col = max(columns)
    if max_col >= len(df.columns):
        raise ValueError(f"Index de colonne {max_col} dépasse le nombre de colonnes ({len(df.columns)})")

    min_col = min(columns)
    if min_col < 0:
        raise ValueError(f"Les indices de colonnes doivent être positifs, reçu: {min_col}")

    # Créer une copie du DataFrame
    df_result = df.copy()

    # Statistiques globales
    total_stats = {
        'outliers_par_colonne': {},
        'total_outliers': 0,
        'method_interpolation': method,
        'passes_effectuees': 0,
        'diagnostics': {}
    }

    # Diagnostics initiaux
    if verbose:
        print("=== DIAGNOSTICS INITIAUX ===")
        for col_idx in columns:
            col_name = df.columns[col_idx]
            data = df.iloc[:, col_idx].values

            print(f"\nColonne {col_idx} ({col_name}):")
            print(f"  - Min: {np.min(data):.2f}")
            print(f"  - Max: {np.max(data):.2f}")
            print(f"  - Médiane: {np.median(data):.2f}")
            print(f"  - MAD: {np.median(np.abs(data - np.median(data))):.2f}")
            print(f"  - Amplitude: {np.max(data) - np.min(data):.2f}")

    # Multi-passes pour éliminer les outliers persistants
    max_passes = 4 if multi_pass else 1

    for pass_num in range(max_passes):
        if verbose:
            print(f"\n=== PASSE {pass_num + 1} ===")

        outliers_found_this_pass = 0

        for col_idx in columns:
            col_name = df.columns[col_idx]
            data = df_result.iloc[:, col_idx].values

            # Détecter les outliers avec Hampel
            outliers_mask = _hampel_outlier_detection_enhanced(data, window_size, k, verbose=(verbose and pass_num == 0))
            n_outliers = np.sum(outliers_mask)

            if n_outliers > 0:
                if verbose:
                    print(f"Colonne {col_idx} ({col_name}): {n_outliers} outliers détectés")

                # Remplacer les outliers par NaN
                df_result.iloc[outliers_mask, col_idx] = np.nan

                # Interpoler les valeurs manquantes
                try:
                    df_result.iloc[:, col_idx] = df_result.iloc[:, col_idx].interpolate(method=method)
                except:
                    df_result.iloc[:, col_idx] = df_result.iloc[:, col_idx].interpolate(method='linear')

                outliers_found_this_pass += n_outliers

                # Mettre à jour les statistiques
                if col_name not in total_stats['outliers_par_colonne']:
                    total_stats['outliers_par_colonne'][col_name] = 0
                total_stats['outliers_par_colonne'][col_name] += n_outliers
                total_stats['total_outliers'] += n_outliers

            else:
                if verbose:
                    print(f"Colonne {col_idx} ({col_name}): aucun outlier détecté")

        total_stats['passes_effectuees'] = pass_num + 1

        # Si aucun outlier trouvé dans cette passe, arrêter
        if outliers_found_this_pass == 0:
            if verbose:
                print(f"Aucun nouvel outlier trouvé, arrêt après {pass_num + 1} passe(s)")
            break

    # Gérer les valeurs NaN restantes aux extrémités
    if df_result.isnull().any().any():
        if verbose:
            print("Remplissage des valeurs NaN restantes aux extrémités...")
        df_result = df_result.ffill().bfill()

    # Diagnostics finaux
    if verbose:
        print("\n=== DIAGNOSTICS FINAUX ===")
        for col_idx in columns:
            col_name = df.columns[col_idx]
            data_original = df.iloc[:, col_idx].values
            data_filtered = df_result.iloc[:, col_idx].values

            print(f"\nColonne {col_idx} ({col_name}):")
            print(f"  - Avant: Min={np.min(data_original):.2f}, Max={np.max(data_original):.2f}")
            print(f"  - Après: Min={np.min(data_filtered):.2f}, Max={np.max(data_filtered):.2f}")
            reduction = (np.max(data_original) - np.min(data_original)) - (np.max(data_filtered) - np.min(data_filtered))
            print(f"  - Réduction amplitude: {reduction:.2f}")

    return df_result, total_stats


def _hampel_outlier_detection_enhanced(data, window_size, k, verbose=False):
    """
    Version améliorée de la détection d'outliers Hampel avec diagnostics
    """
    n = len(data)
    outliers = np.zeros(n, dtype=bool)

    # Diagnostics pour comprendre les pics problématiques
    debug_info = []

    for i in range(n):
        # Ignorer les valeurs NaN
        if np.isnan(data[i]):
            continue

        # Bornes de la fenêtre symétrique
        start = max(0, i - window_size)
        end = min(n, i + window_size + 1)

        # Fenêtre de données
        window = data[start:end]
        window_clean = window[~np.isnan(window)]

        # S'il n'y a pas assez de données valides, passer ce point
        if len(window_clean) < 3:
            continue

        # Médiane de la fenêtre
        median = np.median(window_clean)

        # MAD (Median Absolute Deviation)
        mad = np.median(np.abs(window_clean - median))

        # Éviter division par zéro
        if mad == 0:
            mad = 1e-10

        # Score de déviation
        deviation_score = np.abs(data[i] - median) / mad

        # Test d'outlier : |xi - médiane| > k * MAD
        is_outlier = deviation_score > k

        if is_outlier:
            outliers[i] = True

        # Stocker info pour debug des gros pics
        if deviation_score > 2.0:  # Points suspects
            debug_info.append({
                'index': i,
                'value': data[i],
                'median': median,
                'mad': mad,
                'score': deviation_score,
                'is_outlier': is_outlier,
                'threshold': k
            })

    # Afficher les diagnostics pour les plus gros pics
    if verbose and len(debug_info) > 0:
        print(f"  Diagnostics détaillés ({len(debug_info)} pics suspects):")
        # Trier par score décroissant et montrer les 10 plus importants
        debug_info.sort(key=lambda x: x['score'], reverse=True)
        for info in debug_info[:10]:
            status = "OUTLIER" if info['is_outlier'] else "NON-OUTLIER"
            print(f"    Index {info['index']}: val={info['value']:.1f}, score={info['score']:.1f} → {status}")

    return outliers


# Utilisation directe avec votre DataFrame existant
print(f"DataFrame original: {len(df)} lignes")

# Appliquer le filtre de Hampel avec interpolation
df_filtered_hard, filter_stats = hampel_peak_filter_aggressive(
    df,
    columns=[1, 2],
    window_size=4,
    k=1.9,
    method='linear',
    multi_pass=True,  # Plusieurs passes
    verbose=True      # Diagnostics détaillés
)

print(f"\n=== RÉSULTATS FINAUX ===")
print(f"Outliers totaux interpolés: {filter_stats['total_outliers']}")
print(f"Passes effectuées: {filter_stats['passes_effectuees']}")
print(f"Détail par colonne: {filter_stats['outliers_par_colonne']}")
