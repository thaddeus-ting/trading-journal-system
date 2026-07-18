#!/usr/bin/env python
"""Batch process all DRC files to generate Daily Reports and Pre-Market Notes."""
from __future__ import annotations
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.parser import parse_drc_file, find_all_drc_files
from src.core.models import (
    DailyReport, OrganizedNote, ExtractedTrade, TradeDirection,
    NoteCategory, MarketBias, MarketBiasDirection, MarketBiasConfidence,
    MarketRegime, TradeStatus, PreMarketNotes, EconomicEvent
)
from src.core.extractor import extract_daily_report_fallback, generate_pre_market_fallback
from src.core.journalit_trades import generate_journalit_trades_from_report
from datetime import date, datetime
import yaml
import json

# Read settings
SETTINGS_FILE = Path("config/settings.yaml")
if SETTINGS_FILE.exists():
    settings = yaml.safe_load(SETTINGS_FILE.read_text())
else:
    settings = {}

# Output directories
DAILY_REPORTS_DIR = Path("data/daily_reports")
PRE_MARKET_DIR = Path("data/pre_market")
DAILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
PRE_MARKET_DIR.mkdir(parents=True, exist_ok=True)

# Vault path for Journalit trade files
VAULT_BASE = Path(settings.get("vault_path", "C:/Users/Thaddeus/Claude Code Test/trading-journal-system/Vaulted/!Journalit"))


