"""Fetch economic calendar and earnings data from Financial Modeling Prep API."""
from datetime import date, timedelta
from typing import Optional
import os
import requests
from pathlib import Path
import yaml

# Load settings
SETTINGS_FILE = Path("config/settings.yaml")
if SETTINGS_FILE.exists():
    settings = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8"))
else:
    settings = {}


MIN_MARKET_CAP = settings.get("earnings_min_market_cap", 50_000_000_000)


def fetch_pre_market_data(target_date: date) -> dict:
    """
    Fetch economic events and major earnings for a target date.

    Returns:
        {
            "economic_events": [{"time": "08:30", "event": "CPI", "impact": "HIGH", ...}],
            "earnings": [{"symbol": "AAPL", "name": "Apple Inc.", "marketCap": 3000000000000, ...}]
        }
    """
    api_key = settings.get("fmp_api_key") or os.environ.get("FMP_API_KEY")
    if not api_key:
        return {"economic_events": [], "earnings": []}

    start = target_date.isoformat()
    end = (target_date + timedelta(days=1)).isoformat()

    results = {"economic_events": [], "earnings": []}

    # Fetch economic calendar
    try:
        resp = requests.get(
            "https://financialmodelingprep.com/api/v3/economic_calendar",
            params={"from": start, "to": end, "apikey": api_key},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            for e in data:
                # FMP returns date as "2026-07-17", time as "08:30"
                if e.get("date") == start:
                    results["economic_events"].append({
                        "time": e.get("time", "00:00"),
                        "event": e.get("event", ""),
                        "impact": e.get("impact", "LOW").upper(),
                        "forecast": e.get("forecast"),
                        "prior": e.get("previous")
                    })
        elif resp.status_code == 403:
            print("[warn] FMP API key lacks access to economic calendar (legacy endpoint)")
    except Exception as e:
        print(f"[warn] FMP economic calendar failed: {e}")

    # Fetch earnings calendar
    try:
        resp = requests.get(
            "https://financialmodelingprep.com/api/v3/earning_calendar",
            params={"from": start, "to": end, "apikey": api_key},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            for e in data:
                mcap = e.get("marketCap")
                if mcap and mcap >= MIN_MARKET_CAP:
                    results["earnings"].append({
                        "symbol": e.get("symbol", ""),
                        "name": e.get("name", ""),
                        "marketCap": mcap,
                        "epsEstimated": e.get("epsEstimated"),
                        "epsActual": e.get("epsActual"),
                        "time": e.get("time", "BMO")  # BMO = Before Market Open, AMC = After Market Close
                    })
        elif resp.status_code == 403:
            print("[warn] FMP API key lacks access to earnings calendar (legacy endpoint)")
    except Exception as e:
        print(f"[warn] FMP earnings calendar failed: {e}")

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