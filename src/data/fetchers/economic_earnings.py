"""Fetch economic calendar and earnings data from FMP (economic) and Alpha Vantage (earnings)."""
from datetime import date, timedelta
from typing import Optional
import os
import requests
from pathlib import Path
import yaml

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Load settings
SETTINGS_FILE = Path("config/settings.yaml")
if SETTINGS_FILE.exists():
    settings = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8"))
else:
    settings = {}


MIN_MARKET_CAP = settings.get("earnings_min_market_cap", 50_000_000_000)

# Alpha Vantage API key (free tier)
ALPHA_VANTAGE_API_KEY = settings.get("alphavantage_api_key") or os.environ.get("ALPHA_VANTAGE_API_KEY")

# Major stocks with >$50B market cap (for filtering)
MAJOR_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AVGO", "JPM",
    "LLY", "WMT", "MA", "V", "UNH", "XOM", "PG", "JNJ", "HD", "ORCL",
    "COST", "ABBV", "KO", "BAC", "ADBE", "CRM", "MRK", "CVX", "PEP", "ACN",
    "TMO", "CSCO", "LIN", "AMD", "DIS", "NFLX", "INTC", "VZ", "CMCSA", "TXN",
    "QCOM", "NEE", "PM", "BMY", "HON", "AMGN", "UNP", "LOW", "IBM", "SPGI"
]


def fetch_economic_calendar_fmp(target_date: date) -> list[dict]:
    """Fetch economic calendar from FMP."""
    api_key = settings.get("fmp_api_key") or os.environ.get("FMP_API_KEY")
    if not api_key:
        return []

    start = target_date.isoformat()
    end = (target_date + timedelta(days=1)).isoformat()

    try:
        resp = requests.get(
            "https://financialmodelingprep.com/api/v3/economic_calendar",
            params={"from": start, "to": end, "apikey": api_key},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            events = []
            for e in data:
                if e.get("date") == start:
                    events.append({
                        "time": e.get("time", "00:00"),
                        "event": e.get("event", ""),
                        "impact": e.get("impact", "LOW").upper(),
                        "forecast": e.get("forecast"),
                        "prior": e.get("previous")
                    })
            return events
        elif resp.status_code == 403:
            print("[warn] FMP API key lacks access to economic calendar (legacy endpoint)")
    except Exception as e:
        print(f"[warn] FMP economic calendar failed: {e}")
    return []


def fetch_static_economic_events(target_date: date) -> list[dict]:
    """Fetch economic events from static config in settings.yaml."""
    static_events = settings.get("economic_calendar", {}).get("events_2026_q3", [])
    events = []
    target_str = target_date.isoformat()
    for e in static_events:
        if e.get("date") == target_str:
            events.append({
                "time": e.get("time", "00:00"),
                "event": e.get("event", ""),
                "impact": e.get("impact", "LOW").upper(),
                "forecast": e.get("forecast"),
                "prior": e.get("prior")
            })
    return events


def fetch_earnings_alphavantage(target_date: date) -> list[dict]:
    """Fetch earnings calendar from Alpha Vantage (free tier)."""
    if not ALPHA_VANTAGE_API_KEY:
        return []

    date_str = target_date.isoformat()
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "EARNINGS_CALENDAR",
                "apikey": ALPHA_VANTAGE_API_KEY,
                "date": date_str
            },
            timeout=15
        )
        if resp.status_code == 200:
            # Alpha Vantage returns CSV text
            text = resp.text.strip()
            if not text or "error" in text.lower() or "information" in text.lower():
                return []

            lines = text.split('\n')
            if len(lines) < 2:
                return []

            # Parse CSV header
            import csv
            from io import StringIO
            reader = csv.DictReader(StringIO(text))
            earnings = []
            for row in reader:
                symbol = row.get("symbol", "").upper()
                # Filter by market cap >= 50B (we don't have mcap from AV, so use major tickers list)
                if symbol not in MAJOR_TICKERS:
                    continue

                # Time: "bmo" / "amc" / "time"
                time_str = row.get("time", "").upper()
                if time_str in ("BMO", "BEFORE MARKET OPEN", "PRE-MARKET"):
                    time_str = "BMO"
                elif time_str in ("AMC", "AFTER MARKET CLOSE", "POST-MARKET"):
                    time_str = "AMC"
                else:
                    time_str = "BMO"

                earnings.append({
                    "symbol": symbol,
                    "name": row.get("name", ""),
                    "marketCap": 100_000_000_000,  # Default large cap for major tickers
                    "epsEstimated": row.get("estimate") or None,
                    "epsActual": row.get("reported") or None,
                    "time": time_str
                })
            return earnings
        else:
            print(f"[warn] Alpha Vantage earnings failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[warn] Alpha Vantage earnings failed: {e}")
    return []


def fetch_static_earnings(target_date: date) -> list[dict]:
    """Fetch earnings from static config in settings.yaml."""
    static_earnings = settings.get("economic_calendar", {}).get("earnings_2026_q3", [])
    earnings = []
    target_str = target_date.isoformat()
    for e in static_earnings:
        if e.get("date") == target_str:
            earnings.append({
                "symbol": e.get("symbol", ""),
                "name": e.get("name", ""),
                "marketCap": e.get("marketCap", 100_000_000_000),
                "epsEstimated": e.get("epsEstimated"),
                "epsActual": e.get("epsActual"),
                "time": e.get("time", "BMO")
            })
    return earnings


def fetch_pre_market_data(target_date: date) -> dict:
    """
    Fetch economic events and major earnings for a target date.

    Returns:
        {
            "economic_events": [{"time": "08:30", "event": "CPI", "impact": "HIGH", ...}],
            "earnings": [{"symbol": "AAPL", "name": "Apple Inc.", "marketCap": 3000000000000, ...}]
        }
    """
    results = {"economic_events": [], "earnings": []}

    # Fetch economic calendar from FMP
    results["economic_events"] = fetch_economic_calendar_fmp(target_date)

    # Fallback to static events if FMP fails
    if not results["economic_events"]:
        results["economic_events"] = fetch_static_economic_events(target_date)

    # Fetch earnings: try Alpha Vantage (free tier) first, then static
    results["earnings"] = fetch_earnings_alphavantage(target_date)
    if not results["earnings"]:
        results["earnings"] = fetch_static_earnings(target_date)

    # Sort earnings by market cap descending
    results["earnings"].sort(key=lambda x: x.get("marketCap", 0), reverse=True)

    return results


def format_economic_for_pre_market(events: list[dict]) -> list[dict]:
    """Convert FMP economic events to PreMarketNotes format."""
    formatted = []
    for e in events:
        formatted.append({
            "time": e.get("time", "00:00"),
            "event": e.get("event", ""),
            "impact": e.get("impact", "LOW"),
            "forecast": e.get("forecast"),
            "prior": e.get("prior")
        })
    return formatted


def format_earnings_for_watchlist(earnings: list[dict]) -> list[str]:
    """Convert earnings to watchlist candidate strings."""
    watchlist = []
    for e in earnings[:10]:  # Top 10 by market cap
        symbol = e.get("symbol", "")
        time_str = e.get("time", "BMO")
        if time_str == "BMO":
            time_str = "BMO"
        elif time_str == "AMC":
            time_str = "AMC"
        else:
            time_str = time_str
        watchlist.append(f"Watch {symbol} (Earnings {time_str})")
    return watchlist


if __name__ == "__main__":
    # Test
    from datetime import date
    data = fetch_pre_market_data(date(2026, 7, 17))
    print("Economic:", data["economic_events"])
    print("Earnings:", data["earnings"])