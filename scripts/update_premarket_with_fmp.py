#!/usr/bin/env python
"""Update this week's pre-market reports with live FMP data (economic + earnings)."""
from __future__ import annotations
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Load .env
from dotenv import load_dotenv
from pathlib import Path
import sys
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# Add src to path
sys.path.insert(0, str(ROOT))

from src.data.fetchers.economic_earnings import (
    fetch_pre_market_data,
    format_economic_for_pre_market,
    format_earnings_for_watchlist
)
from src.core.models import EconomicEvent, PreMarketNotes

PRE_MARKET_DIR = Path("data/pre_market")

def update_premarket(target_date: date) -> bool:
    """Fetch FMP data and update pre-market JSON for target_date."""
    path = PRE_MARKET_DIR / f"{target_date.isoformat()}.json"
    if not path.exists():
        print(f"  [WARN] No pre-market file for {target_date}")
        return False

    # Load existing
    data = json.loads(path.read_text(encoding="utf-8"))

    # Fetch live FMP data
    fmp_data = fetch_pre_market_data(target_date)
    econ_raw = fmp_data["economic_events"]
    earn_raw = fmp_data["earnings"]

    # Format for pre-market
    econ_formatted = format_economic_for_pre_market(econ_raw)
    earn_watchlist = format_earnings_for_watchlist(earn_raw)

    # Update data
    data["economic_events"] = [
        {"time": e["time"], "event": e["event"], "impact": e["impact"]}
        for e in econ_formatted
    ]
    data["earnings"] = earn_raw  # Store raw for display

    # Merge earnings into watchlist
    watchlist = data.get("watchlist_candidates", [])
    for ew in earn_watchlist:
        if ew not in str(watchlist):
            watchlist.append(ew)
    data["watchlist_candidates"] = watchlist[:15]

    # Save
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  [OK] {target_date}: {len(econ_formatted)} econ, {len(earn_raw)} earnings, {len(earn_watchlist)} watchlist")
    return True

if __name__ == "__main__":
    # This week: Mon 2026-07-13 to Fri 2026-07-17
    # (adjust if different week)
    start = date(2026, 7, 13)
    end = date(2026, 7, 17)

    print(f"Updating pre-market reports {start} to {end}")
    print("=" * 50)

    current = start
    updated = 0
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri only
            if update_premarket(current):
                updated += 1
        current += timedelta(days=1)

    print("=" * 50)
    print(f"Done. Updated {updated} pre-market reports.")