# CPT Report Lite

Logiciel de traitement des essais CPT (Cone Penetration Test) a partir de fichiers GEF. Application desktop avec interface graphique moderne.

## Stack technique

- **Langage :** Python 3
- **GUI :** customtkinter (wrapper moderne de Tkinter)
- **Donnees :** pandas, numpy, scipy
- **Graphiques :** matplotlib (embarque dans Tkinter)
- **Architecture :** MVP (Model-View-Presenter)

## Structure du projet

- `presenter.py` : Point d'entree principal et logique de presentation (MVP Presenter)
- `view.py` : Vue principale de l'interface graphique (AppView)
- `model.py` : Modele de donnees, gestion des fichiers et indexation (AppModel)
- `import_assistant.py` : Assistant d'import CSV/Excel
- `cpt_cleaning_view.py` : Interface de filtrage et nettoyage des donnees
- `settings_view.py` : Interface des preferences
- `cpt_files_indexer.py` : Moteur d'indexation et recherche de fichiers CPT
- `gef_reader.py` : Lecteur de fichiers GEF avec detection d'encodage
- `tabular_reader.py` : Lecteur de fichiers CSV/Excel
- `cpt_plot.py` : Configuration et rendu des graphiques CPT
- `despike_cleaning.py` : Filtre de Hampel pour suppression des valeurs aberrantes
- `settings_manager.py` : Gestion persistante des parametres
- `icons/` : Icones de l'interface

## Lancement

```bash
python presenter.py
```

## Conventions de code

- **Langue du code :** Francais (variables, commentaires, docstrings)
- **Classes :** PascalCase (`AppModel`, `RawDataManager`)
- **Methodes/fonctions :** snake_case (`add_file`, `search_cpt_files`)
- **Constantes :** UPPER_SNAKE_CASE (`ADD_OK`, `EDITABLE_FIELDS`)
- **Prive :** prefixe underscore (`_notify()`, `_lock`)
- **Docstrings :** Style NumPy avec sections "Parametres" et "Retours"
- **Type hints :** Utilises systematiquement (`Dict`, `List`, `Optional`, `Callable`)
- **Thread-safety :** Gestion explicite des verrous pour les composants partages
- **Separateurs de sections :** `# ──────── Nom de section ────────`
- **Imports :** 1) stdlib, 2) tiers, 3) locaux

## Dependances

customtkinter, pandas, numpy, scipy, matplotlib, Pillow, chardet, openpyxl

## Notes

- Pas de tests automatises ni de linter configures
- Pas de `requirements.txt` (dependances a installer manuellement)
- Les parametres sont stockes dans le dossier systeme de l'application (`~/.config/CPTReportLite/` sous Linux)
