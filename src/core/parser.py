"""
DRC Markdown parser - extracts Market Notes section and parses lines.
Vault is READ-ONLY - only parsing, never writing.
"""
from __future__ import annotations
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
import frontmatter

from src.core.models import (
    DailyReport, OrganizedNote, ExtractedTrade, TradeDirection,
    NoteCategory, MarketBias, MarketBiasDirection, MarketBiasConfidence,
    MarketRegime, TradeStatus
)


# Trade extraction regex patterns
# ... (keeping the rest of the imports and constants)
# Pattern 1: Formal format "short NKE @ 55.10, 4 shares - reason"
# Also handles: "add TEAM short @ 73.58, 2 shares - reason" (ticker before direction)
# Also handles: "short LOW @ 237.60 - reason" (no shares)
# Also handles: "long ENPH @ 45.13 - reason" (no shares)
ENTRY_PATTERN = re.compile(
    r"(?i)(?:add\s+)?(?:([A-Z]{1,5})\s+(long|short)|(long|short)\s+([A-Z]{1,5}))\s*[@\$]\s*([\d.]+)(?:,?\s*(\d+)\s*shares?)?\s*[-–—]\s*(.+)"
)
# Pattern 2: Inline format "short NKE - reason" (text portion after timestamp)
INLINE_ENTRY_PATTERN = re.compile(
    r"(?i)(long|short)\s+([A-Z]{1,5})\s+[-–—]\s*(.+)"
)
# Pattern 3: Inline entry without dash "short NKE reason text"
INLINE_ENTRY_PATTERN2 = re.compile(
    r"(?i)(long|short)\s+([A-Z]{1,5})\b\s*(.+)"
)
EXIT_PATTERN = re.compile(
    r"(?i)exit\s+([A-Z]{1,5})(?:\s+(long|short))?\s*[@\$]\s*([\d.]+)(?:(?:\s+on\s+(\d+)x)|(?:,\s*(\d+)\s*shares?))?(?:\s*[-–—]\s*(.+))?"
)
# Inline exit: "exit NKE @ 54.97 - reason" (text portion) - also without @, with optional direction, "on 2x" or ", N shares" suffix
INLINE_EXIT_PATTERN = re.compile(
    r"(?i)exit\s+([A-Z]{1,5})(?:\s+(long|short))?\s*[@\$]?\s*([\d.]+)(?:(?:\s+on\s+(\d+)x)|(?:,\s*(\d+)\s*shares?))?(?:\s*[-–—]\s*(.+))?"
)
TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")
# Timestamp pattern: handles "10:33 text" (with space) and "10:33Stext" (without space)
# After the time, either whitespace or end-of-line or a non-digit non-colon character
TIMESTAMP_PATTERN = re.compile(r"^(\d{1,2}:\d{2})(?:\s+|(?=\S))(.+)$")


