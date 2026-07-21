"""
LLM Extraction Pipeline - calls LLM to structure daily reports and generate pre-market notes.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from src.core.models import (
    DailyReport, PreMarketNotes, OrganizedNote, ExtractedTrade,
    MarketBias, MarketBiasDirection, MarketBiasConfidence, MarketRegime,
    NoteCategory, TradeDirection, TradeStatus
)


class LLMExtractor:
    """Handles LLM calls with caching and retries."""

    def __init__(self, settings: dict):
        self.settings = settings
        self.llm_config = settings.get("llm", {})
        self.cache_dir = Path(settings.get("output_dir", "data")) / "cache" / "llm"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.provider = self.llm_config.get("provider", "groq")
        self.model = self.llm_config.get("model", "llama-3.1-70b-versatile")
        self.temperature = self.llm_config.get("temperature", 0.1)
        self.max_tokens = self.llm_config.get("max_tokens", 4000)
        self.timeout = self.llm_config.get("timeout_seconds", 30)
        self.max_retries = self.llm_config.get("max_retries", 3)

        self.api_key = os.environ.get(self.llm_config.get("api_key_env", "GROQ_API_KEY"))

        # Load prompts
        prompts_dir = Path("config/prompts")
        self.daily_report_prompt = (prompts_dir / "daily_report.txt").read_text(encoding="utf-8")
        self.pre_market_prompt = (prompts_dir / "pre_market.txt").read_text(encoding="utf-8")

        # Initialize client
        self._init_client()

    def _init_client(self):
        """Initialize LLM client based on provider."""
        if self.provider == "groq":
            from groq import Groq
            self.client = Groq(api_key=self.api_key, timeout=self.timeout)
        elif self.provider == "google":
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
        elif self.provider == "ollama":
            import ollama
            self.client = ollama.Client()
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _get_cache_key(self, prompt: str, input_data: str) -> str:
        """Generate cache key from prompt + input."""
        content = f"{prompt}:{input_data}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_cached(self, cache_key: str) -> Optional[dict]:
        """Get cached response if exists."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _save_cache(self, cache_key: str, response: dict):
        """Save response to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_file.write_text(json.dumps(response, indent=2), encoding="utf-8")

    def _call_llm(self, prompt: str, input_text: str) -> Optional[dict]:
        """Call LLM with retry logic."""
        cache_key = self._get_cache_key(prompt, input_text)

        # Check cache first
        if self.settings.get("processing", {}).get("skip_if_cached", True):
            cached = self._get_cached(cache_key)
            if cached:
                return cached

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": input_text}
        ]

        for attempt in range(self.max_retries):
            try:
                if self.provider == "groq":
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={"type": "json_object"}
                    )
                    content = response.choices[0].message.content

                elif self.provider == "google":
                    response = self.client.generate_content(
                        messages,
                        generation_config={
                            "temperature": self.temperature,
                            "max_output_tokens": self.max_tokens,
                            "response_mime_type": "application/json"
                        }
                    )
                    content = response.text

                elif self.provider == "ollama":
                    response = self.client.chat(
                        model=self.model,
                        messages=messages,
                        options={"temperature": self.temperature, "num_predict": self.max_tokens},
                        format="json"
                    )
                    content = response["message"]["content"]

                result = json.loads(content)
                self._save_cache(cache_key, result)
                return result

            except Exception as e:
                print(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

        return None

    def generate_daily_report(self, raw_report: DailyReport) -> Optional[dict]:
        """Generate structured daily report from parsed Market Notes."""
        # Prepare input for LLM
        notes_text = "\n".join(
            f"- {n.timestamp} {n.text}"
            for n in raw_report.organized_notes
        )

        highlights_text = "\n".join(f"- {h}" for h in raw_report.highlights_for_carry_forward)

        input_data = f"""
DATE: {raw_report.date}
RAW MARKET NOTES:
{notes_text}

REVIEW HIGHLIGHTS:
{highlights_text}
"""

        return self._call_llm(self.daily_report_prompt, input_data)

    def generate_pre_market(self, daily_report: DailyReport, economic_events: list[dict]) -> Optional[dict]:
        """Generate pre-market notes for next trading day."""
        highlights_text = "\n".join(f"- {h}" for h in daily_report.highlights_for_carry_forward)
        notes_text = "\n".join(
            f"- {n.timestamp} {n.text}"
            for n in daily_report.organized_notes[-10:]  # Last 10 notes for context
        )

        events_text = "\n".join(
            f"- {e['time']} {e['event']} ({e['impact']})" + (f" Forecast: {e.get('forecast')}" if e.get('forecast') else "")
            for e in economic_events
        )

        input_data = f"""
DATE: {daily_report.date}
CARRY-FORWARD HIGHLIGHTS:
{highlights_text}

RECENT MARKET NOTES (for context):
{notes_text}