def parse_date(date_str: str) -> date:
    """Parse date string in various formats."""
    for fmt in ["%Y-%m-%d", "%m%d%y", "%d%m%y", "%Y%m%d"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {date_str}")


def save_daily_report(report: DailyReport) -> Path:
    """Save daily report to JSON."""
    path = DAILY_REPORTS_DIR / f"{report.date.isoformat()}.json"

    # Create a pretty JSON with better formatting
    data = report.model_dump()
    # Add a nice header comment
    json_str = json.dumps(data, indent=2, default=str)
    path.write_text(json_str)
    return path


def save_daily_report_pretty(report: DailyReport) -> Path:
    """Save daily report as beautiful Markdown for human reading."""
    path = DAILY_REPORTS_DIR / f"{report.date.isoformat()}_report.md"

    # Category emojis
    cat_emoji = {
        "observation": "🔵",
        "decision": "🟣",
        "entry": "🟢",
        "exit": "🔴",
        "emotion": "🟠",
        "skip": "⚪"
    }

    # Bias emoji
    bias_emoji = {
        "bullish": "🟢",
        "bearish": "🔴",
        "chop": "🟡",
        "unclear": "⚪"
    }.get(report.market_bias.direction.value if report.market_bias else "unclear", "⚪")

    lines = []
    lines.append(f"# 📊 Daily Report — {report.date}")
    lines.append(f"*{report.date.strftime('%A')}, Week {report.date.isocalendar()[1]:02d}*")
    lines.append("")

    # Market Bias Card
    if report.market_bias:
        lines.append("## 🎯 Market Bias")
        lines.append("")
        bias = report.market_bias
        lines.append(f"**{bias_emoji} {bias.direction.value.title()}** • Confidence: **{bias.confidence.value.title()}** • Regime: **{bias.regime.value.upper()}**")
        if bias.key_levels:
            lines.append(f"**Key Levels:** {'  •  '.join(bias.key_levels)}")
        lines.append("")

    # Trades Summary
    if report.trades:
        lines.append("## 💰 Trades")
        lines.append("")
        for i, t in enumerate(report.trades, 1):
            dir_emoji = "🟢" if t.direction == TradeDirection.LONG else "🔴" if t.direction == TradeDirection.SHORT else "⚪"
            status = "✅ Closed" if t.outcome == TradeStatus.CLOSED else "🔄 Open"
            reason = f" — _{t.reason}_" if t.reason else ""
            lines.append(f"**{i}. {dir_emoji} {t.direction.value.upper()} {t.ticker}** @ ${t.price:,.2f} × {t.size} shares  ({status}){reason}")
            if t.exit_price:
                pnl_pct = ((t.exit_price - t.price) / t.price * 100) if t.direction == TradeDirection.LONG else ((t.price - t.exit_price) / t.price * 100)
                lines.append(f"   └─ Exit: ${t.exit_price:,.2f} @ {t.exit_timestamp} | P&L: {pnl_pct:+.1f}% | {t.exit_reason or '—'}")
        lines.append("")

    # Organized Notes (clean, no redundant ticker/key level columns)
    cat_groups = {}
    for note in report.organized_notes:
        cat = note.category.value
        if cat not in cat_groups:
            cat_groups[cat] = []
        cat_groups[cat].append(note)

    cat_order = ["entry", "exit", "decision", "observation", "emotion", "skip"]
    cat_titles = {
        "entry": "🟢 Entries",
        "exit": "🔴 Exits",
        "decision": "🟣 Decisions",
        "observation": "🔵 Observations",
        "emotion": "🟠 Emotion / Mistakes",
        "skip": "⚪ Skipped"
    }

    lines.append("## 📝 Market Notes")
    lines.append("")

    for cat in cat_order:
        if cat not in cat_groups:
            continue
        notes = cat_groups[cat]
        lines.append(f"### {cat_titles[cat]} ({len(notes)})")
        lines.append("")
        for note in notes:
            tags_str = f"  `{'` `'.join(note.tags)}`" if note.tags else ""
            lines.append(f"**{note.timestamp}**  {note.text}{tags_str}")
            if note.key_levels_mentioned:
                lines.append(f"> 🔑 {', '.join(note.key_levels_mentioned)}")
        lines.append("")

    # Highlights
    if report.highlights_for_carry_forward:
        lines.append("## 🎯 Carry-Forward Highlights")
        lines.append("")
        for h in report.highlights_for_carry_forward:
            lines.append(f"- {h}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Source: {Path(report.source_file).name}*")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def generate_journalit_trades(report: DailyReport) -> list[Path]:
    """Generate Journalit trade files from daily report trades."""
    vault_base = VAULT_BASE
    return generate_journalit_trades_from_report(report, vault_base)


def load_daily_report(target_date: date) -> DailyReport | None:
    """Load daily report from JSON."""
    path = DAILY_REPORTS_DIR / f"{target_date.isoformat()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return DailyReport.model_validate(data)


def save_pre_market(pre_market: PreMarketNotes) -> Path:
    """Save pre-market notes to JSON."""
    path = PRE_MARKET_DIR / f"{pre_market.date.isoformat()}.json"
    path.write_text(pre_market.model_dump_json(indent=2))
    return path


def get_events_for_date(target_date: date) -> list[dict]:
    """Get economic events for a specific date from static calendar."""
    events = []

    # Check static events in settings
    cal = settings.get("economic_calendar", {})
    static_events = cal.get("events_2026_q3", [])
    for e in static_events:
        if e["date"] == target_date.isoformat():
            events.append(e)

    # Add recurring events (simplified - first Friday = NFP)
    if target_date.weekday() == 4:  # Friday
        day_of_month = target_date.day
        if 1 <= day_of_month <= 7:  # First Friday
            events.append({
                "date": target_date.isoformat(),
                "time": "08:30",
                "event": "Nonfarm Payrolls",
                "impact": "HIGH"
            })

    return events


def process_single_date(target_date: date, drc_files: list[Path]):
    """Process a single date's DRC file."""
    # Find matching DRC file
    drc_file = None
    for f in drc_files:
        if target_date.isoformat() in f.name or f"DRC-{target_date.strftime('%d%m%y')}" in f.name:
            drc_file = f
            break

    if not drc_file:
        # Try exact match via filename pattern
        for f in drc_files:
            stem = f.stem
            import re
            match = re.search(r"DRC-(\d{6})", stem)
            if match:
                d_str = match.group(1)
                try:
                    f_date = datetime.strptime(d_str, "%d%m%y").date()
                    if f_date == target_date:
                        drc_file = f
                        break
                except ValueError:
                    continue

    if not drc_file:
        print(f"  No DRC file found for {target_date}")
        return False

    print(f"  Processing {drc_file.name}...")

    # Parse DRC
    raw_report = parse_drc_file(drc_file)
    if not raw_report:
        print(f"  No Market Notes content in {drc_file.name}")
        return False

    # Extract with fallback
    extracted = extract_daily_report_fallback(raw_report)

    # Build DailyReport
    organized_notes = [OrganizedNote.model_validate(n) for n in extracted["organized_notes"]]
    trades = [ExtractedTrade.model_validate(t) for t in extracted["trades"]]

    bias_data = extracted.get("market_bias", {})
    market_bias = MarketBias(
        direction=MarketBiasDirection(bias_data.get("direction", "unclear")),
        confidence=MarketBiasConfidence(bias_data.get("confidence", "low")),
        regime=MarketRegime(bias_data.get("regime", "transitional")),
        key_levels=bias_data.get("key_levels", [])
    )

    daily_report = DailyReport(
        date=target_date,
        organized_notes=organized_notes,
        trades=trades,
        highlights_for_carry_forward=extracted["highlights_for_carry_forward"],
        market_bias=market_bias,
        raw_market_notes=raw_report.raw_market_notes,
        source_file=str(drc_file)
    )

    # Save daily report
    report_path = save_daily_report(daily_report)
    print(f"    Saved Daily Report: {report_path.name}")

    # Save pretty version
    pretty_path = save_daily_report_pretty(daily_report)
    print(f"    Saved Daily Report (Pretty): {pretty_path.name}")

    # Generate Journalit trade files
    trade_files = generate_journalit_trades_from_report(daily_report, VAULT_BASE)
    if trade_files:
        print(f"    Generated {len(trade_files)} Journalit trade file(s)")

    # Generate pre-market for NEXT trading day
    next_date = target_date + timedelta(days=1)
    while next_date.weekday() >= 5:  # Skip weekends
        next_date += timedelta(days=1)

    economic_events = get_events_for_date(next_date)

    pre_market_data = generate_pre_market_fallback(daily_report, economic_events)

    events = [EconomicEvent(
        date=next_date,
        time=e["time"],
        event=e["event"],
        impact=e["impact"]
    ) for e in economic_events]

    pre_market = PreMarketNotes(
        date=next_date,
        carry_forward=pre_market_data["carry_forward"],
        economic_events=events,
        active_rules=pre_market_data["active_rules"],
        watchlist_candidates=pre_market_data["watchlist_candidates"]
    )

    pre_path = save_pre_market(pre_market)
    print(f"    Saved Pre-Market: {pre_path.name}")

    return True


def main():
    """Main entry point - process July 2026 only."""
    print("Finding all DRC files...")
    vault = Path(settings.get("vault_path", "C:/Users/Thaddeus/Claude Code Test/trading-journal-system/Vaulted/!Journalit"))
    drc_files = find_all_drc_files(vault)

    print(f"Found {len(drc_files)} DRC files")

    # Get all unique dates from DRC files
    dates = set()
    import re
    for f in drc_files:
        stem = f.stem
        match = re.search(r"DRC-(\d{6})", stem)
        if match:
            d_str = match.group(1)
            try:
                f_date = datetime.strptime(d_str, "%d%m%y").date()
                dates.add(f_date)
            except ValueError:
                continue

    # Filter for July 2026 only
    july_2026_dates = [d for d in dates if d.year == 2026 and d.month == 7]
    sorted_dates = sorted(july_2026_dates)
    print(f"Found {len(sorted_dates)} trading days in July 2026: {sorted_dates}")

    # Clear existing July data
    for target_date in sorted_dates:
        report_path = DAILY_REPORTS_DIR / f"{target_date.isoformat()}.json"
        pre_path = PRE_MARKET_DIR / f"{target_date.isoformat()}.json"
        if report_path.exists():
            report_path.unlink()
        if pre_path.exists():
            pre_path.unlink()

    # Process each date
    success_count = 0

    for target_date in sorted_dates:
        try:
            if process_single_date(target_date, drc_files):
                success_count += 1
        except Exception as e:
            print(f"  Error processing {target_date}: {e}")

    print(f"\nDone! Processed: {success_count} July 2026 days")

if __name__ == "__main__":
    main()