# Common false positive tickers to exclude
EXCLUDE_TICKERS = {
    "SPY", "QQQ", "IWM", "DIA", "VIX", "VXX", "UVXY", "SVXY",
    "M5", "M15", "M30", "H1", "H4", "D1", "W1", "M1",
    "EMA", "SMA", "VWAP", "ATR", "RSI", "MACD", "BB",
    "PDH", "PDL", "HOD", "LOD", "AOD", "PWClose",
    "EOD", "RS", "RW", "ATH", "ATL",  # Trading terms: End of Day, Relative Strength/Weakness, All Time High/Low
    "FOMO", "LPTE", "HPTE", "RTH", "ETH",
    "HA", "CH", "ATRH", "ATRL",
    "H+", "H-", "L+", "L-", "H", "L",  # Trendline levels (OneOption notation)
    "I", "A", "AN", "IF", "OR", "ON", "AT", "TO", "BE", "BY", "DO", "GO", "HE", "ME", "MY", "NO", "OF", "UP", "US", "WE",  # Single letters and common words (S=SPY shorthand - removed as S is a valid ticker)
    "HERE", "USING", "THEN", "THIS", "THAT", "THE", "AND", "BUT", "FOR", "NOT", "YOU", "ARE", "HAD", "HAS", "HIS", "HER", "ITS", "OUR", "OUT", "NOW", "NEW", "OLD", "ONE", "TWO", "WHO", "WHY", "HOW", "WHEN", "WHERE", "WHAT", "WHICH", "WILL", "WOULD", "COULD", "SHOULD", "MIGHT", "MAY", "CAN", "MUST", "NEED", "WANT", "LIKE", "JUST", "ONLY", "EVEN", "ALSO", "VERY", "MUCH", "MORE", "MOST", "LESS", "LEAST", "BEST", "LAST", "FIRST", "NEXT", "AFTER", "BEFORE", "DURING", "ABOUT", "ABOVE", "BELOW", "BETWEEN", "UNDER", "OVER", "AGAIN", "ONCE", "TWICE",  # Common English words that could be parsed as tickers
    "MIGHT", "LOOKS", "BUT", "GREEN", "SCRATCH", "STILL", "STOCK", "LOOK", "GOOD", "DONT", "LIKE", "THAT", "THE", "LON", "LONG", "SHORT", "EXIT", "ENTRY", "TRADE", "FROM", "NOTES", "WHEN", "GOT", "THEN", "WOULD", "HAVE", "THIS", "CANDLE", "NICE", "CLOSE", "HIGH", "VOLUME", "BREAKDOWN", "SMALL", "POP", "WAIT", "FOR", "ADD", "ANOTHER", "SHARE", "IF", "IT", "CLOSES", "ITS", "REALLY", "SWINGING", "WILL", "OPEN", "SO", "CAN", "EITHER", "ENTER", "NOW", "TO", "OR", "BUT", "AND", "KKR",  # Common words from notes + KKR (not traded)
    # Additional trading terms that might be parsed as tickers
    "PBO", "VWAP", "HOD", "EOD", "RW", "RS"
}


# Tag extraction patterns for #watch, #flag, etc.
TAG_PATTERN = re.compile(r"#(\w+)")
# Pattern to extract #flagN where N is the number of messages including current
FLAG_TAG_PATTERN = re.compile(r"#flag(\d+)")
KNOWN_TAGS = {"watch", "flag", "review", "todo", "note", "idea", "setup", "mistake", "good", "bad", "emotion", "sector", "gold", "ptrade"}


def extract_tags(text: str) -> tuple[list[str], int]:
    """
    Extract #tags from text, normalizing to lowercase.
    Returns (tags_list, flag_context_count).
    Handles #flagN format where N indicates total messages to include (current + N-1 prior).
    """
    tags = []
    flag_context = 0

    for match in TAG_PATTERN.finditer(text):
        tag = match.group(1).lower()
        tags.append(tag)

        # Check for #flagN pattern
        if tag.startswith("flag") and len(tag) > 4:
            num_part = tag[4:]
            if num_part.isdigit():
                flag_context = max(flag_context, int(num_part))
                # Store just "flag" in tags list
                tags[-1] = "flag"

    # Deduplicate while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)

    return unique_tags, flag_context


def extract_tickers(text: str) -> list[str]:
    """Extract valid tickers (1-5 uppercase letters) from text."""
    tickers = set()
    for match in TICKER_PATTERN.finditer(text):
        ticker = match.group(1)
        if ticker not in EXCLUDE_TICKERS and 1 <= len(ticker) <= 5:
            tickers.add(ticker)
    return sorted(tickers)