ECONOMIC EVENTS TOMORROW:
{events_text}
"""

        return self._call_llm(self.pre_market_prompt, input_data)


def load_settings() -> dict:
    """Load settings from YAML."""
    import yaml
    config_path = Path("config/settings.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


# --- Fallback: Rule-based extraction without LLM ---

def extract_daily_report_fallback(raw_report: DailyReport) -> dict:
    """
    Rule-based fallback when LLM unavailable.
    Uses parser's organized notes + simple heuristics.
    """
    # Match entries to exits by ticker
    trades = []
    open_trades = {}

    for note in raw_report.organized_notes:
        if "[TRADE:" in note.text:
            # Extract trade info from tag: [TRADE: DIRECTION TICKER [long/short] @ PRICE xSIZE]
            trade_match = note.text.split("[TRADE: ")[-1].rstrip("]")
            parts = trade_match.split()
            if len(parts) >= 5:
                direction_str = parts[0]
                ticker = parts[1]

                # Check if EXIT with exited direction (e.g., "EXIT FTNT long @ 165.85 x2")
                exited_direction = None
                if direction_str.upper() == "EXIT" and len(parts) >= 6 and parts[2].lower() in ("long", "short"):
                    exited_direction = TradeDirection(parts[2].lower())
                    # Shift indices for exit format
                    price_idx = 4  # After: EXIT TICKER long @ PRICE
                    size_idx = 5
                else:
                    # Entry format: "LONG TICKER @ PRICE xSIZE" or "SHORT TICKER @ PRICE xSIZE"
                    price_idx = 3
                    size_idx = 4

                price = 0.0
                if price_idx < len(parts):
                    price_str = parts[price_idx].replace("@", "")
                    try:
                        price = float(price_str)
                    except ValueError:
                        price = 0.0

                size = 0
                if size_idx < len(parts) and parts[size_idx].startswith("x"):
                    try:
                        size = int(parts[size_idx].replace("x", ""))
                    except ValueError:
                        size = 0

                direction = TradeDirection(direction_str.lower())
                reason_idx = size_idx + 1 if size_idx + 1 < len(parts) else len(parts)
                reason = " ".join(parts[reason_idx:]) if reason_idx < len(parts) else ""

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
                    if ticker in open_trades:
                        open_trades[ticker].outcome = TradeStatus.CLOSED
                        open_trades[ticker].exit_timestamp = note.timestamp
                        open_trades[ticker].exit_price = price
                        open_trades[ticker].exit_reason = reason
                        trades.append(open_trades.pop(ticker))
                    else:
                        trades.append(trade)
                else:
                    open_trades[ticker] = trade

    # Add remaining open trades
    for trade in open_trades.values():
        trades.append(trade)

    # Build organized notes without trade tags
    clean_notes = []
    for note in raw_report.organized_notes:
        text = note.text.split(" [TRADE:")[0] if "[TRADE:" in note.text else note.text
        category = note.category
        clean_notes.append(OrganizedNote(
            timestamp=note.timestamp,
            text=text,
            tickers=note.tickers,
            category=category,
            key_levels_mentioned=note.key_levels_mentioned,
            tags=note.tags,
            flag_context=note.flag_context
        ))

    # Use parser's inferred market bias
    market_bias = raw_report.market_bias or MarketBias(
        direction=MarketBiasDirection.UNCLEAR,
        confidence=MarketBiasConfidence.LOW,
        regime=MarketRegime.TRANSITIONAL
    )

    return {
        "organized_notes": [n.model_dump() for n in clean_notes],
        "trades": [t.model_dump() for t in trades],
        "highlights_for_carry_forward": raw_report.highlights_for_carry_forward,
        "market_bias": market_bias.model_dump()
    }


def generate_pre_market_fallback(daily_report: Optional[DailyReport], economic_events: list[dict]) -> dict:
    """Rule-based pre-market generation."""
    import re
    settings = load_settings()
    active_rules = settings.get("active_rules", [])

    if daily_report:
        carry_forward = daily_report.highlights_for_carry_forward[:5]
    else:
        carry_forward = []

    watchlist = []
    # Only add tickers as "Watch TICKER" format
    # Get tickers from carry_forward highlights that have tickers mentioned
    tickers = set()
    if daily_report:
        tickers.update(daily_report.get_tickers_mentioned())
    for t in tickers:
        if re.match(r'^[A-Z]{1,5}$', t):
            watchlist.append(f"Watch {t}")

    return {
        "date": str(daily_report.date) if daily_report else "",
        "carry_forward": carry_forward,
        "economic_events": economic_events,
        "active_rules": active_rules,
        "watchlist_candidates": watchlist[:15]
    }


if __name__ == "__main__":
    # Test with fallback
    from src.core.parser import parse_drc_file
    from pathlib import Path

    vault = Path("C:/Users/Thaddeus/Claude Code Test/trading-journal-system/Vaulted/!Journalit")
    test_file = vault / "2026/Q1/03/W11/DRC-120326.md"
    if test_file.exists():
        raw = parse_drc_file(test_file)
        if raw:
            result = extract_daily_report_fallback(raw)
            print(json.dumps(result, indent=2, default=str))
    else:
        print("Test file not found")