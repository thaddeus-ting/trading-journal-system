"""
Journalit Trade File Generator

Generates Journalit-format trade markdown files from daily reports.
Each trade gets its own file with YAML frontmatter and markdown body.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import uuid
import yaml

from src.core.models import DailyReport, ExtractedTrade, TradeDirection, TradeStatus
from src.core.parser import extract_tags


def infer_setup_from_notes(trade: ExtractedTrade, report: DailyReport) -> list[str]:
    """Infer setup names from note text and market context."""
    setups = []
    text = trade.reason.lower() if trade.reason else ""

    # Also check organized notes for this trade
    for note in report.organized_notes:
        if trade.ticker in note.text and trade.timestamp == note.timestamp:
            text += " " + note.text.lower()

    setup_keywords = {
        "Break of Trendline - Daily": ["trendline", "tl", "trend line"],
        "Grinder or Leaker - Intraday": ["grinder", "leaker", "slow grind"],
        "VWAP Reclaim": ["vwap reclaim", "back above vwap", "reclaim vwap"],
        "VWAP Rejection": ["vwap reject", "rejected at vwap", "vwap hold"],
        "Opening Range Breakout": ["orb", "opening range", "opening breakout"],
        "M5 Pullback": ["m5 pullback", "5min pullback", "pullback to ema"],
        "M15 Pullback": ["m15 pullback", "15min pullback"],
        "Gap Fill": ["gap fill", "fill gap", "gap down", "gap up"],
        "Gap and Go": ["gap and go", "gap up and go"],
        "Breakout": ["breakout", "break out"],
        "Breakdown": ["breakdown", "break down"],
        "Reversal": ["reversal", "reversal candle"],
        "Trend Pullback": ["trend pullback", "pullback in trend"],
        "VWAP Hold": ["vwap hold", "holding vwap"],
        "Opening Drive": ["opening drive", "drive up", "drive down"],
    }

    for setup, keywords in setup_keywords.items():
        if any(kw in text for kw in keywords):
            if setup not in setups:
                setups.append(setup)

    # Default if nothing found
    if not setups:
        if trade.direction == TradeDirection.LONG:
            setups.append("Long Setup - Intraday")
        else:
            setups.append("Short Setup - Intraday")

    return setups


def infer_mistakes_from_notes(trade: ExtractedTrade, report: DailyReport) -> list[str]:
    """Infer mistake tags from note text."""
    mistakes = []
    text = trade.reason.lower() if trade.reason else ""

    # Check organized notes for this trade
    for note in report.organized_notes:
        if trade.ticker in note.text and trade.timestamp == note.timestamp:
            text += " " + note.text.lower()

    mistake_keywords = {
        "Exit - Held Winner Past Profit Target without Technical Reasoning": [
            "held past", "held winner", "past target", "greed", "got greedy"
        ],
        "Entry - FOMO Entry": ["fomo", "chased", "chasing", "fomo entry"],
        "Entry - Early Entry": ["early", "too early", "premature"],
        "Entry - Late Entry": ["late", "too late", "chased"],
        "Exit - Early Exit": ["early exit", "exited early", "scared out"],
        "Sizing - Oversized": ["oversized", "too big", "size up"],
        "Risk - No Stop": ["no stop", "no stop loss", "without stop"],
        "Management - Moved Stop": ["moved stop", "widened stop", "gave more room"],
    }

    for mistake, keywords in mistake_keywords.items():
        if any(kw in text for kw in keywords):
            if mistake not in mistakes:
                mistakes.append(mistake)

    return mistakes


def infer_market_condition_tags(report: DailyReport) -> list[str]:
    """Infer market condition tags from market bias."""
    tags = []
    if not report.market_bias:
        return tags

    regime = report.market_bias.regime.value
    direction = report.market_bias.direction.value

    if regime == "HPTE":
        tags.append("Market Condition - High Probability Trading Environment")
    elif regime == "LPTE":
        tags.append("Market Condition - Low Probability Trading Environment")

    if direction == "bullish":
        tags.append("Market Condition - Bullish Trend Day")
    elif direction == "bearish":
        tags.append("Market Condition - Bearish Trend Day")
    elif direction == "chop":
        tags.append("Market Condition - Choppy/Range Day")

    return tags


def generate_journalit_trade_file(
    trade: ExtractedTrade,
    report: DailyReport,
    vault_base: Path,
) -> Path:
    """Generate a single Journalit trade markdown file."""

    # Determine trade date
    trade_date = report.date

    # Determine week number and folder
    week_num = trade_date.isocalendar()[1]
    week_folder = f"W{week_num:02d}"

    # Year/Quarter/Month folders
    year = trade_date.year
    quarter = (trade_date.month - 1) // 3 + 1
    month = trade_date.month

    # Trade folder path
    trade_dir = vault_base / str(year) / f"Q{quarter}" / f"{month:02d}" / week_folder / "trades"
    trade_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename: TICKER-DDMMYY-T#.md
    # T# is trade number for the day (T1, T2, etc.)
    # We need to find trade index for this ticker/date
    same_ticker_trades = [t for t in report.trades if t.ticker == trade.ticker]
    trade_idx = same_ticker_trades.index(trade) + 1 if trade in same_ticker_trades else 1

    filename = f"{trade.ticker}-{trade_date.strftime('%d%m%y')}-T{trade_idx}.md"
    filepath = trade_dir / filename

    # Build YAML frontmatter
    now_iso = datetime.now().isoformat()

    # Determine PnL and R-Multiple if closed
    pnl = 0.0
    r_multiple = 0.0
    trade_status = "OPEN"
    entries = []
    exits = []

    if trade.direction in (TradeDirection.LONG, TradeDirection.SHORT):
        # Entry
        entries.append({
            "time": datetime.combine(trade_date, datetime.strptime(trade.timestamp, "%H:%M").time()).isoformat()
            if ":" in trade.timestamp else datetime.combine(trade_date, datetime.min.time()).isoformat(),
            "price": trade.price,
            "size": trade.size,
        })
        trade_status = "OPEN"

    if trade.outcome == TradeStatus.CLOSED and trade.exit_price and trade.exit_timestamp:
        exits.append({
            "time": datetime.combine(trade_date, datetime.strptime(trade.exit_timestamp, "%H:%M").time()).isoformat()
            if ":" in trade.exit_timestamp else datetime.combine(trade_date, datetime.min.time()).isoformat(),
            "price": trade.exit_price,
            "size": trade.size,
        })
        trade_status = "CLOSED"

        # Calculate PnL
        if trade.direction == TradeDirection.LONG:
            pnl = (trade.exit_price - trade.price) * trade.size
        else:
            pnl = (trade.price - trade.exit_price) * trade.size

        # R-multiple (simplified - would need risk amount)
        # For now, use $1 per share risk as baseline
        if trade.size > 0:
            r_multiple = pnl / trade.size  # Simplified

    # Infer setup, mistakes, tags
    setups = infer_setup_from_notes(trade, report)
    mistakes = infer_mistakes_from_notes(trade, report)
    market_tags = infer_market_condition_tags(report)

    # Extract tags from notes
    note_tags = []
    for note in report.organized_notes:
        if trade.ticker in note.text and trade.timestamp == note.timestamp:
            note_tags.extend(note.tags)

    all_tags = ["Day Trade"] + market_tags + list(set(note_tags))
    if mistakes:
        all_tags.extend([f"Mistake - {m.split(' - ')[-1]}" for m in mistakes])

    # Build thesis from note text
    thesis_parts = []
    for note in report.organized_notes:
        if trade.ticker in note.text and trade.timestamp == note.timestamp:
            thesis_parts.append(note.text.strip())
    if trade.reason:
        thesis_parts.append(trade.reason.strip())
    thesis = "\n\n".join(thesis_parts) if thesis_parts else ""

    frontmatter = {
        "lastSync": now_iso,
        "type": "trade",
        "tradeStatus": trade_status,
        "direction": trade.direction.value if trade.direction != TradeDirection.EXIT else "long",  # default
        "pnl": round(pnl, 2),
        "rMultiple": round(r_multiple, 2),
        "entries": entries,
        "exits": exits,
        "commission": 0,
        "commissionType": "fixed",
        "swap": 0,
        "fees": 0,
        "setupIds": setups,
        "mistakeIds": mistakes,
        "accountIds": ["Goal: 75% WR, 2.0 PF"],
        "instrument": trade.ticker,
        "assetType": "stock",
        "setup": setups,
        "mistake": mistakes,
        "account": ["Goal: 75% WR, 2.0 PF"],
        "images": [],
        "tags": all_tags,
        "thesis": thesis + "\n" if thesis else "",
        "useDirectPnLInput": False,
        "directPnL": 0,
        "reviewed": False,
        "reviewedAt": None,
        "tradeId": f"trade_{uuid.uuid4().hex[:12]}",
        "schemaVersion": 1,
        "canonicalExecutionMigrationVersion": "2026-05-canonical-execution-v2",
    }

    # Write file
    yaml_str = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True, width=1000)
    content = f"---\n{yaml_str}---\n\n# Trade Notes\n\n<!-- Add your trade notes here -->\n\n## Trade Review\n\n### What worked?\n<!-- journalit-trade-review:question id=\"win-what-worked\" -->\n\n### What didn't work?\n<!-- journalit-trade-review:question id=\"win-what-failed\" -->\n\n### What will I do differently?\n<!-- journalit-trade-review:question id=\"win-next-time\" -->\n\n---\n_End Trade Review_\n"

    filepath.write_text(content, encoding="utf-8")
    return filepath


def generate_journalit_trades_from_report(
    report: DailyReport,
    vault_base: Path,
) -> list[Path]:
    """Generate all Journalit trade files for a daily report."""
    generated = []

    # Only generate for entry trades (not exits without entries)
    for trade in report.trades:
        if trade.direction in (TradeDirection.LONG, TradeDirection.SHORT):
            try:
                path = generate_journalit_trade_file(trade, report, vault_base)
                generated.append(path)
                print(f"    Generated trade file: {path.relative_to(vault_base)}")
            except Exception as e:
                print(f"    Error generating trade for {trade.ticker}: {e}")

    return generated


if __name__ == "__main__":
    # Quick test
    from src.core.parser import parse_drc_file

    vault = Path("C:/Users/Thaddeus/Claude Code Test/trading-journal-system/Vaulted/!Journalit")
    test_file = vault / "2026/Q3/07/W29/DRC-140726.md"
    if test_file.exists():
        report = parse_drc_file(test_file)
        if report:
            generated = generate_journalit_trades_from_report(report, vault)
            print(f"Generated {len(generated)} trade files")