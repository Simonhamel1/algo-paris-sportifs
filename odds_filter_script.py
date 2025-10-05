"""
Script to fetch and filter odds using The Odds API (v4).

This script demonstrates how to retrieve three-way moneyline odds (home/draw/away)
for one or more sports, identify events where all three outcomes have odds
around a target value, and assemble the results into a pandas DataFrame.

Key features:

  • Uses the provided API key to authenticate requests to The Odds API.
  • Requests decimal odds for the h2h (head-to-head) market and includes deep
    links (`includeLinks=true`) and source identifiers (`includeSids=true`).
  • Extracts the best available price for each outcome per bookmaker and
    selects the deepest available link in the hierarchy outcome → market →
    bookmaker → event, as recommended by The Odds API documentation.
  • Filters bookmakers whose odds for all three outcomes fall within a
    configurable tolerance of a target value (default 3.0 ± 0.6) and sorts
    the results by the product of the three odds.

Usage:

  Set the `API_KEY` below to your valid Odds API key.  Then run:

      python3 odds_filter_script.py

  By default the script will query the English Premier League (sport key
  'soccer_epl').  You can change `SPORT_KEYS` to a list of other sports
  (e.g. ['americanfootball_nfl', 'basketball_nba']) or use the endpoint
  '/v4/sports' to discover available sport keys.

Dependencies:

  pip install requests pandas

Note:
  This script is provided for local execution.  Network calls are disabled
  in the current chat environment, so it will not execute successfully here.
  Save it to your machine and run it where you have internet access.
"""

import os
from typing import Dict, List, Optional, Any, Tuple

import requests
import pandas as pd

# ============================ Configuration ============================

# Replace this with your own API key.  Do not expose real API keys publicly.
API_KEY: str = "5bb24e9151caf14c896925a570220a78"

# List of sport keys to query.  Use 'soccer_epl' for the English Premier League,
# 'upcoming' for a mix of sports, or call /v4/sports to discover others.
SPORT_KEYS: List[str] = ["soccer_epl"]

# Target odds and tolerance.  The script selects events where the home,
# draw, and away odds all lie within [TARGET - TOL, TARGET + TOL].
TARGET: float = 3.0
TOL: float = 0.6

# Region codes for bookmakers.  'eu' returns European bookmakers.
REGION: str = "eu"

# =========================== Helper Functions ===========================

