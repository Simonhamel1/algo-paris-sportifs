import requests
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional
import requests.adapters
from itertools import product as iterproduct
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
API_KEY          = 'c8e0590a71042982b6ec3a866f1d72ac'
REGIONS          = 'uk'
MARKETS          = 'h2h,spreads,totals'
TOTAL_INVESTMENT = 100        # Mise totale en €
MIN_PROFIT_PCT   = -5         # Affiche aussi les quasi-surebets (ex: -5% = margin < 105%)
TOP_N            = 30         # Nombre max de résultats affichés
MAX_WORKERS      = 8
OUTLIER_Z_SCORE  = 3.0
KELLY_FRACTION   = 0.25       # Kelly fractionné (25%)
MAX_PROFIT_PCT   = 50         # Ignore les cotes trop belles (probables erreurs)


# ─────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────
@dataclass
class Outcome:
    name: str
    price: float
    bookie: str
    point: Optional[float] = None


@dataclass
class ArbitrageResult:
    sport: str
    match: str
    commence: str
    market: str
    profit_pct: float
    profit_eur: float
    margin: float
    bets: list = field(default_factory=list)
    is_surebet: bool = False
    kelly_stakes: Optional[dict] = None


# ─────────────────────────────────────────────
# FETCHING
# ─────────────────────────────────────────────
def fetch_sports(session):
    try:
        resp = session.get(
            'https://api.the-odds-api.com/v4/sports',
            params={'apiKey': API_KEY},
            timeout=10
        )
        resp.raise_for_status()
        return [s['key'] for s in resp.json() if s.get('active')]
    except requests.RequestException as e:
        print(f"   ✗ Erreur récupération sports : {e}")
        return []


def fetch_sport_odds(sport, session):
    url = f'https://api.the-odds-api.com/v4/sports/{sport}/odds'
    params = {
        'apiKey': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': 'decimal'
    }
    try:
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        for event in data:
            event['_sport'] = sport
        return data
    except requests.RequestException:
        return []


def fetch_all_sports_odds():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=MAX_WORKERS,
        pool_maxsize=MAX_WORKERS,
        max_retries=2
    )
    session.mount('https://', adapter)

    sports = fetch_sports(session)
    if not sports:
        print("   ✗ Aucun sport actif trouvé.")
        return []

    all_events = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_sport_odds, sport, session): sport
            for sport in sports
        }
        for future in as_completed(futures):
            sport = futures[future]
            try:
                events = future.result()
                all_events.extend(events)
                if events:
                    print(f"   ✓ {sport}: {len(events)} événements")
            except Exception as e:
                print(f"   ✗ {sport}: {e}")

    return all_events


# ─────────────────────────────────────────────
# EXTRACTION DES COTES
# ─────────────────────────────────────────────
def extract_all_odds(event: dict) -> dict:
    """
    Retourne : { market_key: { outcome_key: [Outcome, ...] } }
    Un seul outcome par bookmaker par clé.
    """
    markets_data: dict = {}

    for bookie in event.get('bookmakers', []):
        bookie_key = bookie.get('key', 'unknown')

        for market in bookie.get('markets', []):
            mkey = market.get('key', 'unknown')
            if mkey not in markets_data:
                markets_data[mkey] = {}

            for outcome in market.get('outcomes', []):
                name  = outcome.get('name', '?')
                price = outcome.get('price', 0.0)
                point = outcome.get('point')
                okey  = f"{name}|{point}" if point is not None else name

                if okey not in markets_data[mkey]:
                    markets_data[mkey][okey] = []

                already = any(o.bookie == bookie_key for o in markets_data[mkey][okey])
                if not already and price > 1.0:
                    markets_data[mkey][okey].append(
                        Outcome(name=name, price=price, bookie=bookie_key, point=point)
                    )

    return markets_data


# ─────────────────────────────────────────────
# FILTRE OUTLIERS (Z-SCORE)
# ─────────────────────────────────────────────
def filter_outlier_odds(odds_per_outcome: dict) -> dict:
    filtered = {}
    for name, outcomes in odds_per_outcome.items():
        prices = [o.price for o in outcomes]
        if len(prices) < 3:
            filtered[name] = outcomes
            continue
        mean  = statistics.mean(prices)
        stdev = statistics.stdev(prices)
        if stdev == 0:
            filtered[name] = outcomes
            continue
        valid = [o for o in outcomes if abs((o.price - mean) / stdev) <= OUTLIER_Z_SCORE]
        filtered[name] = valid if valid else outcomes
    return filtered


# ─────────────────────────────────────────────
# CALCUL DE L'ARBITRAGE
# ─────────────────────────────────────────────
def best_outcome(outcomes: list) -> Outcome:
    """Retourne le bookmaker avec la meilleure cote."""
    return max(outcomes, key=lambda o: o.price)