def extract_key_levels(text: str) -> list[str]:
    """Extract key level references from text."""
    levels = []
    text_lower = text.lower()

    level_patterns = {
        "VWAP": ["vwap", "v wap"],
        "VWAP+": ["vwap+", "vwap +", "above vwap"],
        "VWAP-": ["vwap-", "vwap -", "below vwap"],
        "D1 8 EMA": ["d1 8 ema", "8 ema", "8ema"],
        "D1 15 EMA": ["d1 15 ema", "15 ema", "15ema"],
        "D1 50 SMA": ["d1 50 sma", "50 sma", "50sma"],
        "D1 100 SMA": ["d1 100 sma", "100 sma", "100sma"],
        "D1 200 SMA": ["d1 200 sma", "200 sma", "200sma"],
        "M5 VWAP": ["m5 vwap", "5min vwap"],
        "M5 8/15 EMA": ["m5 8/15", "m5 8 ema", "m5 15 ema"],
        "PDH": ["pdh", "prior day high"],
        "PDL": ["pdl", "prior day low"],
        "Friday HOD": ["friday hod", "fri hod"],
        "Friday LOD": ["friday lod", "fri lod"],
        "ATRH": ["atr high", "atrh"],
        "ATRL": ["atr low", "atrl"],
        "LOD": ["\blod\b", "low of day"],
        "HOD": ["\bhod\b", "high of day"],
    }

    for level, patterns in level_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                levels.append(level)
                break

    return levels


def categorize_note(text: str, is_trade: bool, trade_direction: Optional[TradeDirection] = None) -> NoteCategory:
    """Categorize a note based on content."""
    text_lower = text.lower()

    if is_trade and trade_direction in (TradeDirection.LONG, TradeDirection.SHORT):
        return NoteCategory.ENTRY
    if is_trade and trade_direction == TradeDirection.EXIT:
        return NoteCategory.EXIT

    # Emotion keywords
    emotion_keywords = ["fomo", "chased", "panic", "scared", "fear", "greed", "frustrat", "angry", "tilt"]
    if any(kw in text_lower for kw in emotion_keywords):
        return NoteCategory.EMOTION

    # Decision keywords
    decision_keywords = ["watch", "waiting", "skip", "pass", "not taking", "decided not", "holding off"]
    if any(kw in text_lower for kw in decision_keywords):
        return NoteCategory.DECISION

    return NoteCategory.OBSERVATION


def parse_trade_line(line: str, timestamp: str) -> Optional[ExtractedTrade]:
    """Try to parse a line as a trade entry or exit."""
    # Try exit patterns FIRST (before entry patterns) since exit lines can match entry patterns too
    # Try inline exit pattern: "exit NKE @ 54.97 - reason"
    inline_exit = INLINE_EXIT_PATTERN.search(line)
    if inline_exit:
        groups = inline_exit.groups()
        # Groups: ticker, dir_opt, price_str, size_on_x, size_shares, reason
        ticker, dir_opt, price_str, size_on_x, size_shares, reason = groups
        ticker = ticker.upper()
        if ticker in EXCLUDE_TICKERS:
            return None

        # Parse exited direction if present
        exited_direction = None
        if dir_opt and dir_opt.lower() in ("long", "short"):
            exited_direction = TradeDirection(dir_opt.lower())

        # Extract size from either "on Nx" or ", N shares" format
        size = int(size_on_x) if size_on_x else (int(size_shares) if size_shares else 0)

        return ExtractedTrade(
            timestamp=timestamp,
            direction=TradeDirection.EXIT,
            ticker=ticker,
            price=float(price_str),
            size=size,
            reason=reason.strip() if reason else "",
            exited_direction=exited_direction,
        )

    # Try formal exit pattern
    exit_match = EXIT_PATTERN.search(line)
    if exit_match:
        groups = exit_match.groups()
        # Groups: ticker, dir_opt, price_str, size_on_x, size_shares, reason
        ticker, dir_opt, price_str, size_on_x, size_shares, reason = groups
        ticker = ticker.upper()
        if ticker in EXCLUDE_TICKERS:
            return None

        # Parse exited direction if present
        exited_direction = None
        if dir_opt and dir_opt.lower() in ("long", "short"):
            exited_direction = TradeDirection(dir_opt.lower())

        # Extract size
        size = int(size_on_x) if size_on_x else (int(size_shares) if size_shares else 0)

        return ExtractedTrade(
            timestamp=timestamp,
            direction=TradeDirection.EXIT,
            ticker=ticker,
            price=float(price_str),
            size=size,
            reason=reason.strip() if reason else "",
            exited_direction=exited_direction,
        )

    # Try formal entry pattern
    entry_match = ENTRY_PATTERN.search(line)
    if entry_match:
        ticker1, dir1, dir2, ticker2, price_str, size_str, reason = entry_match.groups()
        if ticker1:
            ticker, direction_str = ticker1, dir1
        else:
            ticker, direction_str = ticker2, dir2
        ticker = ticker.upper()
        if ticker in EXCLUDE_TICKERS:
            return None
        size = int(size_str) if size_str else 0
        return ExtractedTrade(
            timestamp=timestamp,
            direction=TradeDirection(direction_str.lower()),
            ticker=ticker,
            price=float(price_str),
            size=size,
            reason=reason.strip(),
        )

    # Try inline entry pattern: "short NKE - reason"
    inline_match = INLINE_ENTRY_PATTERN.search(line)
    if inline_match:
        direction_str, ticker, reason = inline_match.groups()
        ticker = ticker.upper()
        if ticker in EXCLUDE_TICKERS:
            return None
        return ExtractedTrade(
            timestamp=timestamp,
            direction=TradeDirection(direction_str.lower()),
            ticker=ticker,
            price=0.0,
            size=0,
            reason=reason.strip(),
        )

    # Try inline entry without dash: "short NKE reason text"
    inline_match2 = INLINE_ENTRY_PATTERN2.search(line)
    if inline_match2:
        direction_str, ticker, reason = inline_match2.groups()
        ticker = ticker.upper()
        if ticker in EXCLUDE_TICKERS:
            return None
        # Skip if it's a continuation like "short NKE - reason already captured"
        if " - " not in reason[:20]:
            return ExtractedTrade(
                timestamp=timestamp,
                direction=TradeDirection(direction_str.lower()),
                ticker=ticker,
                price=0.0,
                size=0,
                reason=reason.strip(),
            )

    return None


