"""
Daily Sync CLI - Parse today's DRC and generate Daily Report + Pre-Market Notes.
Run after market close: python -m src.cli.daily_sync --date 2026-07-16
"""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.parser import parse_drc_file, find_all_drc_files
from src.core.models import (
    DailyReport, OrganizedNote, ExtractedTrade, TradeDirection,
    NoteCategory, MarketBias, MarketBiasDirection, MarketBiasConfidence,
    MarketRegime, TradeStatus, PreMarketNotes, EconomicEvent
)
from src.core.extractor import LLMExtractor, extract_daily_report_fallback, generate_pre_market_fallback
from src.data.fetchers.economic_earnings import (
    fetch_pre_market_data, format_economic_for_pre_market, format_earnings_for_watchlist
)
# from src.core.extractor import LLMExtractor  # We'll implement simple fallback for now

# Read settings
import yaml
SETTINGS_FILE = Path("config/settings.yaml")
if SETTINGS_FILE.exists():
    settings = yaml.safe_load(SETTINGS_FILE.read_text())
else:
    settings = {}


app = typer.Typer(help="Daily trading journal sync")
console = Console()

# Output directories
DAILY_REPORTS_DIR = Path("data/daily_reports")
PRE_MARKET_DIR = Path("data/pre_market")
DAILY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
PRE_MARKET_DIR.mkdir(parents=True, exist_ok=True)


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
    path.write_text(report.model_dump_json(indent=2))
    return path


def load_daily_report(target_date: date) -> Optional[DailyReport]:
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


def load_pre_market(target_date: date) -> Optional[PreMarketNotes]:
    """Load pre-market notes from JSON."""
    path = PRE_MARKET_DIR / f"{target_date.isoformat()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return PreMarketNotes.model_validate(data)


def generate_pre_market_fallback(target_date: date) -> PreMarketNotes:
    """Generate pre-market notes using fallback logic (no LLM)."""
    # Load today's daily report for context
    daily_report = load_daily_report(target_date - timedelta(days=1))

    # Get economic events
    events = get_events_for_date(target_date)

    # Get latest DRC file for any overnight notes
    vault_path = Path(settings.get("vault_path", "").replace("\\", "/"))
    drc_files = find_all_drc_files(vault_path)
    latest_drc = None
    for f in drc_files:
        try:
            f_date = parse_date_from_filename(f.name)
            if f_date == target_date:
                latest_drc = f
                break
        except ValueError:
            continue

    # Build pre-market using fallback extractor
    from src.core.extractor import generate_pre_market_fallback
    pre_market = generate_pre_market_fallback(
        target_date=target_date,
        daily_report=daily_report,
        economic_events=events,
        drc_file=latest_drc
    )

    return pre_market


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


def extract_daily_report_fallback(raw_report) -> dict:
    """Fallback extraction using parser only (no LLM)."""
    organized = []
    trades = []

    for note in raw_report.organized_notes:
        organized.append(note.model_dump())

    for trade in raw_report.trades:
        trades.append(trade.model_dump())

    highlights = raw_report.highlights_for_carry_forward

    bias = raw_report.market_bias
    market_bias = {}
    if bias:
        market_bias = {
            "direction": bias.direction.value,
            "confidence": bias.confidence.value,
            "regime": bias.regime.value,
            "key_levels": bias.key_levels
        }

    return {
        "organized_notes": organized,
        "trades": trades,
        "highlights_for_carry_forward": highlights,
        "market_bias": market_bias
    }


def generate_pre_market_fallback(daily_report: DailyReport, economic_events: list) -> dict:
    """Generate pre-market notes without LLM."""
    carry_forward = daily_report.highlights_for_carry_forward[:5]

    active_rules = settings.get("active_rules", [])

    watchlist = []
    for h in daily_report.highlights_for_carry_forward:
        if h.startswith("Focus:") or h.startswith("Improve:") or h.startswith("Rule:"):
            watchlist.append(h)
    # Add tickers from notes
    tickers = daily_report.get_tickers_mentioned()
    for t in tickers:
        if t not in str(watchlist):
            watchlist.append(f"Watch {t}")

    return {
        "carry_forward": carry_forward,
        "active_rules": active_rules,
        "watchlist_candidates": watchlist[:10]
    }