def fetch_odds(
    api_key: str,
    sport_key: str,
    region: str = REGION,
    markets: str = "h2h",
    odds_format: str = "decimal",
    include_links: bool = True,
    include_sids: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch odds for a given sport from The Odds API.

    Args:
        api_key: Your Odds API key.
        sport_key: Sport identifier (e.g. 'soccer_epl').
        region: Region code(s) such as 'eu', 'us', 'uk'.  Comma separate for multiple.
        markets: Market key; 'h2h' returns three-way moneyline odds for soccer.
        odds_format: Format of the odds ('decimal' or 'american').
        include_links: Whether to request deep links (adds includeLinks=true).
        include_sids: Whether to request source IDs (adds includeSids=true).

    Returns:
        A list of event dictionaries as returned by the API.
    """
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params: Dict[str, Any] = {
        "apiKey": api_key,
        "regions": region,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    if include_links:
        params["includeLinks"] = "true"
    if include_sids:
        params["includeSids"] = "true"
    response = requests.get(url, params=params, timeout=30)
    if response.status_code == 404:
        # Sport not available or not in season
        return []
    response.raise_for_status()
    return response.json()

def _deep_link(event: Dict, bookmaker: Dict, market: Dict, outcome: Dict) -> Optional[str]:
    """Return the deepest available link following the API's hierarchy.

    The recommended order is outcome.link → market.link → bookmaker.link → event.link
    (see The Odds API deep link guide).

    Args:
        event: Event dictionary potentially containing a 'link'.
        bookmaker: Bookmaker dictionary potentially containing a 'link'.
        market: Market dictionary potentially containing a 'link'.
        outcome: Outcome dictionary potentially containing a 'link'.

    Returns:
        The first non-empty link encountered or None.
    """
    return (
        outcome.get("link")
        or market.get("link")
        or bookmaker.get("link")
        or event.get("link")
    )

def extract_bookmaker_odds(event: Dict) -> List[Dict[str, Any]]:
    """Extract best home/draw/away odds and links per bookmaker for one event.

    Args:
        event: Event dictionary from the API, containing bookmakers and markets.

    Returns:
        A list where each element corresponds to a bookmaker offering odds for all
        three outcomes.  Each element contains odds and deep links.
    """
    results: List[Dict[str, Any]] = []
    home_team = event.get("home_team")
    away_team = event.get("away_team")
    for bookmaker in event.get("bookmakers", []):
        book_key = bookmaker.get("key")
        book_title = bookmaker.get("title", book_key)
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            odds_map: Dict[str, float] = {}
            link_map: Dict[str, Optional[str]] = {}
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price")
                if name.lower() in {"draw", "tie", "egalité"}:
                    key = "draw"
                elif name == home_team:
                    key = "home"
                elif name == away_team:
                    key = "away"
                else:
                    continue
                try:
                    price_val = float(price)
                except (TypeError, ValueError):
                    continue
                odds_map[key] = price_val
                link_map[key] = _deep_link(event, bookmaker, market, outcome)
            if len(odds_map) == 3:
                results.append(
                    {
                        "event_id": event.get("id"),
                        "sport_key": event.get("sport_key"),
                        "commence_time": event.get("commence_time"),
                        "home_team": home_team,
                        "away_team": away_team,
                        "bookmaker": book_key,
                        "bookmaker_title": book_title,
                        "home_odds": odds_map["home"],
                        "draw_odds": odds_map["draw"],
                        "away_odds": odds_map["away"],
                        "home_link": link_map["home"],
                        "draw_link": link_map["draw"],
                        "away_link": link_map["away"],
                    }
                )
    return results

def find_events_with_target_odds(
    api_key: str,
    sport_keys: List[str],
    target: float = TARGET,
    tol: float = TOL,
    region: str = REGION,
) -> pd.DataFrame:
    """Retrieve and filter bookmaker offerings near a target odds value.

    Args:
        api_key: Odds API key.
        sport_keys: List of sport identifiers to query.
        target: Desired odds around which all three outcomes should cluster.
        tol: Allowed deviation from the target.
        region: Region code(s) for the bookmakers (e.g. 'eu').

    Returns:
        A pandas DataFrame with one row per (event, bookmaker) that meets the
        criteria.  Columns include the teams, odds, deep links and the product
        of the odds for sorting.
    """
    records: List[Dict[str, Any]] = []
    for sport_key in sport_keys:
        try:
            events = fetch_odds(api_key, sport_key, region=region)
        except Exception as exc:
            print(f"Error fetching odds for {sport_key}: {exc}")
            continue
        for event in events:
            for rec in extract_bookmaker_odds(event):
                if (
                    abs(rec["home_odds"] - target) <= tol
                    and abs(rec["draw_odds"] - target) <= tol
                    and abs(rec["away_odds"] - target) <= tol
                ):
                    rec["combined_product"] = (
                        rec["home_odds"] * rec["draw_odds"] * rec["away_odds"]
                    )
                    records.append(rec)
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("combined_product", ascending=False).reset_index(drop=True)
    return df

def main() -> None:
    """Entry point for the script.  Fetches odds, filters them and prints the result."""
    if not API_KEY:
        print("Aucune clé API n'est configurée. Veuillez définir API_KEY dans le script.")
        return
    if not SPORT_KEYS:
        print("Aucune clé de sport fournie. Spécifiez au moins un sport.")
        return
    df = find_events_with_target_odds(API_KEY, SPORT_KEYS, TARGET, TOL, REGION)
    if df.empty:
        print("Aucun événement correspondant aux critères n'a été trouvé.")
    else:
        with pd.option_context('display.max_columns', None):
            print(df.to_string(index=False))
        df.to_csv("filtered_odds.csv", index=False)
        print("\nLes résultats ont été enregistrés dans le fichier 'filtered_odds.csv'.")

if __name__ == "__main__":
    main()