def parse_market_notes_section(content: str) -> list[OrganizedNote]:
    """
    Parse the Market Notes section content into structured notes.
    Expected format: timestamped bullet points like "- 9:40 some text"
    """
    notes = []

    # Find Market Notes section
    market_notes_match = re.search(
        r"## Market Notes\n(.*?)(?:\n##|\n---|\Z)",
        content,
        re.DOTALL | re.IGNORECASE
    )
    if not market_notes_match:
        return notes

    section = market_notes_match.group(1).strip()
    if not section:
        return notes

    # Split into lines
    raw_lines = section.split("\n")
    current_note = None

    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue

        # Check for timestamp at start (with or without bullet)
        ts_match = TIMESTAMP_PATTERN.match(raw.lstrip("-•* "))
        if ts_match:
            # Save previous note
            if current_note:
                notes.append(current_note)

            timestamp, text = ts_match.groups()
            # Fix: if text doesn't start with space (e.g., "10:33S nice" -> "S nice"), prepend space
            if text and not text.startswith(" "):
                text = " " + text
            tickers = extract_tickers(text)
            key_levels = extract_key_levels(text)
            tags, flag_context = extract_tags(text)
            trade = parse_trade_line(text, timestamp)
            is_trade = trade is not None
            category = categorize_note(text, is_trade, trade.direction if trade else None)

            current_note = OrganizedNote(
                timestamp=timestamp,
                text=text,
                tickers=tickers,
                category=category,
                key_levels_mentioned=key_levels,
                tags=tags,
                flag_context=flag_context
            )
            # Store trade info temporarily in key_levels or we need a different approach
            if trade:
                if trade.direction == TradeDirection.EXIT and trade.exited_direction:
                    current_note.text += f" [TRADE: {trade.direction.value} {trade.ticker} {trade.exited_direction.value.lower()} @ {trade.price} x{trade.size}]"
                else:
                    current_note.text += f" [TRADE: {trade.direction.value} {trade.ticker} @ {trade.price} x{trade.size}]"
        elif current_note:
            # Continuation line
            current_note.text += " " + raw
            current_note.tickers = extract_tickers(current_note.text)
            current_note.key_levels_mentioned = extract_key_levels(current_note.text)
            current_note.tags, current_note.flag_context = extract_tags(current_note.text)
            # Re-categorize with full text
            trade = parse_trade_line(current_note.text, current_note.timestamp)
            is_trade = trade is not None
            current_note.category = categorize_note(current_note.text, is_trade, trade.direction if trade else None)
            if trade:
                if trade.direction == TradeDirection.EXIT and trade.exited_direction:
                    current_note.text += f" [TRADE: {trade.direction.value} {trade.ticker} {trade.exited_direction.value.lower()} @ {trade.price} x{trade.size}]"
                else:
                    current_note.text += f" [TRADE: {trade.direction.value} {trade.ticker} @ {trade.price} x{trade.size}]"
        else:
            # No timestamp, treat as standalone
            tickers = extract_tickers(raw)
            key_levels = extract_key_levels(raw)
            tags, flag_context = extract_tags(raw)
            trade = parse_trade_line(raw, "?:??")
            is_trade = trade is not None
            category = categorize_note(raw, is_trade, trade.direction if trade else None)

            note = OrganizedNote(
                timestamp="?:??",
                text=raw,
                tickers=tickers,
                category=category,
                key_levels_mentioned=key_levels,
                tags=tags,
                flag_context=flag_context
            )
            notes.append(note)

    # Don't forget the last note
    if current_note:
        notes.append(current_note)

    # Sort by timestamp
    def time_sort_key(note: OrganizedNote) -> tuple:
        try:
            parts = note.timestamp.split(":")
            return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        except Exception:
            return (99, 99)

    notes.sort(key=time_sort_key)
    return notes


