#!/usr/bin/env python
"""Weekly Synthesis - Aggregate daily reports into weekly reviews with semantic clustering."""
from __future__ import annotations
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from collections import defaultdict
import json
import yaml
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.models import (
    DailyReport, WeeklyReview, PatternSuggestion, SetupPerformance,
    PatternType, NoteCategory, TradeDirection,
    OrganizedNote, TradeStatus
)
from datetime import date, datetime


# Output directories
SETTINGS_FILE = Path("config/settings.yaml")
if SETTINGS_FILE.exists():
    settings = yaml.safe_load(SETTINGS_FILE.read_text())
else:
    settings = {}

DAILY_REPORTS_DIR = Path("data/daily_reports")
WEEKLY_REVIEWS_DIR = Path("data/weekly_reviews")
PATTERNS_DIR = Path("data/patterns")
WEEKLY_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
PATTERNS_DIR.mkdir(parents=True, exist_ok=True)

# Active rules from settings (fallback defaults)
ACTIVE_RULES = settings.get("active_rules", [
    "NO FOMO entries - wait for M5 pullback close",
    "Don't exit winner on single M5 candle - need 2 stacked reds + volume",
    "NO short entries on gap days without M5 pullback confirmation",
    "Respect VWAP - don't chase extended moves",
    "Size down on gap days - wider stops needed",
])