@app.command()
def run(
    date_str: str = typer.Option(None, "--date", "-d", help="Date to process (YYYY-MM-DD)"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM for enhanced extraction"),
):
    """Run daily sync for a specific date."""
    target_date = parse_date(date_str) if date_str else date.today()

    console.print(f"[bold]Daily Sync for {target_date}[/bold]")

    # Find DRC file
    vault = Path(settings.get("vault_path", "C:/Users/Thaddeus/Claude Code Test/trading-journal-system/Vaulted/!Journalit"))
    drc_files = find_all_drc_files(vault)

    drc_file = None
    for f in drc_files:
        if target_date.isoformat() in f.name or f"DRC-{target_date.strftime('%d%m%y')}" in f.name:
            drc_file = f
            break

    if not drc_file:
        # Try exact match
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
        console.print(f"[red]No DRC file found for {target_date}[/red]")
        console.print("Available DRCs:")
        for f in drc_files[:20]:
            console.print(f"  {f.name}")
        raise typer.Exit(1)

    console.print(f"Found: {drc_file.name}")

    # Parse DRC
    raw_report = parse_drc_file(drc_file)
    if not raw_report:
        console.print(f"[red]No Market Notes content in {drc_file.name}[/red]")
        raise typer.Exit(1)

    # Extract with LLM or fallback
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

    # Save
    report_path = save_daily_report(daily_report)
    console.print(f"[green]Saved Daily Report:[/green] {report_path}")

    # Generate pre-market for NEXT trading day
    next_date = target_date + timedelta(days=1)
    while next_date.weekday() >= 5:  # Skip weekends
        next_date += timedelta(days=1)

    console.print(f"Generating pre-market for {next_date}...")

    # Fetch economic events + earnings from FMP
    fmp_data = fetch_pre_market_data(next_date)
    econ_events_raw = fmp_data["economic_events"]
    earnings_raw = fmp_data["earnings"]

    econ_events = format_economic_for_pre_market(econ_events_raw)
    earnings_watchlist = format_earnings_for_watchlist(earnings_raw)

    if fmp_data["economic_events"] or fmp_data["earnings"]:
        console.print(f"  FMP: {len(econ_events)} economic events, {len(earnings_watchlist)} major earnings")
    else:
        # Fallback to static calendar if no API key
        econ_events = format_economic_for_pre_market(get_events_for_date(next_date))
        console.print(f"  Static fallback: {len(econ_events)} economic events")

    # Generate pre-market base data
    pre_market_data = generate_pre_market_fallback(daily_report, econ_events)

    # Merge earnings into watchlist candidates
    watchlist = pre_market_data["watchlist_candidates"]
    for ew in earnings_watchlist:
        if ew not in str(watchlist):
            watchlist.append(ew)

    events = [EconomicEvent(
        date=next_date,
        time=e["time"],
        event=e["event"],
        impact=e["impact"]
    ) for e in econ_events]

    pre_market = PreMarketNotes(
        date=next_date,
        carry_forward=pre_market_data["carry_forward"],
        economic_events=events,
        earnings=earnings_raw,
        active_rules=pre_market_data["active_rules"],
        watchlist_candidates=watchlist[:15]  # Allow more with earnings
    )

    pre_path = save_pre_market(pre_market)
    console.print(f"[green]Saved Pre-Market:[/green] {pre_path}")

    # Show summary
    show_report_summary(daily_report)
    show_pre_market_summary(pre_market)


@app.command()
def view(
    date_str: str = typer.Argument(..., help="Date to view (YYYY-MM-DD)")
):
    """View existing daily report."""
    target_date = parse_date(date_str)
    report = load_daily_report(target_date)
    if not report:
        console.print(f"[red]No report found for {target_date}[/red]")
        raise typer.Exit(1)
    show_report_summary(report)


@app.command()
def view_pre(
    date_str: str = typer.Argument(..., help="Date to view (YYYY-MM-DD)")
):
    """View existing pre-market notes."""
    target_date = parse_date(date_str)
    pre_market = load_pre_market(target_date)
    if not pre_market:
        console.print(f"[red]No pre-market found for {target_date}[/red]")
        raise typer.Exit(1)
    show_pre_market_summary(pre_market)


@app.command()
def list():
    """List all generated daily reports."""
    reports = sorted(DAILY_REPORTS_DIR.glob("*.json"))
    if not reports:
        console.print("[yellow]No reports found[/yellow]")
        return

    table = Table(title="Daily Reports")
    table.add_column("Date")
    table.add_column("Notes")
    table.add_column("Trades")
    table.add_column("Highlights")

    for r in reports:
        data = json.loads(r.read_text())
        table.add_row(
            data["date"],
            str(len(data.get("organized_notes", []))),
            str(len(data.get("trades", []))),
            str(len(data.get("highlights_for_carry_forward", [])))
        )
    console.print(table)


def show_report_summary(report: DailyReport):
    """Display daily report summary."""
    table = Table(title=f"Daily Report - {report.date}")
    table.add_column("Time", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Text", style="white", max_width=80)
    table.add_column("Tickers", style="yellow")
    table.add_column("Levels", style="green")

    for note in report.organized_notes:
        table.add_row(
            note.timestamp,
            note.category.value,
            note.text[:80] + ("..." if len(note.text) > 80 else ""),
            ", ".join(note.tickers) if note.tickers else "-",
            ", ".join(note.key_levels_mentioned) if note.key_levels_mentioned else "-"
        )

    console.print(table)

    # Trades
    if report.trades:
        trade_table = Table(title="Trades Extracted")
        trade_table.add_column("Time", style="cyan")
        trade_table.add_column("Dir", style="magenta")
        trade_table.add_column("Ticker", style="yellow")
        trade_table.add_column("Price", style="green")
        trade_table.add_column("Size", style="blue")
        trade_table.add_column("Reason", style="white")
        trade_table.add_column("Status", style="cyan")

        for t in report.trades:
            status = t.outcome.value if t.outcome else "open"
            if t.exit_timestamp:
                status += f" @ {t.exit_timestamp}"
            trade_table.add_row(
                t.timestamp,
                t.direction.value,
                t.ticker,
                str(t.price),
                str(t.size) if t.size > 0 else "-",
                t.reason[:50] + ("..." if len(t.reason) > 50 else ""),
                status
            )
        console.print(trade_table)

    # Market bias
    if report.market_bias:
        console.print(Panel(
            f"Direction: {report.market_bias.direction.value}\n"
            f"Confidence: {report.market_bias.confidence.value}\n"
            f"Regime: {report.market_bias.regime.value}\n"
            f"Key Levels: {', '.join(report.market_bias.key_levels) or 'None'}",
            title="Market Bias"
        ))

    # Highlights
    if report.highlights_for_carry_forward:
        console.print(Panel(
            "\n".join(f"• {h}" for h in report.highlights_for_carry_forward),
            title="Highlights for Carry-Forward"
        ))


def show_pre_market_summary(pre_market: PreMarketNotes):
    """Display pre-market notes summary."""
    if pre_market.carry_forward:
        console.print(Panel(
            "\n".join(f"• {c}" for c in pre_market.carry_forward),
            title=f"Pre-Market Carry-Forward - {pre_market.date}"
        ))

    if pre_market.economic_events:
        console.print("[bold]Economic Events:[/bold]")
        for e in pre_market.economic_events:
            console.print(f"  {e.time} - {e.event} ({e.impact})")

    if pre_market.active_rules:
        console.print("[bold]Active Rules:[/bold]")
        for r in pre_market.active_rules:
            console.print(f"  • {r}")

    if pre_market.watchlist_candidates:
        console.print("[bold]Watchlist Candidates:[/bold]")
        for w in pre_market.watchlist_candidates:
            console.print(f"  • {w}")


@app.command()
def generate_pre_market(
    date_str: str = typer.Option(None, "--date", "-d", help="Date for pre-market (YYYY-MM-DD)"),
):
    """Generate pre-market notes for a specific date (default: next trading day)."""
    if date_str:
        target_date = parse_date(date_str)
    else:
        target_date = date.today() + timedelta(days=1)
        while target_date.weekday() >= 5:
            target_date += timedelta(days=1)

    console.print(f"[bold]Generating Pre-Market for {target_date}[/bold]")

    # Get economic events
    fmp_data = fetch_pre_market_data(target_date)
    econ_events_raw = fmp_data["economic_events"]
    earnings_raw = fmp_data["earnings"]

    econ_events = format_economic_for_pre_market(econ_events_raw)
    earnings_watchlist = format_earnings_for_watchlist(earnings_raw)

    if fmp_data["economic_events"] or fmp_data["earnings"]:
        console.print(f"  FMP: {len(econ_events)} economic events, {len(earnings_watchlist)} major earnings")
    else:
        econ_events = format_economic_for_pre_market(get_events_for_date(target_date))
        console.print(f"  Static fallback: {len(econ_events)} economic events")

    # Load prior daily report for carry-forward
    prev_date = target_date - timedelta(days=1)
    while prev_date.weekday() >= 5:
        prev_date -= timedelta(days=1)
    daily_report = load_daily_report(prev_date)

    # Generate
    pre_market_data = generate_pre_market_fallback(daily_report, econ_events)

    watchlist = pre_market_data["watchlist_candidates"]
    for ew in earnings_watchlist:
        if ew not in str(watchlist):
            watchlist.append(ew)

    events = [EconomicEvent(
        date=target_date,
        time=e["time"],
        event=e["event"],
        impact=e["impact"]
    ) for e in econ_events]

    pre_market = PreMarketNotes(
        date=target_date,
        carry_forward=pre_market_data["carry_forward"],
        economic_events=events,
        earnings=earnings_raw,
        active_rules=pre_market_data["active_rules"],
        watchlist_candidates=watchlist[:15]
    )

    pre_path = save_pre_market(pre_market)
    console.print(f"[green]Saved Pre-Market:[/green] {pre_path}")
    show_pre_market_summary(pre_market)


if __name__ == "__main__":
    app()