def extract_flag_context(notes: list[OrganizedNote]) -> list[OrganizedNote]:
    """
    Validate and preserve #flagN context information.
    The flag_context count is already set during parsing; this function
    just ensures it's correctly preserved. The actual context display
    should be computed on-demand in the UI (flags/tags section).
    """
    # The flag_context is already set during parse_market_notes_section
    # via extract_tags(). We just return the notes unchanged to preserve
    # the original text. UI will compute context from the notes list.
    return notes


def extract_raw_market_notes(content: str) -> str:
    """Extract raw Market Notes text for preservation."""
    match = re.search(
        r"## Market Notes\n(.*?)(?:\n##|\n---|\Z)",
        content,
        re.DOTALL | re.IGNORECASE
    )
    return match.group(1).strip() if match else ""


def extract_highlights_from_review(content: str) -> list[str]:
    """Extract actionable highlights from Review section for carry-forward."""
    highlights = []

    # Post-market Comments
    pm_match = re.search(
        r"### Post-market Comments\n(.*?)(?:\n###|\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE
    )
    if pm_match:
        text = pm_match.group(1).strip()
        if text and text != "-":
            highlights.append(f"Market context: {text}")

    # What will I focus on
    focus_match = re.search(
        r"### What will I focus on for the next session\?\n(.*?)(?:\n###|\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE
    )
    if focus_match:
        for line in focus_match.group(1).split("\n"):
            line = line.strip().lstrip("-•* ")
            if line and line != "-":
                highlights.append(f"Focus: {line}")

    # What could I improve on
    improve_match = re.search(
        r"### What could I improve on\?\n(.*?)(?:\n###|\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE
    )
    if improve_match:
        for line in improve_match.group(1).split("\n"):
            line = line.strip().lstrip("-•* ")
            if line and line != "-":
                highlights.append(f"Improve: {line}")

    # What did I do well
    well_match = re.search(
        r"### What did I do well today\?\n(.*?)(?:\n###|\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE
    )
    if well_match:
        for line in well_match.group(1).split("\n"):
            line = line.strip().lstrip("-•* ")
            if line and line != "-":
                highlights.append(f"Strength: {line}")

    return highlights


