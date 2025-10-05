# Algo Paris Sportifs

Ce projet permet d'analyser automatiquement les cotes de paris sportifs (football principalement) en utilisant The Odds API. Il identifie les matchs où les trois issues (victoire domicile, nul, victoire extérieur) ont des cotes proches d'une valeur cible, ce qui peut révéler des opportunités de value bet ou d'arbitrage.

## Fonctionnalités principales

- Récupération automatisée des cotes via The Odds API (v4)
- Filtrage des matchs selon des critères personnalisables (cote cible, tolérance)
- Export des résultats filtrés au format CSV
- Analyse et visualisation des résultats dans un notebook Jupyter (`pari-sportif.ipynb`)

## Prérequis

- Python 3.8 ou supérieur
- Un compte sur [The Odds API](https://the-odds-api.com/) pour obtenir une clé API

## Installation

1. Créez un environnement virtuel (recommandé) pas obligatoire :
	```powershell
	python -m venv .venv
	.\.venv\Scripts\Activate.ps1
	```
2. Installez les dépendances :
	```powershell
	pip install -r requirements.txt
	```

## Configuration

Completer le fichier `.env` à la racine du projet avec votre clé API :

```env
ODDS_API_KEY=VOTRE_CLE_API_ICI
```

## Utilisation

Ouvrez le notebook Jupyter `pari-sportif.ipynb` et exécutez les cellules pour :
- Charger la clé API depuis `.env`
- Récupérer et filtrer les cotes selon vos paramètres (`TARGET`, `TOL`, etc.)
- Exporter les résultats dans `data/data-paris-sportifs.csv`
- Analyser les bookmakers français ou autres critères

## Personnalisation

Dans le notebook, vous pouvez modifier :
- `SPORT_KEYS` : liste des sports à analyser (ex : `['soccer_epl']`)
- `TARGET` : valeur cible des cotes (ex : 3.0)
- `TOL` : tolérance autour de la cible (ex : 0.6)
- `REGION` : région des bookmakers (ex : 'eu')

## Remarques

- Le notebook utilise `python-dotenv` pour charger la variable d'environnement `ODDS_API_KEY` depuis le fichier `.env`.
- Si vous obtenez des erreurs réseau, vérifiez votre clé API et votre connexion internet.

## Structure du projet

- `pari-sportif.ipynb` : notebook principal d'analyse
- `requirements.txt` : dépendances Python
- `data/` : dossiers de données et exports CSV
- `.env` : fichier contenant la clé API (à ne pas partager)

## Licence

Projet à but éducatif, non destiné à encourager le jeu d'argent. Utilisez avec responsabilité.
- `region` : région des bookmakers (ex. 'eu')
- `max_events_per_sport` : limite d'événements par championnat pour économiser le quota

Remarques

- Le script utilise `python-dotenv` pour charger la variable d'environnement `THE_ODDS_API_KEY` depuis le fichier `.env`.
- Si vous obtenez des erreurs réseau, vérifiez votre clé API et votre connexion.
