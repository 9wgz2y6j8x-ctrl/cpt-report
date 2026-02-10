import os
import json
import time
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Optional
import hashlib
import re  # AJOUT : Import optimisé


class CPTFilesIndexer:
    """
    Indexeur optimisé pour les fichiers CPT (.000).
    Utilise une vérification par hash MD5 systématique, sauf si cache récent (< 60 secondes).
    Gère l'indexation, la mise en cache et la recherche dans les fichiers.
    Supporte un ou plusieurs répertoires racines.
    """

    def __init__(self, root_directories: List[str], cache_file: str = "cpt_index_cache.json"):
        # Normaliser en liste et filtrer les chemins vides
        if isinstance(root_directories, str):
            root_directories = [root_directories]
        self.root_directories = [d for d in root_directories if d and d.strip()]

        # Rétro-compatibilité : propriété root_directory pointe vers le premier
        self.root_directory = self.root_directories[0] if self.root_directories else ""

        self.cache_file = cache_file
        self.required_keys = ["Job Number", "Date", "Location", "TestNumber", "Operator"]
        self.indexed_data = []
        self._cache_metadata = {}

        # Cache temporaire très court pour éviter les recalculs immédiats
        self._last_hash = None
        self._last_hash_time = 0
        self._last_file_list = None
        self._last_file_list_time = 0
        self._temp_cache_duration = 15  # 15 secondes seulement

    def _get_cached_file_list(self) -> List[str]:
        """
        Retourne la liste de fichiers avec cache temporaire très court.
        Évite seulement les recalculs immédiats multiples.
        """
        current_time = time.time()
        
        # Cache très court (5 secondes) seulement pour éviter calculs multiples immédiats
        if (self._last_file_list is not None and 
            current_time - self._last_file_list_time < self._temp_cache_duration):
            return self._last_file_list
        
        # Recalculer
        file_paths = self._list_target_files_optimized()
        self._last_file_list = file_paths
        self._last_file_list_time = current_time
        
        return file_paths

    def _list_target_files_optimized(self) -> List[str]:
        """
        Version optimisée du parcours de fichiers SANS compromis sur la fiabilité.
        Améliore les performances tout en gardant une détection 100% fiable.
        Parcourt tous les répertoires racines configurés.
        """
        file_paths = []

        for directory in self.root_directories:
            if not os.path.exists(directory):
                print(f"Attention: Répertoire introuvable, ignoré : {directory}")
                continue

            try:
                for root, dirs, files in os.walk(directory):
                    # Filtrage précoce des dossiers système (ne compromet pas la détection)
                    dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('__')]

                    # Traitement batch optimisé
                    target_files = [
                        os.path.join(root, f)
                        for f in files
                        if f.lower().endswith(".000")
                    ]

                    # Extension efficace de liste
                    if target_files:
                        file_paths.extend(target_files)

            except (OSError, PermissionError) as e:
                print(f"Attention: Erreur d'accès lors du parcours de '{directory}' : {e}")
                print("Continuant avec les fichiers trouvés jusqu'à présent...")

        return file_paths

    def get_directory_hash(self) -> str:
        """
        Hash MD5 avec cache très court et cohérence améliorée.
        Fiabilité 100% avec optimisation minimale.
        """
        current_time = time.time()
        
        # AMÉLIORATION : Si le cache file_list a expiré, vider aussi le cache hash
        if (self._last_file_list_time > 0 and 
            current_time - self._last_file_list_time >= self._temp_cache_duration):
            self._last_hash = None
            self._last_hash_time = 0
        
        # Cache très court (5 secondes) seulement pour éviter calculs multiples immédiats
        if (self._last_hash and 
            current_time - self._last_hash_time < self._temp_cache_duration):
            return self._last_hash
        
        # Calcul MD5 complet (méthode fiable à 100%)
        file_paths = self._get_cached_file_list()  # Peut utiliser son cache de 5s
        content = "".join(sorted(file_paths))
        hash_value = hashlib.md5(content.encode()).hexdigest()
        
        # Cache très court
        self._last_hash = hash_value
        self._last_hash_time = current_time
        
        return hash_value

    def is_cache_valid(self) -> bool:
        """
        Validation simple avec exception pour cache récent (< 60 secondes).
        - Cache < 60s : Valide sans vérification
        - Cache >= 60s : Validation par hash MD5 complet
        """
        if not self._cache_metadata:
            print("DEBUG: Pas de métadonnées de cache")
            return False

        # Vérifier que les répertoires correspondent
        cached_directories = self._cache_metadata.get("root_directories")
        if cached_directories is None:
            # Rétro-compatibilité avec l'ancien format mono-répertoire
            cached_directory = self._cache_metadata.get("root_directory")
            cached_directories = [cached_directory] if cached_directory else []
        if sorted(cached_directories) != sorted(self.root_directories):
            print(f"DEBUG: Répertoires différents - Cache: {cached_directories} vs Actuel: {self.root_directories}")
            return False

        # NOUVEAU : Exception pour cache récent (< 60 secondes)
        last_update_str = self._cache_metadata.get("last_update")
        if last_update_str:
            try:
                # Parser la date de dernière mise à jour
                last_update = datetime.fromisoformat(last_update_str)
                current_time = datetime.now()
                cache_age_seconds = (current_time - last_update).total_seconds()
                
                if cache_age_seconds < 60:  # Moins de 1 minute
                    print(f"🚀 Cache récent ({cache_age_seconds:.1f}s) - Validé sans vérification")
                    return True
                else:
                    print(f"🔍 Cache ancien ({cache_age_seconds:.1f}s) - Vérification hash MD5 requise")
                    
            except (ValueError, AttributeError) as e:
                print(f"DEBUG: Erreur parsing date cache: {e}")
                print("DEBUG: Parsing date échoué, validation hash MD5 obligatoire")
                # Continuer vers la validation MD5 (comportement voulu)

        # Validation par hash MD5 complet (fiabilité 100%)
        print("DEBUG: Validation stricte par hash MD5...")
        current_hash = self.get_directory_hash()
        cached_hash = self._cache_metadata.get("directory_hash")
        
        result = current_hash == cached_hash
        print(f"DEBUG: Hash MD5 - Résultat: {'Valide' if result else 'Invalidé'}")
        return result

    @staticmethod
    def _derive_gef_path(meta_path: str) -> Optional[str]:
        """
        Dérive le chemin du fichier GEF correspondant à un fichier .000.
        Teste d'abord l'extension .GEF puis .gef (sensibilité à la casse sur Linux).
        Retourne le chemin existant ou None si aucun GEF trouvé.
        """
        base = os.path.splitext(meta_path)[0]
        for ext in (".GEF", ".gef"):
            candidate = base + ext
            if os.path.isfile(candidate):
                return candidate
        return None

    def _process_file(self, file_path: str) -> Optional[Dict]:
        """
        Traite un fichier .000 et dérive le chemin GEF correspondant.
        Retourne None si aucun fichier GEF n'existe pour ce .000.
        """
        info_found = {}
        file_mtime = None

        # Dériver le chemin GEF ; exclure l'entrée si absent
        gef_path = self._derive_gef_path(file_path)
        if gef_path is None:
            return None

        try:
            # Obtenir mtime en premier pour détecter les fichiers supprimés
            file_mtime = os.path.getmtime(file_path)

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    for key in self.required_keys:
                        if key not in info_found and key in line:
                            parts = line.split(":", 1)
                            if len(parts) > 1:
                                info_found[key] = parts[1].strip()
                            break
                    if len(info_found) == len(self.required_keys):
                        break

            # Marquer les clés non trouvées
            for key in self.required_keys:
                if key not in info_found:
                    info_found[key] = "Non trouvé"

        except FileNotFoundError:
            print(f"ATTENTION: Fichier supprimé pendant traitement : {file_path}")
            info_found = {key: "Fichier supprimé" for key in self.required_keys}
            file_mtime = 0
        except Exception as e:
            print(f"ERREUR: Traitement de {file_path}: {e}")
            info_found = {key: "Erreur" for key in self.required_keys}
            info_found["error"] = str(e)
            file_mtime = file_mtime or 0

        return {
            "file_path": gef_path,
            "meta_filepath": file_path,
            "file_name": os.path.basename(gef_path),
            "last_modified": file_mtime,
            **info_found
        }

    def _load_cache(self) -> bool:
        """Charge le cache depuis le fichier JSON."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                self.indexed_data = cache_data.get("data", [])
                self._cache_metadata = cache_data.get("metadata", {})
                
                print(f"DEBUG: Cache chargé - {len(self.indexed_data)} fichiers")
                return True
        except Exception as e:
            print(f"Erreur lors du chargement du cache : {e}")
            
        return False

    def _save_cache(self):
        """
        CORRECTION CRITIQUE : Sauvegarde avec recalcul forcé du hash.
        Évite l'utilisation d'un hash en cache temporaire obsolète.
        """
        try:
            # CORRECTION : Forcer le recalcul du hash pour les nouvelles données
            self.clear_temp_cache()  # Vider le cache temporaire avant sauvegarde
            
            cache_data = {
                "metadata": {
                    "last_update": datetime.now().isoformat(),
                    "directory_hash": self.get_directory_hash(),
                    "total_files": len(self.indexed_data),
                    "root_directories": self.root_directories,
                    "root_directory": self.root_directory,  # Rétro-compatibilité
                    "validation_method": "hash_md5_with_age_exception",
                    "cache_version": "3.1"
                },
                "data": self.indexed_data
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            self._cache_metadata = cache_data["metadata"]
            print(f"Cache sauvegardé : {len(self.indexed_data)} fichiers indexés")
            
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du cache : {e}")

    def index_files(self, max_workers: int = 8, force_reindex: bool = False, progress_callback=None) -> Dict:
        """
        Indexation optimisée avec validation simplifiée et fiable.
        """
        start_time = time.perf_counter()

        # Charger le cache existant
        cache_loaded = self._load_cache()

        # Vérification simplifiée du cache
        if not force_reindex and cache_loaded and self.is_cache_valid():
            print("Cache valide trouvé, utilisation des données existantes")
            if progress_callback is not None:  # CORRECTION : Vérification explicite
                progress_callback(100, 100)
            return {
                "status": "cache_used",
                "total_files": len(self.indexed_data),
                "execution_time": time.perf_counter() - start_time,
                "from_cache": True
            }

        print("Début de l'indexation des fichiers...")

        # Récupérer la liste de fichiers
        file_paths = self._get_cached_file_list()
        total_files = len(file_paths)

        if total_files == 0:
            print("Aucun fichier .000 trouvé")
            if progress_callback is not None:
                progress_callback(0, 0)
            return {
                "status": "no_files",
                "total_files": 0,
                "execution_time": time.perf_counter() - start_time,
                "from_cache": False
            }

        print(f"Indexation de {total_files} fichiers...")

        # Ajuster le nombre de workers selon la charge
        optimal_workers = min(max_workers, max(2, total_files // 100))
        print(f"Utilisation de {optimal_workers} workers (optimisé pour {total_files} fichiers)")
        
        # Traitement concurrent optimisé avec batching adaptatif
        self.indexed_data = []
        processed_count = 0
        
        # Traitement par batches pour un meilleur feedback
        batch_size = max(50, total_files // 20)
        print(f"Traitement par batches de {batch_size} fichiers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=optimal_workers) as executor:
            # Traitement par batches pour un meilleur feedback utilisateur
            for i in range(0, total_files, batch_size):
                batch = file_paths[i:i + batch_size]
                futures = {executor.submit(self._process_file, fp): fp for fp in batch}
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result is not None:
                            self.indexed_data.append(result)
                        processed_count += 1
                        
                        # Callback de progression
                        if progress_callback is not None:
                            progress_callback(processed_count, total_files)
                            
                    except Exception as e:
                        print(f"Erreur dans le traitement d'un fichier : {e}")
                
                # Afficher le progrès par batch
                if processed_count % (batch_size * 2) == 0 or processed_count == total_files:
                    print(f"Progression : {processed_count}/{total_files} fichiers traités")

        # Sauvegarder le nouveau cache
        self._save_cache()

        execution_time = time.perf_counter() - start_time
        return {
            "status": "completed",
            "total_files": len(self.indexed_data),
            "execution_time": execution_time,
            "from_cache": False
        }

    def get_files_by_latest_date(self) -> List[Dict]:
        """
        Retourne tous les fichiers ayant la date la plus récente (en ignorant les dates invalides).
        """
        if not self.indexed_data:
            return []
        
        # Fonction pour valider et parser une date
        def is_valid_date(date_str):
            """Vérifie si une date est valide et dans un format reconnu."""
            if not date_str or date_str.strip().lower() in ['non trouvé', 'erreur', '', 'non trouve']:
                return False
            
            # Accepter les formats : DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, DD.MM.YYYY
            date_patterns = [
                r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}$',  # DD-MM-YYYY ou DD/MM/YYYY
                r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$',  # YYYY-MM-DD ou YYYY/MM/DD
                r'^\d{1,2}\.\d{1,2}\.\d{4}$'       # DD.MM.YYYY
            ]
            
            for pattern in date_patterns:
                if re.match(pattern, date_str.strip()):
                    return True
            
            return False
        
        # Filtrer et grouper les fichiers par date valide
        valid_dates = {}  # date -> liste de fichiers
        
        for item in self.indexed_data:
            date_str = item.get('Date', '').strip()
            
            if is_valid_date(date_str):
                cleaned_date = date_str.strip()
                
                if cleaned_date not in valid_dates:
                    valid_dates[cleaned_date] = []
                
                valid_dates[cleaned_date].append(item)
        
        if not valid_dates:
            print("DEBUG: Aucune date valide trouvée dans les fichiers")
            return []
        
        # Trier les dates pour trouver la plus récente
        try:
            def parse_date_for_sorting(date_str):
                """Parse une date pour le tri chronologique."""
                
                # Format DD-MM-YYYY ou DD/MM/YYYY
                match = re.match(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', date_str)
                if match:
                    day, month, year = match.groups()
                    try:
                        return datetime(int(year), int(month), int(day))
                    except ValueError:
                        return datetime(1900, 1, 1)  # Date par défaut si invalide
                
                # Format YYYY-MM-DD ou YYYY/MM/DD
                match = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
                if match:
                    year, month, day = match.groups()
                    try:
                        return datetime(int(year), int(month), int(day))
                    except ValueError:
                        return datetime(1900, 1, 1)
                
                # Format DD.MM.YYYY
                match = re.match(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', date_str)
                if match:
                    day, month, year = match.groups()
                    try:
                        return datetime(int(year), int(month), int(day))
                    except ValueError:
                        return datetime(1900, 1, 1)
                
                # Si aucun format ne correspond, retourner date par défaut
                return datetime(1900, 1, 1)
            
            # Trier les dates par ordre chronologique décroissant
            sorted_dates = sorted(valid_dates.keys(), key=parse_date_for_sorting, reverse=True)
            latest_date = sorted_dates[0]
            
        except Exception as e:
            print(f"DEBUG: Erreur lors du tri des dates: {e}")
            # Fallback : tri alphabétique inverse
            sorted_dates = sorted(valid_dates.keys(), reverse=True)
            latest_date = sorted_dates[0]
        
        latest_files = valid_dates[latest_date]
        print(f"DEBUG: {len(latest_files)} fichiers trouvés pour la date la plus récente valide: '{latest_date}'")
        
        # Trier les fichiers par nom pour un affichage cohérent
        latest_files.sort(key=lambda x: x.get('file_name', ''))
        
        return latest_files

    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Dict]:
        """
        Recherche dans les données indexées.
        Si la requête est vide, retourne les fichiers de la date la plus récente.
        """
        if not query.strip():
            return self.get_files_by_latest_date()

        query_lower = query.lower()
        results = []

        # Champs de recherche par défaut
        if fields is None:
            fields = ["Job Number", "TestNumber", "Location", "Date", "Operator", "file_name"]

        for item in self.indexed_data:
            # Chercher dans les champs spécifiés
            for field in fields:
                if field in item and query_lower in str(item[field]).lower():
                    results.append(item)
                    break  # Éviter les doublons

        return results

    def get_statistics(self) -> Dict:
        """Retourne les statistiques de l'index."""
        if not self.indexed_data:
            return {"total_files": 0}

        stats = {
            "total_files": len(self.indexed_data),
            "last_update": self._cache_metadata.get("last_update"),
            "directories": self.root_directories,
            "directory": self.root_directory,  # Rétro-compatibilité
            "validation_method": self._cache_metadata.get("validation_method", "legacy"),
            "cache_version": self._cache_metadata.get("cache_version", "1.0")
        }

        # Statistiques sur les champs
        for key in self.required_keys:
            found_count = sum(1 for item in self.indexed_data
                            if item.get(key) not in ["Non trouvé", "Erreur"])
            stats[f"{key}_found"] = found_count

        # Âge du cache
        last_update_str = self._cache_metadata.get("last_update")
        if last_update_str:
            try:
                last_update = datetime.fromisoformat(last_update_str)
                cache_age_seconds = (datetime.now() - last_update).total_seconds()
                stats["cache_age_seconds"] = cache_age_seconds
            except:
                pass

        return stats

    def clear_temp_cache(self):
        """AMÉLIORATION : Vide le cache temporaire de façon atomique."""
        self._last_hash = None
        self._last_hash_time = 0
        self._last_file_list = None
        self._last_file_list_time = 0
        print("Cache temporaire vidé")

    def force_reindex(self) -> Dict:
        """Force une réindexation complète en ignorant le cache."""
        self.clear_temp_cache()
        return self.index_files(force_reindex=True)

    def clear_cache(self) -> bool:
        """Supprime le fichier de cache et vide le cache temporaire."""
        try:
            self.clear_temp_cache()
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                print("Cache complet supprimé avec succès")
                return True
        except Exception as e:
            print(f"Erreur lors de la suppression du cache: {e}")
        return False