def infer_market_bias(notes: list[OrganizedNote]) -> MarketBias:
    """Infer market bias from notes."""
    text = " ".join(n.text.lower() for n in notes)

    # Explicit regime keywords (strongest signal)
    regime = MarketRegime.TRANSITIONAL
    if "hpte" in text or "high probability" in text:
        regime = MarketRegime.HPTE
    elif "lpte" in text or "low probability" in text:
        regime = MarketRegime.LPTE

    # Direction keywords
    bearish_keywords = [
        "short ", " shorts", "shorting", "breakdown", "bearish", "downtrend",
        "sell the rip", "fade", "resistance", "rejection", "vap-",
        "lpte", "low prob", "gap fill", "gap down"
    ]
    bullish_keywords = [
        "long ", " longs", "going long", "breakout", "bullish", "uptrend",
        "buy the dip", "support", "bounce", "vap+",
        "hpte", "high prob", "gap and go", "gap up"
    ]
    chop_keywords = ["chop", "choppy", "range", "sideways", "chop city"]

    bearish_score = sum(1 for kw in bearish_keywords if kw in text)
    bullish_score = sum(1 for kw in bullish_keywords if kw in text)
    chop_score = sum(1 for kw in chop_keywords if kw in text)

    if bearish_score > bullish_score and bearish_score > chop_score:
        direction = MarketBiasDirection.BEARISH
    elif bullish_score > bearish_score and bullish_score > chop_score:
        direction = MarketBiasDirection.BULLISH
    elif chop_score > 0:
        direction = MarketBiasDirection.CHOP
    else:
        # Check trade directions
        short_count = sum(1 for n in notes if "short" in n.text.lower() and "shorts" not in n.text.lower())
        long_count = sum(1 for n in notes if " long " in n.text.lower() or "going long" in n.text.lower())
        if short_count > long_count:
            direction = MarketBiasDirection.BEARISH
        elif long_count > short_count:
            direction = MarketBiasDirection.BULLISH
        else:
            direction = MarketBiasDirection.UNCLEAR

    # Confidence
    max_score = max(bearish_score, bullish_score, chop_score)
    if max_score >= 3:
        confidence = MarketBiasConfidence.HIGH
    elif max_score >= 1:
        confidence = MarketBiasConfidence.MEDIUM
    else:
        confidence = MarketBiasConfidence.LOW

    # Key levels
    levels = set()
    for n in notes:
        levels.update(n.key_levels_mentioned)

    return MarketBias(
        direction=direction,
        confidence=confidence,
        regime=regime,
        key_levels=sorted(levels)
    )


