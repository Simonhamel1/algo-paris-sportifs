import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Optional


def fetch_sports(api_key: str, only_soccer: bool = True) -> List[str]:
    """Fetch sport keys from the Odds API and optionally filter for soccer.

    Args:
        api_key: The user's API key.
        only_soccer: If True, return only sports whose group is 'Soccer'.

    Returns:
        A list of sport keys.
    """
    url = "https://api.the-odds-api.com/v4/sports/"
    params = {"apiKey": api_key}
    res = requests.get(url, params=params, timeout=20)
    res.raise_for_status()
    sports = res.json()
    if only_soccer:
        return [s["key"] for s in sports if s.get("group") == "Soccer"]
    else:
        return [s["key"] for s in sports]


def fetch_odds(api_key: str, sport_key: str, region: str = "eu", markets: str = "h2h", odds_format: str = "decimal") -> List[Dict]:
    """Fetch odds for a given sport.

    Args:
        api_key: The user's API key.
        sport_key: Sport key (e.g. 'soccer_epl'). Use 'upcoming' for next 8 events across all sports.
        region: Region code(s) such as 'us', 'uk', 'eu', etc. Comma-delimit multiple.
        markets: Market(s) to query. 'h2h' returns moneyline odds which include draws for soccer.
        odds_format: 'decimal' or 'american'.

    Returns:
        A list of event objects returned by the API.
    """
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "apiKey": api_key,
        "regions": region,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    res = requests.get(url, params=params, timeout=20)
    # If the API returns a 404 or empty list when out of season, skip gracefully
    if res.status_code == 404:
        return []
    res.raise_for_status()
    return res.json()


def extract_three_way_odds(event: Dict) -> Optional[Dict[str, float]]:
    """Extract the best three-way (home/draw/away) odds from event data.

    For each outcome (home, draw, away) we pick the maximum price across all bookmakers.
    Events without all three outcomes are skipped.

    Args:
        event: An event object from the Odds API.

    Returns:
        A dict mapping 'home', 'draw', 'away' to their best odds, or None if not all present.
    """
    home_team = event.get("home_team")
    away_team = event.get("away_team")
    best_odds = {}

    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome.get("name", "")
                price = outcome.get("price")
                # Identify outcome type
                if name.lower() in {"draw", "tie", "espn", "egalité"}:
                    outcome_key = "draw"
                elif name == home_team:
                    outcome_key = "home"
                elif name == away_team:
                    outcome_key = "away"
                else:
                    # Unknown label (skip)
                    continue
                # Keep the highest price for each outcome
                try:
                    price_val = float(price)
                except (TypeError, ValueError):
                    continue
                if outcome_key not in best_odds or price_val > best_odds[outcome_key]:
                    best_odds[outcome_key] = price_val
    return best_odds if len(best_odds) == 3 else None


def find_high_odds_events(api_key: str,
                          sport_keys: List[str],
                          target: float = 3.0,
                          tol: float = 0.6,
                          region: str = "eu",
                          max_events_per_sport: int = None) -> List[Dict]:
    """Find events where home/draw/away odds are near a target value.

    Args:
        api_key: API key for the Odds API.
        sport_keys: List of sport keys to check (e.g. soccer leagues).
        target: The desired odds value (around which all three outcomes should lie).
        tol: The tolerance for deviation from the target.
        region: Region code(s) for bookmakers (e.g. 'eu').
        max_events_per_sport: Optional maximum number of events to process per sport.

    Returns:
        A sorted list of dictionaries with event and odds information, sorted by product of odds (descending).
    """
    results = []
    for sport_key in sport_keys:
        try:
            events = fetch_odds(api_key, sport_key, region=region)
        except Exception as e:
            print(f"Skipping sport {sport_key} due to error: {e}")
            continue
        if max_events_per_sport:
            events = events[:max_events_per_sport]
        for event in events:
            odds = extract_three_way_odds(event)
            if not odds:
                continue
            # Check each of the three outcomes is close to target
            if all(abs(odds[outcome] - target) <= tol for outcome in odds):
                combined_product = odds['home'] * odds['draw'] * odds['away']
                results.append({
                    'event_id': event.get('id'),
                    'sport_key': event.get('sport_key'),
                    'commence_time': event.get('commence_time'),
                    'home_team': event.get('home_team'),
                    'away_team': event.get('away_team'),
                    'best_odds': odds,
                    'combined_product': combined_product
                })
    # Sort by combined product descending to highlight highest odds events
    results.sort(key=lambda x: x['combined_product'], reverse=True)
    return results


if __name__ == "__main__":
    # Load environment variables from .env if present
    load_dotenv()

    # Example usage:
    api_key = os.getenv("THE_ODDS_API_KEY")

    if not api_key or api_key == "YOUR_API_KEY":
        print("Aucune clé API trouvée. Veuillez créer un fichier .env à la racine du projet avec:\nTHE_ODDS_API_KEY=votre_cle_api")
        raise SystemExit(1)

    # Step 1: get soccer sport keys
    try:
        soccer_sports = fetch_sports(api_key, only_soccer=True)
    except Exception as e:
        print(f"Unable to fetch sports: {e}")
        soccer_sports = []

    # Limit to a few leagues (optional) to save quota
    sample_sports = soccer_sports[:5] if soccer_sports else ["soccer_epl"]

    # Find events with odds near 3
    events = find_high_odds_events(
        api_key,
        sport_keys=sample_sports,
        target=3.0,
        tol=0.6,
        region='eu',
        max_events_per_sport=10
    )

    for ev in events[:10]:  # display first 10 matches
        print(f"{ev['home_team']} vs {ev['away_team']} (sport: {ev['sport_key']}, event_id: {ev['event_id']})")
        print(f"  Commence: {ev['commence_time']}")
        print(f"  Home: {ev['best_odds']['home']}, Draw: {ev['best_odds']['draw']}, Away: {ev['best_odds']['away']}")
        print(f"  Combined product: {ev['combined_product']:.3f}\n")
