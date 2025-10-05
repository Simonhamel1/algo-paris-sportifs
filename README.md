# Odds Script

Ce script récupère des cotes (odds) depuis The Odds API et cherche des matchs de football dont les trois issues (victoire à domicile, nul, victoire à l'extérieur) ont des cotes proches d'une valeur cible.

Pré-requis

- Python 3.8+

Installation

1. Créez un environnement virtuel (recommandé) :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Installez les dépendances :

```powershell
pip install -r requirements.txt
```

Configuration

Créez un fichier `.env` à la racine du projet contenant :

```
THE_ODDS_API_KEY=votre_cle_api
```

Utilisation

```powershell
python "./odds_script.py"
```

Options utiles (à modifier dans le script) :
- `target` : valeur cible des cotes (ex. 3.0)
- `tol` : tolérance autour de la cible
- `region` : région des bookmakers (ex. 'eu')
- `max_events_per_sport` : limite d'événements par championnat pour économiser le quota

Remarques

- Le script utilise `python-dotenv` pour charger la variable d'environnement `THE_ODDS_API_KEY` depuis le fichier `.env`.
- Si vous obtenez des erreurs réseau, vérifiez votre clé API et votre connexion.