def parse_drc_file(filepath: Path) -> Optional[DailyReport]:
    """Parse a DRC markdown file into a DailyReport."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

    # Parse frontmatter
    try:
        post = frontmatter.loads(content)
        metadata = post.metadata
        body = post.content
    except Exception:
        body = content
        metadata = {}

    # Get date from frontmatter or filename
    report_date = None
    if "date" in metadata:
        if isinstance(metadata["date"], str):
            report_date = datetime.fromisoformat(metadata["date"]).date()
        elif isinstance(metadata["date"], date):
            report_date = metadata["date"]
        elif isinstance(metadata["date"], datetime):
            report_date = metadata["date"].date()

    if not report_date:
        stem = filepath.stem
        date_match = re.search(r"(\d{2})(\d{2})(\d{2})", stem)
        if date_match:
            day, month, year = date_match.groups()
            report_date = date(2000 + int(year), int(month), int(day))

    if not report_date:
        print(f"Could not determine date for {filepath}")
        return None

    # Parse Market Notes
    organized_notes = parse_market_notes_section(body)
    # Expand #flagN context
    organized_notes = extract_flag_context(organized_notes)
    raw_notes = extract_raw_market_notes(body)

    if not organized_notes:
        return None  # Skip empty Market Notes

    # Build trades from organized notes
    trades = []
    open_trades = {}  # ticker -> entry trade

    for note in organized_notes:
        if "[TRADE:" in note.text:
            # Extract trade info from appended text
            # Format: [TRADE: DIRECTION TICKER @ PRICE xSIZE] or [TRADE: EXIT TICKER long/short @ PRICE xSIZE]
            trade_match = re.search(r"\[TRADE: (\w+) (\w+) (?:(\w+) )?@ ([\d.]+) x(\d+)\]", note.text)
            if trade_match:
                groups = trade_match.groups()
                # Groups: direction, ticker, exited_direction (optional), price, size
                direction_str = groups[0]
                ticker = groups[1]
                exited_direction_str = groups[2]  # This is 'long'/'short' for exits, None for entries
                price_str = groups[3]
                size_str = groups[4]

                direction = TradeDirection(direction_str)
                price = float(price_str)
                size = int(size_str)
                reason = note.text.split(" - ")[-1] if " - " in note.text else "From notes"

                exited_direction = None
                if direction == TradeDirection.EXIT and exited_direction_str:
                    if exited_direction_str.lower() in ("long", "short"):
                        exited_direction = TradeDirection(exited_direction_str.lower())

                trade = ExtractedTrade(
                    timestamp=note.timestamp,
                    direction=direction,
                    ticker=ticker,
                    price=price,
                    size=size,
                    reason=reason,
                    exited_direction=exited_direction,
                )

                if direction == TradeDirection.EXIT:
                    # Match with open trade
                    if ticker in open_trades:
                        open_trades[ticker].outcome = TradeStatus.CLOSED
                        open_trades[ticker].exit_timestamp = note.timestamp
                        open_trades[ticker].exit_price = price
                        open_trades[ticker].exit_reason = note.text.split(" - ")[-1] if " - " in note.text else ""
                        trades.append(open_trades.pop(ticker))
                    else:
                        trades.append(trade)  # Orphan exit
                else:
                    open_trades[ticker] = trade

    # Add any still-open trades
    trades.extend(open_trades.values())

    # Extract highlights
    highlights = extract_highlights_from_review(body)

    # Infer market bias
    market_bias = infer_market_bias(organized_notes)

    return DailyReport(
        date=report_date,
        organized_notes=organized_notes,
        trades=trades,
        highlights_for_carry_forward=highlights,
        market_bias=market_bias,
        raw_market_notes=raw_notes,
        source_file=str(filepath)
    )


def find_all_drc_files(vault_path: Path) -> list[Path]:
    """Find all DRC markdown files in vault."""
    # Use set to deduplicate (case-insensitive filesystem may match both DRC- and drc-)
    drc_files = set()
    for pattern in ["DRC-*.md", "DRC-*.markdown"]:
        drc_files.update(vault_path.rglob(pattern))
    return sorted(drc_files, key=lambda p: p.name)


def parse_all_drcs(vault_path: Path) -> list[DailyReport]:
    """Parse all DRC files in vault."""
    reports = []
    for filepath in find_all_drc_files(vault_path):
        report = parse_drc_file(filepath)
        if report:
            reports.append(report)
    return reports


if __name__ == "__main__":
    # Quick test
    vault = Path("C:/Users/Thaddeus/Claude Code Test/trading-journal-system/Vaulted/!Journalit")
    test_file = vault / "2026/Q1/03/W11/DRC-120326.md"
    if test_file.exists():
        report = parse_drc_file(test_file)
        if report:
            print(f"Date: {report.date}")
            print(f"Notes: {len(report.organized_notes)}")
            print(f"Trades: {len(report.trades)}")
            print(f"Highlights: {len(report.highlights_for_carry_forward)}")
            print(f"Market Bias: {report.market_bias}")
            for note in report.organized_notes[:10]:
                print(f"  {note.timestamp} [{note.category.value}] {note.text[:100]}")
            for trade in report.trades:
                print(f"  TRADE: {trade.direction.value} {trade.ticker} @ {trade.price} x{trade.size} - {trade.reason}")
    else:
        print("Test file not found")