def compute_arbitrage(event: dict, mkey: str, outcomes_dict: dict) -> Optional[ArbitrageResult]:
    """
    Calcule l'opportunité d'arbitrage pour un marché donné.
    Pour chaque outcome, on prend la meilleure cote disponible (tous bookmakers).
    margin = somme des (1/cote) — si < 1.0, c'est un surebet.
    """
    outcome_keys = list(outcomes_dict.keys())
    if len(outcome_keys) < 2:
        return None

    best_per_outcome = {okey: best_outcome(outcomes_dict[okey]) for okey in outcome_keys}

    # Marge (overround inversé)
    margin = sum(1.0 / o.price for o in best_per_outcome.values())

    profit_pct = (1.0 / margin - 1.0) * 100

    # Filtre : on ignore si hors plage
    if profit_pct < MIN_PROFIT_PCT or profit_pct > MAX_PROFIT_PCT:
        return None

    # Calcul des mises optimales
    bets = []
    kelly_stakes = {}
    for okey, outcome in best_per_outcome.items():
        stake = (TOTAL_INVESTMENT / margin) / outcome.price
        bets.append({
            'outcome': outcome.name,
            'point':   outcome.point,
            'bookie':  outcome.bookie,
            'cote':    outcome.price,
            'mise':    round(stake, 2),
            'gain':    round(stake * outcome.price, 2)
        })
        # Kelly fractionné
        p_implied = 1.0 / outcome.price
        kelly = KELLY_FRACTION * ((outcome.price - 1) * p_implied - (1 - p_implied)) / (outcome.price - 1)
        kelly_stakes[outcome.name] = round(max(kelly, 0) * TOTAL_INVESTMENT, 2)

    profit_eur = round((1.0 / margin - 1.0) * TOTAL_INVESTMENT, 2)

    # Format date
    commence_raw = event.get('commence_time', '')
    try:
        commence = datetime.fromisoformat(commence_raw.replace('Z', '+00:00')).strftime('%d/%m/%Y %H:%M')
    except Exception:
        commence = commence_raw

    return ArbitrageResult(
        sport      = event.get('_sport', '?'),
        match      = f"{event.get('home_team', '?')} vs {event.get('away_team', '?')}",
        commence   = commence,
        market     = mkey,
        profit_pct = round(profit_pct, 3),
        profit_eur = profit_eur,
        margin     = round(margin, 4),
        bets       = bets,
        is_surebet = margin < 1.0,
        kelly_stakes = kelly_stakes
    )


# ─────────────────────────────────────────────
# AFFICHAGE
# ─────────────────────────────────────────────
def display_results(results: list):
    # Trier : surebets d'abord, puis par profit décroissant
    results.sort(key=lambda r: (-int(r.is_surebet), -r.profit_pct))
    top = results[:TOP_N]

    surebets = [r for r in top if r.is_surebet]
    near     = [r for r in top if not r.is_surebet]

    print("\n" + "═" * 70)
    print(f"  🎯  RÉSULTATS — {len(results)} opportunités analysées  |  Top {TOP_N} affichés")
    print("═" * 70)

    if surebets:
        print(f"\n✅  SUREBETS CONFIRMÉS ({len(surebets)})\n" + "─" * 70)
        for r in surebets:
            _print_result(r)
    else:
        print("\n⚠️  Aucun surebet confirmé (margin < 1.0) trouvé.")

    if near:
        print(f"\n📊  QUASI-SUREBETS / VALEUR ({len(near)})\n" + "─" * 70)
        for r in near:
            _print_result(r)

    print("═" * 70)


def _print_result(r: ArbitrageResult):
    tag = "🟢 SUREBET" if r.is_surebet else "🔵 VALUE"
    print(f"\n{tag}  {r.match}")
    print(f"   Sport    : {r.sport}")
    print(f"   Marché   : {r.market}")
    print(f"   Date     : {r.commence}")
    print(f"   Marge    : {r.margin:.4f}  |  Profit : {r.profit_pct:+.3f}%  ({r.profit_eur:+.2f}€ pour {TOTAL_INVESTMENT}€)")
    for bet in r.bets:
        pt = f" @ {bet['point']}" if bet['point'] is not None else ""
        print(f"   ├─ [{bet['bookie']}]  {bet['outcome']}{pt}  →  cote {bet['cote']}  |  mise {bet['mise']}€  →  gain {bet['gain']}€")
    if r.kelly_stakes:
        ks = "  |  ".join(f"{k}: {v}€" for k, v in r.kelly_stakes.items())
        print(f"   └─ Kelly ({int(KELLY_FRACTION*100)}%) : {ks}")
    print()


# ─────────────────────────────────────────────
# POINT D'ENTRÉE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 70)
    print("  📡  ARBITRAGE SPORTIF — The-Odds-API")
    print(f"  Régions: {REGIONS}  |  Marchés: {MARKETS}  |  Mise: {TOTAL_INVESTMENT}€")
    print("═" * 70)
    print("\n🔍 Récupération des cotes en cours...\n")

    events = fetch_all_sports_odds()
    print(f"\n✅ {len(events)} événements récupérés au total.")

    if not events:
        print("❌ Aucun événement. Vérifie ta clé API ou ta connexion.")
    else:
        print("⚙️  Calcul des opportunités d'arbitrage...\n")
        results = []

        for event in events:
            markets = extract_all_odds(event)
            for mkey, outcomes_dict in markets.items():
                filtered = filter_outlier_odds(outcomes_dict)
                arb = compute_arbitrage(event, mkey, filtered)
                if arb is not None:
                    results.append(arb)

        if not results:
            print("😔 Aucune opportunité trouvée dans les plages configurées.")
            print(f"   (MIN_PROFIT_PCT={MIN_PROFIT_PCT}%, MAX_PROFIT_PCT={MAX_PROFIT_PCT}%)")
        else:
            display_results(results)