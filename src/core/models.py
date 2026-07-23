"""
Pydantic models for the trading journal system.
"""
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class NoteCategory(str, Enum):
    OBSERVATION = "observation"
    DECISION = "decision"
    ENTRY = "entry"
    EXIT = "exit"
    EMOTION = "emotion"
    SKIP = "skip"


class MarketBiasDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    CHOP = "chop"
    UNCLEAR = "unclear"


class MarketBiasConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MarketRegime(str, Enum):
    HPTE = "HPTE"
    LPTE = "LPTE"
    TRANSITIONAL = "transitional"


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    EXIT = "exit"


class PatternType(str, Enum):
    MISTAKE = "mistake"
    OBSERVATION = "observation"
    SETUP = "setup"
    RULE = "rule"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"


# ============================================================
# Daily Report Models
# ============================================================

class OrganizedNote(BaseModel):
    timestamp: str
    text: str
    tickers: list[str] = Field(default_factory=list)
    category: NoteCategory
    key_levels_mentioned: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)  # #watch, #flag, etc.
    flag_context: int = Field(default=0, description="Number of prior notes to include as context from #flagN tag")


class ExtractedTrade(BaseModel):
    timestamp: str
    direction: TradeDirection
    ticker: str
    price: float
    size: int
    reason: str
    outcome: TradeStatus = TradeStatus.OPEN
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    exited_direction: Optional[TradeDirection] = None  # For EXIT trades: was it closing a LONG or SHORT?


class MarketBias(BaseModel):
    direction: MarketBiasDirection
    confidence: MarketBiasConfidence
    regime: MarketRegime
    key_levels: list[str] = Field(default_factory=list)


class DailyReport(BaseModel):
    date: date
    organized_notes: list[OrganizedNote] = Field(default_factory=list)
    trades: list[ExtractedTrade] = Field(default_factory=list)
    highlights_for_carry_forward: list[str] = Field(default_factory=list)
    market_bias: Optional[MarketBias] = None
    raw_market_notes: str = ""  # Preserve original
    source_file: str = ""

    def get_tickers_mentioned(self) -> set[str]:
        """All unique tickers mentioned in notes."""
        tickers = set()
        for note in self.organized_notes:
            tickers.update(note.tickers)
        for trade in self.trades:
            tickers.add(trade.ticker)
        return tickers

    def get_mistakes(self) -> list[OrganizedNote]:
        """Notes categorized as emotion (FOMO, fear, etc.)"""
        return [n for n in self.organized_notes if n.category == NoteCategory.EMOTION]


# ============================================================
# Pre-Market Models
# ============================================================

class EconomicEvent(BaseModel):
    time: str
    event: str
    impact: Literal["HIGH", "MEDIUM", "LOW"]
    forecast: Optional[str] = None
    prior: Optional[str] = None


class PreMarketNotes(BaseModel):
    model_config = ConfigDict(extra='ignore')

    date: date
    carry_forward: list[str] = Field(default_factory=list)
    economic_events: list[EconomicEvent] = Field(default_factory=list)
    earnings: list[dict] = Field(default_factory=list)  # Major earnings >$50B
    active_rules: list[str] = Field(default_factory=list)
    watchlist_candidates: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


# ============================================================
# Weekly Review Models
# ============================================================

class PatternSuggestion(BaseModel):
    pattern: str
    type: PatternType
    supporting_days: list[date]
    evidence_quotes: list[str]
    frequency: int
    severity_hint: Optional[Literal["critical", "high", "medium", "low"]] = None
    user_confirmed: bool = False
    user_dismissed: bool = False
    user_renamed: Optional[str] = None


class SetupPerformance(BaseModel):
    setup: str
    market_condition: str
    trades: int
    wins: int
    notes: Optional[str] = None


class MarketConditionTracking(BaseModel):
    date: date
    predicted: str
    actual: str
    correct: bool


class WeeklyReview(BaseModel):
    week: str  # "W11"
    date_range: tuple[date, date]
    daily_reports: list[DailyReport] = Field(default_factory=list)
    pattern_suggestions: list[PatternSuggestion] = Field(default_factory=list)
    setup_performance: list[SetupPerformance] = Field(default_factory=list)
    market_condition_tracking: list[MarketConditionTracking] = Field(default_factory=list)
    metric_updates: dict[str, list[dict]] = Field(default_factory=dict)
    user_notes: str = ""


# ============================================================
# Monthly Models
# ============================================================

class PatternEvolution(BaseModel):
    pattern: str
    trend: Literal["resolving", "resolved", "strengthening", "emerging", "stable"]
    weekly_frequency: str
    rule_adopted: Optional[str] = None


class MonthlyTrajectory(BaseModel):
    month: str  # "2026-03"
    summary: str
    key_metrics: dict[str, Any]
    pattern_evolution: list[PatternEvolution] = Field(default_factory=list)
    setup_performance: dict[str, dict] = Field(default_factory=dict)
    focus_areas_next_month: list[str] = Field(default_factory=list)


# ============================================================
# Metric Tracking
# ============================================================

class MetricPoint(BaseModel):
    date: date
    value: float | int
    notes: Optional[str] = None


class MetricSeries(BaseModel):
    metric: str
    description: str
    active: bool = True
    series: list[MetricPoint] = Field(default_factory=list)

    def add_point(self, date: date, value: float | int, notes: str = ""):
        self.series.append(MetricPoint(date=date, value=value, notes=notes))


# ============================================================
# Configuration Models
# ============================================================

class LLMSettings(BaseModel):
    provider: Literal["groq", "google", "ollama"] = "groq"
    model: str = "llama-3.1-70b-versatile"
    api_key_env: str = "GROQ_API_KEY"
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout_seconds: int = 30


class VaultSettings(BaseModel):
    path: Path


class EconomicCalendarSettings(BaseModel):
    enabled: bool = True
    source: Literal["static", "fred", "alphavantage"] = "static"
    major_events_only: bool = True


class Settings(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vault: VaultSettings = Field(default_factory=lambda: VaultSettings(path=Path("vault")))
    economic_calendar: EconomicCalendarSettings = Field(default_factory=EconomicCalendarSettings)
    output_dir: Path = Path("data")
    cache_dir: Path = Path("data/cache/llm")
    prompts_dir: Path = Path("config/prompts")
    fmp_api_key_env: str = "FMP_API_KEY"
    alphavantage_api_key_env: str = "ALPHA_VANTAGE_API_KEY"
    earnings_min_market_cap: int = 50_000_000_000