def get_week_range(target_date: date) -> tuple[date, date]:
    """Get Monday-Sunday range for the week containing target_date."""
    monday = target_date - timedelta(days=target_date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_week_label(target_date: date) -> str:
    """Get week label like 'W11' for the week containing target_date."""
    monday, _ = get_week_range(target_date)
    # ISO week number
    week_num = monday.isocalendar()[1]
    return f"W{week_num:02d}"


def load_daily_reports_for_week(monday: date, sunday: date) -> list[DailyReport]:
    """Load all daily reports for a given week (Mon-Fri trading days)."""
    reports = []
    current = monday
    while current <= sunday:
        if current.weekday() < 5:  # Mon-Fri only
            path = DAILY_REPORTS_DIR / f"{current.isoformat()}.json"
            if path.exists():
                data = json.loads(path.read_text())
                reports.append(DailyReport.model_validate(data))
        current += timedelta(days=1)
    return reports


def collect_mistake_notes(reports: list[DailyReport]) -> list[tuple[date, OrganizedNote]]:
    """Collect all EMOTION category notes (mistakes/FOMO/fear) across the week."""
    mistakes = []
    for r in reports:
        for note in r.organized_notes:
            if note.category == NoteCategory.EMOTION:
                mistakes.append((r.date, note))
    return mistakes


def collect_setup_notes(reports: list[DailyReport]) -> dict[str, list[tuple[date, OrganizedNote]]]:
    """Collect notes by mentioned setup/ticker pattern."""
    setups = defaultdict(list)
    for r in reports:
        for note in r.organized_notes:
            # Extract potential setup names from note text
            text_lower = note.text.lower()
            # Common setup keywords
            setup_keywords = [
                "vwap", "vwap pullback", "orb", "opening range breakout",
                "m5 pullback", "m15 pullback", "gap", "gap fill",
                "breakout", "breakdown", "reversal", "trend pullback",
                "vwap reclaim", "vwap rejection", "opening drive",
                "m5 trend", "m15 trend", "vwap hold", "vwap break"
            ]
            for kw in setup_keywords:
                if kw in text_lower:
                    setups[kw].append((r.date, note))
    return dict(setups)


def build_weekly_review(monday: date) -> WeeklyReview:
    """Build a complete weekly review from daily reports."""
    monday, sunday = get_week_range(monday)
    week_label = get_week_label(monday)

    reports = load_daily_reports_for_week(monday, sunday)
    if not reports:
        return None

    # Collect mistakes (EMOTION category notes)
    mistakes = collect_mistake_notes(reports)

    # Collect setups
    setups = collect_setup_notes(reports)

    # Build pattern suggestions from mistake clustering (simple frequency for now)
    pattern_suggestions = build_pattern_suggestions(mistakes, setups, reports)

    # Build setup performance
    setup_performance = build_setup_performance(setups, reports)

    # Metric updates
    metric_updates = build_metric_updates(reports)

    review = WeeklyReview(
        week=week_label,
        date_range=(monday, sunday),
        daily_reports=reports,
        pattern_suggestions=pattern_suggestions,
        setup_performance=setup_performance,
        metric_updates=metric_updates,
        user_notes=""
    )

    return review


def build_pattern_suggestions(
    mistakes: list[tuple[date, OrganizedNote]],
    setups: dict[str, list[tuple[date, OrganizedNote]]],
    reports: list[DailyReport]
) -> list[PatternSuggestion]:
    """Build pattern suggestions using semantic clustering (placeholder - uses frequency for now)."""
    suggestions = []

    # Cluster mistakes by text similarity (simplified - frequency based)
    mistake_texts = defaultdict(list)
    for d, note in mistakes:
        # Normalize text for clustering
        key = note.text.lower().strip()
        # Simple normalization: remove timestamps, tickers, specific prices
        import re
        key = re.sub(r'\d{1,2}:\d{2}', '', key)
        key = re.sub(r'\$\d+\.?\d*', '', key)
        key = re.sub(r'@\s*\d+\.?\d*', '', key)
        key = re.sub(r'\b[A-Z]{1,5}\b', 'TICKER', key)
        key = re.sub(r'\s+', ' ', key).strip()
        mistake_texts[key].append((d, note.text))

    for pattern_text, occurrences in mistake_texts.items():
        if len(occurrences) >= 2:  # Pattern appears at least twice
            dates = [d for d, _ in occurrences]
            quotes = [text[:200] for _, text in occurrences]
            freq = len(occurrences)

            # Determine severity
            emotion_keywords = ["fomo", "fear", "panic", "revenge", "tilt", "chase", "forced", "hesitat"]
            severity = "critical" if any(kw in pattern_text for kw in emotion_keywords) else "medium"

            suggestions.append(PatternSuggestion(
                pattern=pattern_text[:200],
                type=PatternType.MISTAKE,
                supporting_days=dates,
                evidence_quotes=quotes,
                frequency=freq,
                severity_hint=severity
            ))

    # Add setup patterns
    for setup_name, occurrences in setups.items():
        if len(occurrences) >= 2:
            dates = [d for d, _ in occurrences]
            quotes = [note.text[:200] for _, note in occurrences]
            suggestions.append(PatternSuggestion(
                pattern=f"Setup: {setup_name}",
                type=PatternType.SETUP,
                supporting_days=dates,
                evidence_quotes=quotes,
                frequency=len(occurrences),
                severity_hint="low"
            ))

    return suggestions


def build_setup_performance(
    setups: dict[str, list[tuple[date, OrganizedNote]]],
    reports: list[DailyReport]
) -> list[SetupPerformance]:
    """Build setup performance metrics."""
    performance = []
    for setup_name, occurrences in setups.items():
        if len(occurrences) < 2:
            continue
        # Count trades associated with this setup
        trades = 0
        wins = 0
        for r in reports:
            for trade in r.trades:
                if trade.outcome.value != "open":
                    trades += 1
                    if trade.outcome == TradeStatus.CLOSED and trade.exit_price:
                        if trade.direction == TradeDirection.LONG:
                            pnl = trade.exit_price - trade.price
                        else:
                            pnl = trade.price - trade.exit_price
                        if pnl > 0:
                            wins += 1

        if trades > 0:
            performance.append(SetupPerformance(
                setup=setup_name,
                market_condition="mixed",  # Would need market regime per day
                trades=trades,
                wins=wins,
                notes=f"Observed {len(occurrences)} times in notes"
            ))
    return performance


def build_metric_updates(reports: list[DailyReport]) -> dict[str, list[dict]]:
    """Build weekly metric tracking data."""
    metrics = defaultdict(list)

    for r in reports:
        # Mistake count
        mistake_count = len(r.get_mistakes())
        metrics["weekly_mistakes"].append({"date": r.date.isoformat(), "value": mistake_count})

        # Trade count
        trade_count = len(r.trades)
        metrics["weekly_trades"].append({"date": r.date.isoformat(), "value": trade_count})

        # Win rate (for closed trades)
        closed = [t for t in r.trades if t.outcome == TradeStatus.CLOSED]
        if closed:
            wins = sum(1 for t in closed if t.exit_price and
                      (t.direction == TradeDirection.LONG and t.exit_price > t.price) or
                      (t.direction == TradeDirection.SHORT and t.exit_price < t.price))
            wr = wins / len(closed) * 100
            metrics["daily_win_rate"].append({"date": r.date.isoformat(), "value": round(wr, 1)})

        # Market bias confidence
        if r.market_bias:
            conf_map = {"high": 3, "medium": 2, "low": 1}
            metrics["bias_confidence"].append({"date": r.date.isoformat(), "value": conf_map.get(r.market_bias.confidence.value, 0)})

        # Highlights count
        metrics["highlights_count"].append({"date": r.date.isoformat(), "value": len(r.highlights_for_carry_forward)})

    return dict(metrics)


def save_weekly_review(review: WeeklyReview) -> Path:
    """Save weekly review to JSON."""
    path = WEEKLY_REVIEWS_DIR / f"{review.week}.json"
    path.write_text(review.model_dump_json(indent=2))
    return path


def load_weekly_review(week_label: str) -> WeeklyReview | None:
    """Load weekly review from JSON."""
    path = WEEKLY_REVIEWS_DIR / f"{week_label}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return WeeklyReview.model_validate(data)


def list_weekly_reviews() -> list[str]:
    """List all weekly review files."""
    return sorted([f.stem for f in WEEKLY_REVIEWS_DIR.glob("W*.json")])


def main():
    """Process all weeks with daily reports."""
    print("Building weekly reviews...")

    # Get all dates with daily reports
    dates = set()
    for f in DAILY_REPORTS_DIR.glob("*.json"):
        try:
            d = date.fromisoformat(f.stem)
            dates.add(d)
        except ValueError:
            continue

    if not dates:
        print("No daily reports found. Run historical ingestion first.")
        return

    # Group by week
    weeks = defaultdict(list)
    for d in dates:
        monday, _ = get_week_range(d)
        weeks[monday].append(d)

    print(f"Found {len(weeks)} weeks with data")

    for monday in sorted(weeks.keys()):
        week_label = get_week_label(monday)
        existing = WEEKLY_REVIEWS_DIR / f"{week_label}.json"
        if existing.exists():
            print(f"  {week_label}: already exists, skipping")
            continue

        review = build_weekly_review(monday)
        if review:
            save_weekly_review(review)
            print(f"  {week_label}: created ({len(review.pattern_suggestions)} patterns, {len(review.setup_performance)} setups)")
        else:
            print(f"  {week_label}: no data")


if __name__ == "__main__":
    main()