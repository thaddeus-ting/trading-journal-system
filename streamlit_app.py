import streamlit as st
import json
import re
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file for API keys
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core.models import (
    DailyReport, PreMarketNotes, OrganizedNote, ExtractedTrade,
    MarketBias, WeeklyReview, PatternSuggestion,
    NoteCategory, TradeDirection, TradeStatus, MarketBiasDirection,
    PatternType
)

# LLM extractor for AI summary
from src.core.extractor import LLMExtractor

# Page config
st.set_page_config(
    page_title="Trading Journal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load settings early for data directories
SETTINGS_FILE = Path("config/settings.yaml")
if SETTINGS_FILE.exists():
    settings = yaml.safe_load(SETTINGS_FILE.read_text())
else:
    settings = {}

# Data directories from settings
data_locations = settings.get("data_locations", {})
DATA_DIR = Path(data_locations.get("data_dir", "data"))
DAILY_DIR = DATA_DIR / data_locations.get("daily_reports_dir", "daily_reports")
PRE_DIR = DATA_DIR / data_locations.get("pre_market_dir", "pre_market")
WEEKLY_DIR = DATA_DIR / data_locations.get("weekly_reviews_dir", "weekly_reviews")

# ================================
# AI Summary Disk Cache
# ================================
import hashlib

CACHE_DIR = DATA_DIR / "cache" / "summaries"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_VERSION = "v4"  # Increment when you edit the LLM prompt in generate_llm_summary()

def _semantic_key(report: DailyReport) -> str:
    """Generate a deterministic cache key from TAGGED notes + market bias + prompt version.
    Changes to untagged notes do NOT invalidate the cache."""
    tagged = []
    for n in sorted(report.organized_notes, key=lambda x: x.timestamp):
        tags = getattr(n, 'tags', None) or []
        if tags:
            tagged.append((n.timestamp, n.category.value, n.text, tuple(sorted(tags))))
    bias = report.market_bias
    bias_data = (bias.direction.value, bias.confidence.value, bias.regime.value, tuple(bias.key_levels)) if bias else None
    data = json.dumps((PROMPT_VERSION, tagged, bias_data), sort_keys=True).encode()
    return hashlib.md5(data).hexdigest()

def get_cached_summary(report: DailyReport) -> str | None:
    """Return cached summary if exists, else None."""
    key = _semantic_key(report)
    cache_file = CACHE_DIR / f"{key}.txt"
    if cache_file.exists():
        try:
            return cache_file.read_text(encoding="utf-8")
        except Exception:
            return None
    return None

def save_summary_cache(report: DailyReport, summary: str):
    """Save summary to disk cache."""
    key = _semantic_key(report)
    cache_file = CACHE_DIR / f"{key}.txt"
    try:
        cache_file.write_text(summary, encoding="utf-8")
    except Exception:
        pass  # Cache write failures are non-fatal

# Tag color constants (module-level to avoid duplication)
TAG_COLORS = {
    "watch": "#1f77b4", "flag": "#d62728", "qn": "#ff7f0e",
    "impt": "#9467bd", "task": "#2ca02c", "review": "#8c564b",
    "todo": "#e377c2", "note": "#7f7f7f", "idea": "#17becf",
    "setup": "#bcbd22", "mistake": "#d62728", "good": "#2ca02c",
    "bad": "#d62728", "emotion": "#ff7f0e", "sector": "#795548",
    "gold": "#ffd700", "ptrade": "#4caf50"
}

TAG_EMOJI = {
    "watch": "🔵", "flag": "🔴", "qn": "❓", "impt": "⭐",
    "task": "✅", "review": "🔍", "todo": "📋", "note": "📝",
    "idea": "💡", "setup": "📐", "mistake": "❌", "good": "✅",
    "bad": "❌", "emotion": "🟠", "sector": "🏭", "gold": "🏆", "ptrade": "📝"
}

# ================================
# Data Loading Functions
# ================================

@st.cache_data(ttl=300)
def load_daily_reports() -> list[DailyReport]:
    """Load all daily reports."""
    reports = []
    for f in sorted(DAILY_DIR.glob("*.json")):
        # Skip pretty JSON files - they have a different structure
        if f.name.endswith("_pretty.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            reports.append(DailyReport.model_validate(data))
        except Exception as e:
            st.error(f"Error loading {f.name}: {e}")
    return reports

@st.cache_data(ttl=300, show_spinner=False)
def load_pre_market(target_date: date) -> PreMarketNotes | None:
    """Load pre-market notes for a date."""
    path = PRE_DIR / f"{target_date.isoformat()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    # Ensure all fields exist with defaults (Pydantic v2 handles this automatically)
    return PreMarketNotes.model_validate(data)

@st.cache_data(ttl=300)
def load_weekly_reviews() -> list[WeeklyReview]:
    """Load all weekly reviews."""
    reviews = []
    for f in sorted(WEEKLY_DIR.glob("W*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            reviews.append(WeeklyReview.model_validate(data))
        except Exception as e:
            st.error(f"Error loading {f.name}: {e}")
    return reviews

# ================================
# UI Components
# ================================

# Inject custom CSS for larger headers, tabs
st.markdown("""
<style>
/* Larger section headers (expanders) */
[data-testid="stExpander"] summary {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
}

/* Larger tab labels */
[data-testid="stTabs"] button {
    font-size: 1.05rem !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
}

/* Larger main headers */
h1 { font-size: 2.2rem !important; }
h2 { font-size: 1.8rem !important; }
h3 { font-size: 1.4rem !important; }

/* Reduce sidebar title font size */
[data-testid="stSidebar"] h1 {
    font-size: 1.5rem !important;
}
</style>
""", unsafe_allow_html=True)


def render_daily_report(report: DailyReport):
    """Render a complete daily report."""
    # Market Bias emoji for header
    bias_emoji = ""
    if report.market_bias:
        bias = report.market_bias
        bias_emoji = {
            MarketBiasDirection.BULLISH: "🟢",
            MarketBiasDirection.BEARISH: "🔴",
            MarketBiasDirection.CHOP: "🟡",
            MarketBiasDirection.UNCLEAR: "⚪"
        }.get(bias.direction, "⚪")

    st.header(f"📊 Daily Report — {report.date}  {bias_emoji}")
    st.markdown('<div style="margin-top: 2.5rem;"></div>', unsafe_allow_html=True)

    # Session Summary - AI/rule-based synthesis
    render_ai_summary(report)
    st.markdown('<hr style="margin: 1rem 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)

    # Carry-Forward Highlights, Metrics in row
    col1, col2 = st.columns([2, 1])

    with col1:
        if report.highlights_for_carry_forward:
            st.markdown("**Carry-Forward Highlights:**")
            for h in report.highlights_for_carry_forward:
                st.markdown(f"- {h}")

    # Tabs with counts in brackets
    notes_count = len(report.organized_notes)
    tags = set()
    for n in report.organized_notes:
        tags.update(getattr(n, 'tags', []) or [])
    tags_count = len(tags)
    trades_count = len(report.trades)
    highlights_count = len(report.highlights_for_carry_forward)
    pred_count = sum(1 for n in report.organized_notes if 'gold' in (getattr(n, 'tags', []) or []) or 'ptrade' in (getattr(n, 'tags', []) or []))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"📝 Notes ({notes_count})",
        f"🏷️ Tags ({tags_count})",
        f"💰 Trades ({trades_count})",
        f"🎯 Highlights ({highlights_count})",
        f"📊 Scorecard ({pred_count})"
    ])

    with tab1:
        render_notes_tab(report)

    with tab2:
        render_tags_tab(report)

    with tab3:
        render_trades_tab(report)

    with tab4:
        render_highlights_tab(report)

    with tab5:
        render_prediction_scorecard_daily(report)


def render_tags_tab(report: DailyReport):
    """Render tags and associated notes - matches Notes tab format with single expander per tag."""
    all_tags = {}
    for note in report.organized_notes:
        tags = getattr(note, 'tags', []) or []
        for tag in tags:
            if tag not in all_tags:
                all_tags[tag] = []
            all_tags[tag].append(note)

    if not all_tags:
        st.info("No tags found in notes")
        return

    for tag, notes in sorted(all_tags.items()):
        emoji = TAG_EMOJI.get(tag.lower(), "🏷️")
        count_str = f"({len(notes)} notes)"

        # Single expander with emoji in title (matches Notes tab format)
        with st.expander(f"{emoji} **#{tag}**  {count_str}", expanded=False):
            for i, note in enumerate(notes):
                # Clean note text - remove [TRADE:...] only
                clean_text = re.sub(r'\s*\[TRADE:[^\]]*\]\s*', ' ', note.text).strip()
                clean_text = re.sub(r'\s{2,}', ' ', clean_text).strip()

                # Strip ALL #tags from text for display (tags shown as badges)
                display_text = re.sub(r'\s*#\w+', '', clean_text).strip()
                display_text = re.sub(r'\s{2,}', ' ', display_text).strip()

                # Blank line separator between notes (not before first)
                if i > 0:
                    st.markdown('<div style="margin: 8px 0;"></div>', unsafe_allow_html=True)

                # Format tag badges (colored pills)
                tag_badges = ""
                if note.tags:
                    badges = []
                    for t in note.tags:
                        color = TAG_COLORS.get(t.lower(), "#6c757d")
                        badges.append(f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 4px;">#{t}</span>')
                    tag_badges = " ".join(badges)

                # Display note with white timestamp
                st.markdown(f"""
                <div style="padding-left: 4px; margin: 4px 0;">
                    <strong style="color:#ffffff;">{note.timestamp}</strong>  {display_text} {tag_badges}
                </div>
                """, unsafe_allow_html=True)

                # If this note has flag_context > 0, show expanded context
                flag_context = getattr(note, 'flag_context', 0)
                if flag_context and flag_context > 1:
                    # Find prior notes in the same day (by timestamp order)
                    note_idx = report.organized_notes.index(note)
                    if note_idx > 0:
                        context_notes = report.organized_notes[max(0, note_idx - flag_context + 1):note_idx]
                        if context_notes:
                            color = TAG_COLORS.get(tag.lower(), "#6c757d")
                            st.markdown(f'<div style="margin-left: 20px; margin-top: 4px; padding-left: 8px; border-left: 2px solid {color};">', unsafe_allow_html=True)
                            st.caption(f"📎 Flag context ({len(context_notes)} prior {'note' if len(context_notes) == 1 else 'notes'}):")
                            for ctx_note in context_notes:
                                ctx_text = re.sub(r'\s*\[TRADE:[^\]]*\]\s*', ' ', ctx_note.text).strip()
                                ctx_text = re.sub(r'\s*#\w+', '', ctx_text).strip()
                                st.markdown(f'<div style="color: #aaa; font-size: 0.9em; margin: 2px 0;">{ctx_note.timestamp} — {ctx_text}</div>', unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)


# ================================
# LLM-based AI Summary
# ================================

def render_ai_summary(report: DailyReport):
    """Generate AI summary using LLM (Groq/Ollama/Google) - force AI when key available. Uses cache to avoid repeated calls."""
    if not report.organized_notes and not report.trades:
        st.caption("No data to summarize")
        return

    # Build context from report
    # Only include non-trade-execution notes (exclude entry/exit categories)
    filtered_notes = [n for n in report.organized_notes if n.category.value not in ("entry", "exit")]
    notes_lines = []
    for n in filtered_notes:
        tags_str = f" [tags: {', '.join(n.tags)}]" if getattr(n, 'tags', None) else ""
        notes_lines.append(f"[{n.timestamp}] {n.category.value}: {n.text}{tags_str}")
    notes_text = "\n".join(notes_lines)
    bias_text = ""
    if report.market_bias:
        b = report.market_bias
        bias_text = f"Market Bias: {b.direction.value} ({b.confidence.value} confidence, {b.regime.value} regime)"

    # Load previous day's pre-market notes for context
    pre_market_context = ""
    try:
        prev_date = report.date - timedelta(days=1)
        # Skip weekends
        while prev_date.weekday() > 4:  # 5=Sat, 6=Sun
            prev_date -= timedelta(days=1)
        pre = load_pre_market(prev_date)
        if pre:
            parts = []
            if pre.carry_forward:
                parts.append("Carry-forward: " + "; ".join(pre.carry_forward[:3]))
            if pre.watchlist_candidates:
                parts.append("Watchlist: " + ", ".join(pre.watchlist_candidates[:5]))
            if pre.active_rules:
                parts.append("Rules: " + "; ".join(pre.active_rules[:3]))
            pre_market_context = " | ".join(parts)
    except Exception:
        pre_market_context = ""

    # Check if user disabled LLM API calls in settings
    if st.session_state.get("disable_llm", False):
        st.info("🔧 LLM disabled in Settings — using rule-based summary")
        render_rule_based_summary(report, notes_text, bias_text)
        return

    config_path = Path("config/settings.yaml")
    if not config_path.exists():
        st.warning("⚠️ Config not found — using rule-based summary")
        render_rule_based_summary(report, notes_text, bias_text)
        return

    settings = yaml.safe_load(config_path.read_text())

    # Check if API key is available - if so, FORCE AI
    api_key_env = settings.get("llm", {}).get("api_key_env", "GROQ_API_KEY")
    api_key = os.environ.get(api_key_env)

    if not api_key:
        st.warning(f"⚠️ {api_key_env} not set — using rule-based summary")
        render_rule_based_summary(report, notes_text, bias_text)
        return

    # Check disk cache first (persists across restarts)
    cached = get_cached_summary(report)
    if cached:
        st.subheader("🤖 AI-Generated Summary")
        st.write(cached)
        st.caption("💾 Cached")
        return

    # API key present - generate AI summary
    with st.spinner("Generating AI summary..."):
        try:
            extractor = LLMExtractor(settings)
            summary = generate_llm_summary(extractor, notes_text, bias_text, pre_market_context)

            if summary:
                save_summary_cache(report, summary)
                st.subheader("🤖 AI-Generated Summary")
                st.write(summary)
            else:
                st.warning("AI returned empty — using rule-based fallback")
                render_rule_based_summary(report, notes_text, bias_text)
        except Exception as e:
            st.error(f"LLM error: {e} — using rule-based fallback")
            render_rule_based_summary(report, notes_text, bias_text)


def generate_llm_summary(extractor: LLMExtractor, notes_text: str, bias_text: str, pre_market_context: str = "") -> str:
    """Call LLM to generate structured session summary."""
    prompt = f"""You are a trading performance coach. Write a concise, synthesized summary of THIS trading session.

{bias_text}

PREVIOUS DAY PRE-MARKET CONTEXT (reference only):
{pre_market_context if pre_market_context else "None provided"}

TODAY'S TAGGED NOTES:
{notes_text if notes_text else "No tagged notes"}

CRITICAL: ONLY use notes that have tags in [tags: ...]. Ignore ALL untagged notes completely.
Priority tags (highest to lowest): #flag > #gold > #ptrade > #mistake > #impt > #qn > #setup > #emotion > #watch > #task > #todo > #review > #note > #idea > #sector > #bad > #good

Write a summary as BULLET POINTS covering:
• 2-3 synthesized observations grouping related tagged notes by theme
• ONE specific, actionable command for tomorrow

Rules:
- SYNTHESIZE: Combine related notes into themes. Don't just copy each note verbatim.
- If multiple notes mention the same ticker/theme (e.g., PANW, sector rotation), merge them into ONE bullet citing the key insight.
- Cite tickers, times, or exact behaviors from the notes as evidence.
- Be specific and actionable — avoid generic statements like "review trades" or "manage risk."
- If no tagged notes exist, output: "No tagged notes to review."
- Output as plain text bullet points only (no headers, no markdown, no bold/italic)
- Each bullet = one observation or action
- Action bullet MUST start with "Action: " followed by ONE short imperative sentence

EXAMPLE — Good output:
• Sector rotation: Big-money flows shifted from cybersecurity (PANW lagging RDDT/AAPL) to new themes every 4-5 days (#flag #impt at 10:05, #flag #qn at 11:11)
• FOMO entries on LPTE days without pullback confirmation led to quick stops (#flag at 11:40)

Action: Wait for M5 pullback close before entering longs on range-bound days

EXAMPLE — Bad output (what to avoid):
• 10:05 observation: Big-money flows shift every 4-5 days... #flag #impt
• 11:11 observation: PANW is underperforming relative to RDDT and AAPL... #flag #qn
• Action: Review PANW's recent price and news data versus RDDT and AAPL before taking any related trades tomorrow.

"""

    try:
        if extractor.provider == "groq":
            response = extractor.client.chat.completions.create(
                model=extractor.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=extractor.temperature,
                max_tokens=extractor.max_tokens
            )
            return response.choices[0].message.content
        elif extractor.provider == "google":
            response = extractor.client.generate_content(prompt)
            return response.text
        elif extractor.provider == "ollama":
            response = extractor.client.generate(
                model=extractor.model,
                prompt=prompt,
                options={"temperature": extractor.temperature}
            )
            return response.get("response", "")
    except Exception as e:
        return f"Error: {e}"


def render_rule_based_summary(report: DailyReport, notes_text: str, bias_text: str):
    """Fallback rule-based summary when LLM unavailable."""
    note_texts = [n.text.lower() for n in report.organized_notes]
    all_text = " ".join(note_texts)

    # Count categories
    cat_counts = {}
    for n in report.organized_notes:
        cat = n.category.value
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Trade analysis
    closed_trades = [t for t in report.trades if t.outcome == TradeStatus.CLOSED and t.exit_price and t.price > 0]
    wins = 0
    for t in closed_trades:
        if t.direction == TradeDirection.LONG and t.exit_price > t.price:
            wins += 1
        elif t.direction == TradeDirection.SHORT and t.exit_price < t.price:
            wins += 1
    win_rate = f"{wins}/{len(closed_trades)} ({wins/len(closed_trades)*100:.0f}%)" if closed_trades else "—"

    # Pattern detection
    patterns = []
    if any("oversiz" in t or "chase" in t or "fomo" in t for t in note_texts):
        patterns.append("⚠️ **Sizing/Chasing** — Multiple entries mention oversizing or chasing")
    if any("early exit" in t or "cut winner" in t or "took profit early" in t for t in note_texts):
        patterns.append("📉 **Early Exits** — Cutting winners mentioned")
    if any("stop" in t and ("hit" in t or "taken" in t) for t in note_texts):
        patterns.append("🛑 **Stops Hit** — Multiple stops triggered")
    if any("vwap" in t for t in note_texts):
        patterns.append("📊 **VWAP Focus** — VWAP referenced as key level")
    if cat_counts.get("emotion", 0) > 0:
        patterns.append(f"🧠 **Emotion Notes** — {cat_counts['emotion']} emotion/mistake entries")
    if cat_counts.get("decision", 0) > 0:
        patterns.append(f"🤔 **Decision Points** — {cat_counts['decision']} deliberate decisions logged")

    # Watch/flag tracking
    watch_tags = sum(1 for n in report.organized_notes if "watch" in (getattr(n, 'tags', []) or []))
    flag_tags = sum(1 for n in report.organized_notes if "flag" in (getattr(n, 'tags', []) or []))

    # Render
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Session Scorecard**")
        st.markdown(f"- **Trades**: {len(report.trades)} total | {win_rate} win rate")
        st.markdown(f"- **Notes**: {len(report.organized_notes)} total ({cat_counts.get('entry',0)} entries, {cat_counts.get('exit',0)} exits, {cat_counts.get('observation',0)} observations)")
        st.markdown(f"- **Watchlist**: {watch_tags} tagged #watch | **Flags**: {flag_tags} tagged #flag")

    with col2:
        st.markdown("**Patterns for Review**")
        if patterns:
            for p in patterns:
                st.markdown(f"- {p}")
        else:
            st.markdown("- No clear patterns detected")

        st.markdown("**Suggested Review Topics**")
        if closed_trades:
            st.markdown("- Compare exit reasoning vs actual outcome on closed trades")
        if cat_counts.get("entry", 0) > 0:
            st.markdown("- Entry quality: Were setups A-grade or forced?")
        if any("earnings" in t or "news" in t for t in note_texts):
            st.markdown("- Event-driven trades: How did catalyst plays work?")
        if cat_counts.get("emotion", 0) > 0:
            st.markdown("- Emotion log: What triggered each flag? Pattern?")
        st.markdown("- Next session: What's the one setup rule to enforce?")


def render_notes_tab(report: DailyReport):
    """Render organized notes in clean card layout."""
    if not report.organized_notes:
        st.info("No organized notes for this day.")
        return

    # Category order and styling - decision + observation combined
    cat_order = ["entry", "exit", "decision_observation", "emotion", "skip"]
    cat_config = {
        "entry": {"icon": "🟢", "title": "Entries", "color": "#28a745"},
        "exit": {"icon": "🔴", "title": "Exits", "color": "#dc3545"},
        "decision_observation": {"icon": "🔵", "title": "Analysis", "color": "#007bff"},
        "emotion": {"icon": "🟠", "title": "Emotion / Mistakes", "color": "#fd7e14"},
        "skip": {"icon": "⚪", "title": "Skipped", "color": "#6c757d"}
    }

    # Group by category - merge decision and observation
    # Also re-categorize notes that are clearly exits but mislabeled as entry/observation
    cat_groups = {}
    for note in report.organized_notes:
        cat = note.category.value

        # Fix mis-categorized exits: if text starts with "exit" or contains "exit " followed by ticker pattern
        if cat in ["entry", "observation"]:
            text_lower = note.text.lower().strip()
            # Check if this is actually an exit note
            if text_lower.startswith("exit ") or " exit " in text_lower[:30]:
                cat = "exit"
            elif cat in ["decision", "observation"]:
                cat = "decision_observation"

        if cat in ["decision", "observation"]:
            cat = "decision_observation"

        if cat not in cat_groups:
            cat_groups[cat] = []
        cat_groups[cat].append(note)

    # Render each category
    for cat in cat_order:
        if cat not in cat_groups and cat not in ["entry", "exit"]:
            continue
        elif cat in ["entry", "exit"] and cat not in cat_groups:
            # Always show Entries and Exits sections even if empty (show 0)
            notes = []
            cfg = cat_config[cat]
            count_str = "(0)"

            empty_messages = {
                "entry": "No entries logged this session",
                "exit": "No exits logged this session"
            }
            msg = empty_messages.get(cat, f"No {cat} notes logged this session")

            with st.expander(f"{cfg['icon']} **{cfg['title']}**  {count_str}", expanded=False):
                st.caption(msg)
            continue

        notes = cat_groups[cat]
        cfg = cat_config[cat]
        count_str = f"({len(notes)})"

        with st.expander(f"{cfg['icon']} **{cfg['title']}**  {count_str}", expanded=(cat in ["entry", "exit", "emotion"])):
            for i, note in enumerate(notes):
                # Clean note text - remove [TRADE:...] only
                clean_text = re.sub(r'\s*\[TRADE:[^\]]*\]\s*', ' ', note.text).strip()
                clean_text = re.sub(r'\s{2,}', ' ', clean_text).strip()

                # Remove leading dash/space from comments (the " - " separator or leading dash)
                # Split on " - " and keep the part after it if it looks like a comment
                if " - " in clean_text:
                    parts = clean_text.split(" - ", 1)
                    if len(parts) == 2:
                        # Check if first part looks like a trade/action (has ticker)
                        # If so, show both parts but without the " - " separator
                        clean_text = f"{parts[0]} — {parts[1]}"

                # Remove leading space if present
                clean_text = clean_text.lstrip()

                # Format tags as visual badges
                tag_badges = ""
                if note.tags:
                    badges = []
                    for tag in note.tags:
                        color = TAG_COLORS.get(tag.lower(), "#6c757d")
                        badges.append(f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 4px;">#{tag}</span>')
                    tag_badges = " ".join(badges)

                # Strip #tags from clean_text for display (tags shown as badges instead)
                display_text = re.sub(r'\s*#\w+', '', clean_text).strip()
                display_text = re.sub(r'\s{2,}', ' ', display_text).strip()

                # Blank line separator between notes (except first)
                if i > 0:
                    st.markdown('<div style="margin: 8px 0;"></div>', unsafe_allow_html=True)

                # Display note with white timestamp for all categories
                st.markdown(f"""
                <div style="padding-left: 4px; margin: 4px 0;">
                    <strong style="color: #ffffff;">{note.timestamp}</strong>  {display_text} {tag_badges}
                </div>
                """, unsafe_allow_html=True)

            # Show warning if too many notes collapsed
            if len(notes) > 5 and cat not in ["entry", "exit", "emotion"]:
                st.caption(f"{len(notes)} notes — click to expand")

    # Gold Mine Section — highlight all #gold tagged notes
    gold_notes = [n for n in report.organized_notes if "gold" in (getattr(n, 'tags', []) or [])]
    if gold_notes:
        with st.expander(f"🏆 **Gold Mine**  ({len(gold_notes)} {'note' if len(gold_notes) == 1 else 'notes'})", expanded=True):
            st.caption("Key insights flagged for review — predictions, setups spotted, and valuable observations")
            for i, note in enumerate(gold_notes):
                clean_text = re.sub(r'\s*\[TRADE:[^\]]*\]\s*', ' ', note.text).strip()
                clean_text = re.sub(r'\s{2,}', ' ', clean_text).strip()
                clean_text = clean_text.lstrip()

                # Format all tags as badges
                tag_badges = ""
                if note.tags:
                    badges = []
                    for tag in note.tags:
                        color = TAG_COLORS.get(tag.lower(), "#6c757d")
                        badges.append(f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 4px;">#{tag}</span>')
                    tag_badges = " ".join(badges)

                if i > 0:
                    st.markdown('<div style="margin: 8px 0;"></div>', unsafe_allow_html=True)

                st.markdown(f"""
                <div style="padding-left: 4px; margin: 4px 0; border-left: 3px solid #ffd700; padding-left: 10px;">
                    <strong style="color:#ffffff;">{note.timestamp}</strong>  {clean_text} {tag_badges}
                </div>
                """, unsafe_allow_html=True)


def find_existing_trade_file(trade: ExtractedTrade, target_date: date, vault_base: Path) -> Path | None:
    """Find existing Journalit trade file for this trade."""
    year = target_date.year
    quarter = (target_date.month - 1) // 3 + 1
    week_num = target_date.isocalendar()[1]
    week_folder = f"W{week_num:02d}"
    month = target_date.month

    trades_dir = vault_base / str(year) / f"Q{quarter}" / f"{month:02d}" / week_folder / "trades"
    if not trades_dir.exists():
        return None

    # Look for matching file: TICKER-DDMMYY-T#.md
    date_str = target_date.strftime('%d%m%y')
    pattern = f"{trade.ticker}-{date_str}-T*.md"
    matches = list(trades_dir.glob(pattern))
    return matches[0] if matches else None


def render_trades_tab(report: DailyReport):
    """Render trades DataFrame with action buttons."""
    if not report.trades:
        st.info("No trades extracted for this day.")
        return

    # Load settings for vault path
    config_path = Path("config/settings.yaml")
    vault_base = Path("C:/Users/Thaddeus/OneDrive/Desktop/Vaulted/!Journalit")
    if config_path.exists():
        settings = yaml.safe_load(config_path.read_text())
        vault_path = settings.get("vault_path", "")
        if vault_path:
            vault_base = Path(vault_path)

    st.markdown("**📋 Trades for this session**")

    df_data = []
    trade_objects = []
    for t in report.trades:
        pnl = 0
        pnl_pct = 0
        if t.exit_price and t.price > 0:
            if t.direction == TradeDirection.LONG:
                pnl = (t.exit_price - t.price) / t.price * 100
            elif t.direction == TradeDirection.SHORT:
                pnl = (t.price - t.exit_price) / t.price * 100

        existing_file = find_existing_trade_file(t, report.date, vault_base)

        # Format trade like comment for dropdown: "11:22 long CSCO @ 122, 2 shares" or "12:20 exit CSCO @ 120, 1 share"
        if t.exit_price:
            trade_display = f"{t.timestamp} exit {t.ticker} @ {t.exit_price:.2f}, {int(t.size)} share{'s' if t.size != 1 else ''}"
        else:
            dir_str = t.direction.value.lower()
            trade_display = f"{t.timestamp} {dir_str} {t.ticker} @ {t.price:.2f}, {int(t.size)} share{'s' if t.size != 1 else ''}"

        dir_cap = t.direction.value.capitalize()  # "Long" / "Short"

        df_data.append({
            "Time": t.timestamp,
            "Direction": dir_cap,
            "Ticker": t.ticker,
            "Entry": f"${t.price:.2f}" if t.price > 0 else "—",
            "Exit": f"${t.exit_price:.2f}" if t.exit_price else "—",
            "Size": int(t.size) if t.size > 0 else "—",
            "P&L %": f"{pnl:+.2f}%" if pnl != 0 else "—",
            "Status": f"{t.outcome.value}{' @ ' + t.exit_timestamp if t.exit_timestamp else ''}",
            "HasFile": "✅" if existing_file else "❌",
        })
        trade_objects.append((t, existing_file, trade_display))

    df = pd.DataFrame(df_data)

    # Display table
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Time": st.column_config.TextColumn(width="small"),
            "Direction": st.column_config.TextColumn(width="small"),
            "Ticker": st.column_config.TextColumn(width="small"),
            "Entry": st.column_config.TextColumn(width="small"),
            "Exit": st.column_config.TextColumn(width="small"),
            "Size": st.column_config.TextColumn(width="small"),
            "P&L %": st.column_config.TextColumn(width="small"),
            "Status": st.column_config.TextColumn(width="medium"),
            "HasFile": st.column_config.TextColumn(width="small"),
        }
    )

    # Center table content
    st.markdown("""
    <style>
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { text-align: center; }
    </style>
    """, unsafe_allow_html=True)

    # Action buttons below table
    if trade_objects:
        st.markdown("---")
        st.markdown("**Add Trade to Journalit:**")
        col1, col2 = st.columns([3, 1])
        with col1:
            trade_labels = [td for _, _, td in trade_objects]
            selected_idx = st.selectbox("Select trade:", range(len(trade_labels)), format_func=lambda i: trade_labels[i], key="trade_select")
        with col2:
            st.write("")  # vertical align
            st.write("")
            selected_trade, selected_file, _ = trade_objects[selected_idx]
            if selected_trade.direction in (TradeDirection.LONG, TradeDirection.SHORT):
                label = "✏️ Update Trade File" if selected_file else "➕ Create Trade File"
                if st.button(label, key="trade_action_btn", use_container_width=True, type="primary"):
                    create_or_update_trade_file(selected_trade, report.date)
                    st.success(f"Trade file {'updated' if selected_file else 'created'}!")
                    st.rerun()

    # Trade summary
    closed = [t for t in report.trades if t.outcome == TradeStatus.CLOSED]
    if closed:
        wins = sum(1 for t in closed if t.exit_price and t.price > 0 and
                   ((t.direction == TradeDirection.LONG and t.exit_price > t.price) or
                    (t.direction == TradeDirection.SHORT and t.exit_price < t.price)))
        st.metric("Win Rate", f"{wins}/{len(closed)} ({wins/len(closed)*100:.0f}%)")


def render_highlights_tab(report: DailyReport):
    """Render carry-forward highlights."""
    if not report.highlights_for_carry_forward:
        st.info("No highlights for carry-forward.")
        return

    for h in report.highlights_for_carry_forward:
        # Classify highlight type
        if h.startswith("Market context:"):
            st.markdown(f"📊 **Market Context:** {h[15:]}")
        elif h.startswith("Focus:"):
            st.markdown(f"🎯 **Focus:** {h[6:]}")
        elif h.startswith("Improve:"):
            st.markdown(f"📈 **Improve:** {h[8:]}")
        elif h.startswith("Strength:"):
            st.markdown(f"💪 **Strength:** {h[9:]}")
        elif h.startswith("Rule:"):
            st.markdown(f"📜 **Rule:** {h[5:]}")
        else:
            st.markdown(f"• {h}")


def render_pre_market(pre: PreMarketNotes):
    """Render pre-market notes in a nice format."""
    if not pre.carry_forward and not pre.economic_events and not pre.active_rules and not pre.watchlist_candidates:
        st.info("No pre-market data available")
        return

    # Check if this pre-market was generated without a prior daily report
    # Look through ALL carry_forward items for the "no prior daily" marker
    has_prior_daily = True
    for item in pre.carry_forward:
        if "No prior daily journal" in item and "showing economic events only" in item:
            has_prior_daily = False
            break

    st.markdown("""
    <style>
    /* Pre-market page visual improvements - use thin lines instead of boxes */
    .premarket-section {
        margin-bottom: 0.25rem;
        padding-bottom: 0.25rem;
    }
    .premarket-section:last-child {
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .premarket-section h3 {
        margin-top: 0 !important;
        margin-bottom: 0.4rem !important;
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        color: #e0e0e0 !important;
    }
    .stMarkdown {
        line-height: 1.6;
    }
    /* Reduce space before watchlist section and ensure left alignment */
    .watchlist-section {
        margin-top: 0;
    }
    .watchlist-table {
        width: 100%;
        max-width: 100%;
        margin-left: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Carry-Forward
    if pre.carry_forward:
        st.markdown('<div class="premarket-section">', unsafe_allow_html=True)
        st.markdown("### 📋 Carry-Forward from Yesterday")
        for item in pre.carry_forward:
            st.markdown(f"> {item}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Economic Events
    if pre.economic_events:
        st.markdown('<hr style="margin: 0.1rem 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)
        st.markdown('<div class="premarket-section">', unsafe_allow_html=True)
        st.markdown("### 📅 Economic Events")
        for e in pre.economic_events:
            impact_color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(e.impact, "⚪")
            st.markdown(f"{impact_color} **{e.time}** — {e.event}")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<hr style="margin: 0.25rem 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)
        st.markdown('<div class="premarket-section">', unsafe_allow_html=True)
        st.caption("No economic events today")
        st.markdown('</div>', unsafe_allow_html=True)

    # Earnings (Major companies >$50B)
    earnings = getattr(pre, "earnings", [])
    if earnings:
        st.markdown('<div class="premarket-section">', unsafe_allow_html=True)
        st.markdown("### 💰 Major Earnings (>$50B Market Cap)")
        for e in pre.earnings[:10]:
            symbol = e.get("symbol", "")
            name = e.get("name", "")
            mcap = e.get("marketCap", 0) / 1e9
            time_str = e.get("time", "BMO")
            eps_est = e.get("epsEstimated")
            extra = f" | Est EPS: {eps_est}" if eps_est is not None else ""
            st.markdown(f"📊 **{symbol}** — {name} (${mcap:.0f}B) {time_str}{extra}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Active Rules
    if pre.active_rules:
        st.markdown('<hr style="margin: 0.25rem 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)
        st.markdown('<div class="premarket-section">', unsafe_allow_html=True)
        st.markdown("### 📜 Active Rules")
        for r in pre.active_rules:
            st.markdown(f"• {r}")
        st.markdown('</div>', unsafe_allow_html=True)

    # Watchlist Candidates - only show if we have a prior daily report AND valid watchlist items
    # First, filter valid tickers from watchlist_candidates
    valid_longs = []
    valid_shorts = []
    if has_prior_daily and pre.watchlist_candidates:
        for w in pre.watchlist_candidates:
            # Skip non-ticker items (Focus:, Improve:, Rule:, Strength:, Market context:, Bias:, SPY key levels:)
            skip_prefixes = ("Focus:", "Improve:", "Rule:", "Strength:", "Market context:", "Bias:", "SPY key levels:")
            if w.startswith(skip_prefixes):
                continue
            # Extract ticker from "Watch TICKER" or "Watch TICKER (Earnings BMO/AMC)"
            if w.startswith("Watch "):
                ticker_part = w[6:].strip()
                # Handle "Watch TICKER (Earnings BMO/AMC)" format
                if "(" in ticker_part:
                    ticker = ticker_part.split("(")[0].strip()
                else:
                    ticker = ticker_part
            else:
                ticker = w
            # Skip invalid tickers (RS, HOD, EOD are not valid tickers)
            if ticker.upper() in ("RS", "HOD", "EOD"):
                continue
            # Check for ' short' suffix and strip it
            if ticker.lower().endswith(" short"):
                ticker = ticker[:-6].strip()
                if ticker.upper() in ("RS", "HOD", "EOD"):
                    continue
                if re.match(r'^[A-Z]{1,5}$', ticker):
                    valid_shorts.append(ticker)
            else:
                # Also strip ' long' suffix if present
                if ticker.lower().endswith(" long"):
                    ticker = ticker[:-5].strip()
                if ticker.upper() in ("RS", "HOD", "EOD"):
                    continue
                if re.match(r'^[A-Z]{1,5}$', ticker):
                    valid_longs.append(ticker)

        # Sort tickers: XL* tickers (XLE, XLF, XLV, XLRE, etc.) and sector ETFs (SMH, IGV, MAGS) go to the end
        def sort_key(ticker):
            is_sector_etf = ticker.startswith("XL") or ticker in ("SMH", "IGV", "MAGS")
            return (is_sector_etf, ticker)
        valid_longs.sort(key=sort_key)
        valid_shorts.sort(key=sort_key)

    # Display watchlist section ONLY if we have valid tickers
    if valid_longs or valid_shorts:
        st.markdown('<hr style="margin: 0.25rem 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)
        st.markdown('<div class="premarket-section watchlist-section">', unsafe_allow_html=True)
        st.markdown("### Watchlist Candidates")
        long_str = ', '.join(valid_longs) if valid_longs else '—'
        short_str = ', '.join(valid_shorts) if valid_shorts else '—'
        st.markdown(f"""
<table class="watchlist-table" style="width: 100%; border-collapse: collapse; font-family: inherit; margin-left: 0;">
  <thead>
    <tr style="background: rgba(128,128,128,0.1);">
      <th style="text-align: left; padding: 8px 12px; border: 1px solid rgba(128,128,128,0.2); font-weight: 600;">Direction</th>
      <th style="text-align: left; padding: 8px 12px; border: 1px solid rgba(128,128,128,0.2); font-weight: 600;">Watchlist</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="text-align: left; padding: 8px 12px; border: 1px solid rgba(128,128,128,0.15);"><strong>Long</strong></td>
      <td style="text-align: left; padding: 8px 12px; border: 1px solid rgba(128,128,128,0.15);">{long_str}</td>
    </tr>
    <tr>
      <td style="text-align: left; padding: 8px 12px; border: 1px solid rgba(128,128,128,0.15);"><strong>Short</strong></td>
      <td style="text-align: left; padding: 8px 12px; border: 1px solid rgba(128,128,128,0.15);">{short_str}</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_weekly_review(review: WeeklyReview):
    """Render a weekly review."""
    st.header(f"📅 Weekly Review - {review.week} ({review.date_range[0]} to {review.date_range[1]})")

    total_trades = sum(len(r.trades) for r in review.daily_reports)
    total_notes = sum(len(r.organized_notes) for r in review.daily_reports)
    total_highlights = sum(len(r.highlights_for_carry_forward) for r in review.daily_reports)

    # Compact inline stats — avoid st.metric vertical stacking
    st.markdown(f"""
    <div style="display: flex; gap: 24px; margin-top: 2.5rem; margin-bottom: 2.5rem; flex-wrap: wrap;">
        <div style="
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(128,128,128,0.15);
            border-radius: 6px;
            padding: 8px 16px;
            text-align: center;
            min-width: 100px;
        ">
            <div style="font-size: 0.8rem; color: #9e9e9e;">Trading Days</div>
            <div style="font-size: 1.4rem; font-weight: 600; color: #e0e0e0;">{len(review.daily_reports)}</div>
        </div>
        <div style="
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(128,128,128,0.15);
            border-radius: 6px;
            padding: 8px 16px;
            text-align: center;
            min-width: 100px;
        ">
            <div style="font-size: 0.8rem; color: #9e9e9e;">Total Trades</div>
            <div style="font-size: 1.4rem; font-weight: 600; color: #e0e0e0;">{total_trades}</div>
        </div>
        <div style="
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(128,128,128,0.15);
            border-radius: 6px;
            padding: 8px 16px;
            text-align: center;
            min-width: 100px;
        ">
            <div style="font-size: 0.8rem; color: #9e9e9e;">Total Notes</div>
            <div style="font-size: 1.4rem; font-weight: 600; color: #e0e0e0;">{total_notes}</div>
        </div>
        <div style="
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(128,128,128,0.15);
            border-radius: 6px;
            padding: 8px 16px;
            text-align: center;
            min-width: 100px;
        ">
            <div style="font-size: 0.8rem; color: #9e9e9e;">Highlights</div>
            <div style="font-size: 1.4rem; font-weight: 600; color: #e0e0e0;">{total_highlights}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="margin: 1rem 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["🏆 Gold Mine", "🔍 Pattern Suggestions", "📏 Metrics", "📈 Scorecard"])

    with tab1:
        render_weekly_gold_mine(review)

    with tab2:
        render_pattern_suggestions(review.pattern_suggestions, review.week)

    with tab3:
        render_metrics(review.metric_updates)

    with tab4:
        render_weekly_prediction_scorecard(review)


def render_pattern_suggestions(suggestions: list[PatternSuggestion], week_prefix: str = ""):
    """Render pattern suggestions with confirmation UI."""
    if not suggestions:
        st.info("No pattern suggestions for this week.")
        return

    for i, s in enumerate(suggestions):
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(s.severity_hint, "⚪")
        type_icon = {"mistake": "❌", "observation": "👁️", "setup": "📐", "rule": "📜"}.get(s.type.value, "📌")

        with st.expander(f"{type_icon} {severity_icon} {s.pattern} (x{s.frequency})"):
            st.write(f"**Type:** {s.type.value}")
            st.write(f"**Frequency:** {s.frequency} occurrences")
            st.write(f"**Severity:** {s.severity_hint}")
            st.write(f"**Supporting Days:** {', '.join(str(d) for d in s.supporting_days)}")

            st.write("**Evidence:**")
            for quote in s.evidence_quotes:
                st.text(f"  • {quote}")

            # User confirmation controls
            col1, col2, col3 = st.columns(3)
            key_prefix = f"{week_prefix}_" if week_prefix else ""
            with col1:
                if st.button("✅ Confirm", key=f"{key_prefix}confirm_{i}"):
                    st.success("Marked as confirmed!")
            with col2:
                if st.button("❌ Dismiss", key=f"{key_prefix}dismiss_{i}"):
                    st.warning("Pattern dismissed.")
            with col3:
                new_name = st.text_input("Rename", key=f"{key_prefix}rename_{i}", placeholder="Custom name...")
                if new_name:
                    st.info(f"Renamed to: {new_name}")


def render_metrics(metrics: dict[str, list[dict]]):
    """Render metric charts."""
    if not metrics:
        st.info("No metrics data.")
        return

    for metric_name, series in metrics.items():
        if not series:
            continue

        df = pd.DataFrame(series)
        df['date'] = pd.to_datetime(df['date'])

        fig = px.line(df, x='date', y='value', title=metric_name.replace('_', ' ').title(),
                      markers=True)
        st.plotly_chart(fig, use_container_width=True)


def render_weekly_gold_mine(review: "WeeklyReview"):
    """Render gold mine — all #gold and #ptrade tagged notes aggregated from the week."""

    all_gold = []
    all_ptrade = []
    for report in review.daily_reports:
        for note in report.organized_notes:
            tags = getattr(note, 'tags', []) or []
            if "gold" in tags:
                all_gold.append((report.date, note))
            if "ptrade" in tags:
                all_ptrade.append((report.date, note))

    all_items = all_gold + all_ptrade
    if not all_items:
        st.info("No #gold or #ptrade tagged notes this week.")
        return

    st.caption(f"Key insights & paper trades from {len(set(d for d, _ in all_items))} trading days — review for calibration")

    current_date = None
    for report_date, note in all_items:
        # Date header when date changes
        if report_date != current_date:
            current_date = report_date
            if current_date is not None:
                st.markdown('<hr style="margin: 8px 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)
            st.markdown(f"**{report_date}**")

        tags = getattr(note, 'tags', []) or []
        is_ptrade = 'ptrade' in tags
        tag_label = "🧪 Paper Trade" if is_ptrade else "🏆 Gold Insight"

        clean_text = re.sub(r'\s*\[TRADE:[^\]]*\]\s*', ' ', note.text).strip()
        clean_text = re.sub(r'\s{2,}', ' ', clean_text).strip()
        clean_text = clean_text.lstrip()

        # Format tags
        tag_badges = ""
        if note.tags:
            badges = []
            for tag in note.tags:
                color = TAG_COLORS.get(tag.lower(), "#6c757d")
                badges.append(f'<span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-left: 4px;">#{tag}</span>')
            tag_badges = " ".join(badges)

        border_color = "#4caf50" if is_ptrade else "#ffd700"
        st.markdown(f"""
        <div style="padding-left: 4px; margin: 4px 0; border-left: 3px solid {border_color}; padding-left: 10px;">
            <strong style="color:{border_color};">{tag_label} {note.timestamp}</strong>  {clean_text} {tag_badges}
        </div>
        """, unsafe_allow_html=True)

    # Summary count
    st.markdown(f'<div style="margin-top: 12px;"><strong>Total: {len(all_gold)} gold insights + {len(all_ptrade)} paper trades this week</strong></div>', unsafe_allow_html=True)


def render_prediction_scorecard_daily(report: DailyReport):
    """Render prediction scorecard for a single day - shows #gold and #ptrade notes with grading."""
    gold_notes = []
    ptrade_notes = []

    for note in report.organized_notes:
        tags = getattr(note, 'tags', []) or []
        if 'gold' in tags:
            gold_notes.append(note)
        if 'ptrade' in tags:
            ptrade_notes.append(note)

    all_pred_notes = gold_notes + ptrade_notes
    if not all_pred_notes:
        st.info("No #gold or #ptrade predictions to score for this day.")
        return

    st.markdown("**📊 Prediction Scorecard — Daily Review**")
    st.caption("💡 #gold = key insights to revisit (not to act on) | #ptrade = paper trades to grade")

    # Use session state to store grades for this session
    if 'prediction_grades' not in st.session_state:
        st.session_state['prediction_grades'] = {}

    # Create a container for each prediction
    for i, note in enumerate(all_pred_notes):
        tags = getattr(note, 'tags', []) or []
        is_ptrade = 'ptrade' in tags
        is_gold = 'gold' in tags

        tag_label = "🧪 Paper Trade" if is_ptrade else "🏆 Gold Insight"
        tag_color = "#4caf50" if is_ptrade else "#ffd700"

        clean_text = re.sub(r'\s*\[TRADE:[^\]]*\]\s*', ' ', note.text).strip()
        clean_text = re.sub(r'\s{2,}', ' ', clean_text).strip()
        clean_text = clean_text.lstrip()

        note_key = f"{report.date}_{note.timestamp}_{i}"
        current_grade = st.session_state['prediction_grades'].get(note_key, None)

        with st.expander(f"{tag_label} — {note.timestamp} | {clean_text[:80]}...", expanded=(current_grade is None)):
            st.markdown(f"""
            <div style="padding: 8px; border-left: 3px solid {tag_color}; background: rgba(255,255,255,0.02); margin: 4px 0;">
                <strong style="color:{tag_color};">{tag_label}</strong>  {note.timestamp}
                <div style="margin-top: 4px;">{clean_text}</div>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("✅ Right", key=f"grade_right_{note_key}", use_container_width=True):
                    st.session_state['prediction_grades'][note_key] = "right"
                    st.rerun()
            with col2:
                if st.button("❌ Wrong", key=f"grade_wrong_{note_key}", use_container_width=True):
                    st.session_state['prediction_grades'][note_key] = "wrong"
                    st.rerun()
            with col3:
                if st.button("⚪ Partial", key=f"grade_partial_{note_key}", use_container_width=True):
                    st.session_state['prediction_grades'][note_key] = "partial"
                    st.rerun()
            with col4:
                if st.button("🔄 Clear", key=f"grade_clear_{note_key}", use_container_width=True):
                    if note_key in st.session_state['prediction_grades']:
                        del st.session_state['prediction_grades'][note_key]
                    st.rerun()

            if current_grade:
                grade_colors = {"right": "#2ca02c", "wrong": "#d62728", "partial": "#ff7f0e"}
                grade_labels = {"right": "✅ CORRECT", "wrong": "❌ WRONG", "partial": "⚪ PARTIAL"}
                st.markdown(f"**Grade:** <span style='color:{grade_colors[current_grade]}; font-weight:600;'>{grade_labels[current_grade]}</span>", unsafe_allow_html=True)
                notes = st.text_input("Notes on outcome", key=f"grade_notes_{note_key}", placeholder="What happened?")
                if notes:
                    st.session_state['prediction_grades'][note_key + "_notes"] = notes

    # Summary
    graded = {k: v for k, v in st.session_state['prediction_grades'].items() if not k.endswith("_notes") and v in ("right", "wrong", "partial")}
    if graded:
        right = sum(1 for v in graded.values() if v == "right")
        wrong = sum(1 for v in graded.values() if v == "wrong")
        partial = sum(1 for v in graded.values() if v == "partial")
        total = len(graded)
        accuracy = right / total * 100 if total > 0 else 0

        st.markdown(f"""
        <div style="display: flex; gap: 16px; margin-top: 12px; padding: 12px; border-radius: 6px; background: rgba(255,255,255,0.03);">
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #2ca02c;">{right}</div>
                <div style="font-size: 0.8rem; color: #9e9e9e;">Right</div>
            </div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #d62728;">{wrong}</div>
                <div style="font-size: 0.8rem; color: #9e9e9e;">Wrong</div>
            </div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #ff7f0e;">{partial}</div>
                <div style="font-size: 0.8rem; color: #9e9e9e;">Partial</div>
            </div>
            <div style="text-align: center; flex: 1;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #17becf;">{accuracy:.0f}%</div>
                <div style="font-size: 0.8rem; color: #9e9e9e;">Accuracy</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_weekly_prediction_scorecard(review: "WeeklyReview"):
    """Aggregate prediction scorecard for the entire week."""
    st.markdown("**📈 Weekly Prediction Scorecard**")
    st.caption("Aggregated from daily #gold and #ptrade notes across the week")

    # Collect all graded predictions
    all_grades = {}
    for report in review.daily_reports:
        day_key = str(report.date)
        for note in report.organized_notes:
            tags = getattr(note, 'tags', []) or []
            if 'gold' in tags or 'ptrade' in tags:
                note_key = f"{day_key}_{note.timestamp}"
                if note_key in st.session_state.get('prediction_grades', {}):
                    grade = st.session_state['prediction_grades'][note_key]
                    if grade in ("right", "wrong", "partial"):
                        all_grades[note_key] = {"grade": grade, "date": day_key, "note": note, "type": "ptrade" if 'ptrade' in tags else "gold"}

    if not all_grades:
        st.info("No graded predictions yet. Use the daily Prediction Scorecard to grade your #gold and #ptrade notes.")
        return

    # Separate by type
    gold_grades = {k: v for k, v in all_grades.items() if v["type"] == "gold"}
    ptrade_grades = {k: v for k, v in all_grades.items() if v["type"] == "ptrade"}

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🏆 Gold Insights**")
        if gold_grades:
            total = len(gold_grades)
            right = sum(1 for v in gold_grades.values() if v["grade"] == "right")
            wrong = sum(1 for v in gold_grades.values() if v["grade"] == "wrong")
            partial = sum(1 for v in gold_grades.values() if v["grade"] == "partial")
            acc = right / total * 100 if total > 0 else 0
            st.metric("Accuracy", f"{acc:.0f}%", f"{right}/{total}")

            for k, v in gold_grades.items():
                grade_color = {"right": "green", "wrong": "red", "partial": "orange"}[v["grade"]]
                st.markdown(f"- <span style='color:{grade_color}'>●</span> {v['date']} {v['note'].timestamp}: {v['note'].text[:60]}...", unsafe_allow_html=True)
        else:
            st.caption("No gold insights graded yet")

    with col2:
        st.markdown("**🧪 Paper Trades**")
        if ptrade_grades:
            total = len(ptrade_grades)
            right = sum(1 for v in ptrade_grades.values() if v["grade"] == "right")
            wrong = sum(1 for v in ptrade_grades.values() if v["grade"] == "wrong")
            partial = sum(1 for v in ptrade_grades.values() if v["grade"] == "partial")
            acc = right / total * 100 if total > 0 else 0
            st.metric("Accuracy", f"{acc:.0f}%", f"{right}/{total}")

            for k, v in ptrade_grades.items():
                grade_color = {"right": "green", "wrong": "red", "partial": "orange"}[v["grade"]]
                st.markdown(f"- <span style='color:{grade_color}'>●</span> {v['date']} {v['note'].timestamp}: {v['note'].text[:60]}...", unsafe_allow_html=True)
        else:
            st.caption("No paper trades graded yet")


# ================================
# Sidebar Navigation
# ================================

def render_sidebar():
    """Render sidebar navigation and date/week selectors."""
    st.sidebar.title("📈 Trading Journal")

    page = st.sidebar.radio(
        "Navigate",
        ["Daily Report", "Pre-Market", "Weekly Review", "Settings"]
    )

    # Date selector for daily/pre-market - native st.date_input in sidebar
    reports = load_daily_reports()
    available_dates = sorted([r.date for r in reports])

    if available_dates:
        selected_date = st.sidebar.date_input(
            "Select Date",
            value=available_dates[-1],
            min_value=min(available_dates),
            max_value=date.today()  # Future dates greyed out/unclickable
        )

        # Check if selected date has a report
        has_report = selected_date in available_dates

        if not has_report and selected_date <= date.today():
            # Past date without report - offer to create
            st.sidebar.warning(f"No report for {selected_date}.")
            if st.sidebar.button("📝 Create Daily Report", key="create_daily_report", use_container_width=True):
                create_daily_report(selected_date)
                st.rerun()
        elif not has_report and selected_date > date.today():
            # Future date - already unclickable due to max_value, but handle edge case
            st.sidebar.info("Future dates cannot be selected.")
            selected_date = available_dates[-1]
        elif selected_date not in available_dates:
            # This handles edge case where min_value > available_dates[-1] somehow
            st.sidebar.warning(f"No report for {selected_date}. Showing latest.")
            selected_date = available_dates[-1]
    else:
        selected_date = date.today()
        st.sidebar.warning("No daily reports found. Run historical ingestion first.")

    # Week selector for weekly review (show in sidebar)
    reviews = load_weekly_reviews()
    if reviews:
        week_labels = [r.week for r in reviews]
        selected_week = st.sidebar.selectbox(
            "Select Week",
            week_labels,
            index=len(week_labels) - 1,
            key="week_selector_sidebar"
        )
    else:
        selected_week = None
        st.sidebar.caption("No weekly reviews found. Run weekly synthesis first.")

    return page, selected_date, selected_week, reports, reviews


def create_daily_report(target_date: date):
    """Create a new daily report for the given date by parsing DRC file from vault."""
    from src.core.parser import parse_drc_file, find_all_drc_files
    from src.core.extractor import extract_daily_report_fallback
    from src.core.models import (
        DailyReport, MarketBias, MarketBiasDirection, MarketBiasConfidence,
        MarketRegime, OrganizedNote, ExtractedTrade, NoteCategory,
        TradeDirection, TradeStatus
    )
    import yaml

    # Load vault path from settings
    SETTINGS_FILE = Path("config/settings.yaml")
    if SETTINGS_FILE.exists():
        settings = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8"))
    else:
        settings = {}

    vault_path = Path(settings.get("vault_path", "C:/Users/Thaddeus/OneDrive/Desktop/Vaulted/!Journalit"))

    # Find all DRC files
    drc_files = find_all_drc_files(vault_path)

    # Find matching DRC file (DDMMYY format in filename)
    drc_file = None
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
        # Fallback: create empty report if no DRC file found
        report = DailyReport(
            date=target_date,
            market_bias=MarketBias(
                direction=MarketBiasDirection.UNCLEAR,
                confidence=MarketBiasConfidence.LOW,
                regime=MarketRegime.TRANSITIONAL,
                key_levels=[]
            ),
            organized_notes=[],
            trades=[],
            highlights_for_carry_forward=[],
            raw_market_notes="",
            source_file=f"Manual entry via UI ({date.today().isoformat()}) - No DRC file found"
        )
    else:
        # Parse DRC file
        raw_report = parse_drc_file(drc_file)
        if not raw_report:
            # Fallback empty report
            report = DailyReport(
                date=target_date,
                market_bias=MarketBias(
                    direction=MarketBiasDirection.UNCLEAR,
                    confidence=MarketBiasConfidence.LOW,
                    regime=MarketRegime.TRANSITIONAL,
                    key_levels=[]
                ),
                organized_notes=[],
                trades=[],
                highlights_for_carry_forward=[],
                raw_market_notes="",
                source_file=f"Manual entry via UI ({date.today().isoformat()}) - DRC parse failed"
            )
        else:
            # Extract with fallback logic
            extracted = extract_daily_report_fallback(raw_report)

            organized_notes = [OrganizedNote.model_validate(n) for n in extracted["organized_notes"]]
            trades = [ExtractedTrade.model_validate(t) for t in extracted["trades"]]

            bias_data = extracted.get("market_bias", {})
            market_bias = MarketBias(
                direction=MarketBiasDirection(bias_data.get("direction", "unclear")),
                confidence=MarketBiasConfidence(bias_data.get("confidence", "low")),
                regime=MarketRegime(bias_data.get("regime", "transitional")),
                key_levels=bias_data.get("key_levels", [])
            )

            report = DailyReport(
                date=target_date,
                organized_notes=organized_notes,
                trades=trades,
                highlights_for_carry_forward=extracted["highlights_for_carry_forward"],
                market_bias=market_bias,
                raw_market_notes=raw_report.raw_market_notes,
                source_file=str(drc_file)
            )

    # Save to JSON
    path = Path("data/daily_reports") / f"{target_date.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    st.sidebar.success(f"Created daily report for {target_date}")
    # Clear cache so it reloads
    load_daily_reports.clear()


def create_or_update_trade_file(trade: ExtractedTrade, target_date: date) -> Path:
    """
    Create or update a journalit trade YAML file for a given trade.
    Creates YAML frontmatter in the journalit trade format.
    """
    from src.core.models import TradeDirection, TradeStatus

    # Determine trade direction from ExtractedTrade.direction
    direction = trade.direction.value if trade.direction else "long"

    # Determine trade status
    if trade.outcome == TradeStatus.CLOSED:
        trade_status = "CLOSED"
    elif trade.outcome in (TradeStatus.STOPPED, TradeStatus.STOPPED_OUT):
        trade_status = "STOPPED"
    else:
        trade_status = "OPEN"

    # Build entries
    entries = [
        {
            "time": f"{target_date}T{trade.timestamp}:00",
            "price": float(trade.price),
            "size": int(trade.size) if trade.size else 1
        }
    ]

    # Build exits
    exits = []
    if trade.exit_timestamp and trade.exit_price:
        exits.append({
            "time": f"{target_date}T{trade.exit_timestamp}:00",
            "price": float(trade.exit_price),
            "size": int(trade.size) if trade.size else 1
        })

    # YAML frontmatter content
    import uuid
    trade_id = f"trade_{uuid.uuid4().hex[:12]}"

    yaml_content = f"""---
lastSync: '{datetime.now().isoformat()}'
type: trade
tradeStatus: {trade_status}
direction: {direction}
pnl: 0.0
rMultiple: 0.0
entries:
- time: '{target_date}T{trade.timestamp}:00'
  price: {trade.price}
  size: {trade.size if trade.size else 1}
exits: {exits if exits else '[]'}
commission: 0
commissionType: fixed
swap: 0
fees: 0
setupIds:
- Long Setup - Intraday
mistakeIds: []
accountIds:
- 'Goal: 75% WR, 2.0 PF'
instrument: {trade.ticker}
assetType: stock
setup: Long Setup - Intraday
mistake: []
account:
- 'Goal: 75% WR, 2.0 PF'
images: []
tags:
- Day Trade
- Market Condition - Bullish Trend Day
thesis: '{trade.reason}'
useDirectPnLInput: false
directPnL: 0
reviewed: false
reviewedAt: null
tradeId: {trade_id}
schemaVersion: 1
canonicalExecutionMigrationVersion: 2026-05-canonical-execution-v2
---

# Trade Notes

<!-- Add your trade notes here -->

## Trade Review

### What worked?
<!-- journalit-trade-review:question id="win-what-worked" -->

### What didn't work?
<!-- journalit-trade-review:question id="win-what-failed" -->

### What will I do differently?
<!-- journalit-trade-review:question id="win-next-time" -->

---
_End Trade Review_
"""

    # Load vault path from settings
    import yaml
    SETTINGS_FILE = Path("config/settings.yaml")
    if SETTINGS_FILE.exists():
        settings_local = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8"))
    else:
        settings_local = {}

    vault_path = Path(settings_local.get("vault_path", "C:/Users/Thaddeus/OneDrive/Desktop/Vaulted/!Journalit"))

    # Determine trade directory path
    # Format: Vault/!Journalit/YYYY/QQ/MM/WNN/trades/TICKER-DDMMYY-T#.md
    year = target_date.year
    quarter = (target_date.month - 1) // 3 + 1
    month = target_date.month
    week = (target_date.day - 1) // 7 + 1

    trades_dir = vault_path / str(year) / f"Q{quarter}" / f"{month:02d}" / f"W{week}" / "trades"
    trades_dir.mkdir(parents=True, exist_ok=True)

    # Find existing trade file for this ticker/date
    date_str = target_date.strftime("%d%m%y")
    existing_file = None
    for f in trades_dir.glob(f"{trade.ticker}-{date_str}-T*.md"):
        existing_file = f
        break

    if existing_file:
        trade_file = existing_file
    else:
        # Find next trade number
        existing = list(trades_dir.glob(f"{trade.ticker}-{date_str}-T*.md"))
        trade_num = 1
        if existing:
            nums = []
            for f in existing:
                match = re.search(rf"{trade.ticker}-{date_str}-T(\d+)", f.name)
                if match:
                    nums.append(int(match.group(1)))
            if nums:
                trade_num = max(nums) + 1

        trade_file = trades_dir / f"{trade.ticker}-{date_str}-T{trade_num}.md"

    # Write the trade file
    trade_file.write_text(yaml_content, encoding="utf-8")
    return trade_file


# ================================
# Main Pages
# ================================

def page_daily_report(selected_date: date, reports: list[DailyReport]):
    """Daily report page."""
    report = next((r for r in reports if r.date == selected_date), None)
    if report:
        render_daily_report(report)
    else:
        st.error(f"No report found for {selected_date}")


def delete_daily_report(target_date: date):
    """Delete a daily report JSON file."""
    path = Path("data/daily_reports") / f"{target_date.isoformat()}.json"
    pretty_path = Path("data/daily_reports") / f"{target_date.isoformat()}_report.md"
    if path.exists():
        path.unlink()
    if pretty_path.exists():
        pretty_path.unlink()
    st.sidebar.success(f"Deleted daily report for {target_date}")
    load_daily_reports.clear()


def delete_pre_market(target_date: date):
    """Delete pre-market notes JSON file."""
    path = Path("data/pre_market") / f"{target_date.isoformat()}.json"
    if path.exists():
        path.unlink()
    st.sidebar.success(f"Deleted pre-market for {target_date}")
    load_pre_market.clear()


def delete_weekly_review(target_week: str):
    """Delete weekly review JSON file."""
    path = Path("data/weekly_reviews") / f"{target_week}.json"
    if path.exists():
        path.unlink()
    st.sidebar.success(f"Deleted weekly review {target_week}")
    load_weekly_reviews.clear()


def next_trading_day(d: date) -> date:
    """Get the next trading day (skip weekends)."""
    next_d = d + timedelta(days=1)
    while next_d.weekday() >= 5:  # Skip weekends
        next_d += timedelta(days=1)
    return next_d


def page_pre_market(selected_date: date):
    """Pre-market page - shows pre-market for the NEXT trading day after selected daily report date."""
    # Compute the pre-market date (next trading day after the daily report date)
    pre_market_date = next_trading_day(selected_date)

    st.header(f"🌅 Pre-market Report — {pre_market_date}")
    st.caption(f"Based on daily report from {selected_date}")

    # Load pre-market for the computed date
    pre = load_pre_market(pre_market_date)
    if pre:
        render_pre_market(pre)
    else:
        st.info(f"No pre-market notes generated for {pre_market_date}.")
        st.caption("Pre-market notes are generated from the PREVIOUS day's daily report during daily_sync.")

        # Check if we have a daily report for the selected date (which is the prior trading day)
        reports = load_daily_reports()
        prior_report = next((r for r in reports if r.date == selected_date), None)

        if prior_report:
            if st.button("📊 Generate Pre-market Report", key="gen_premarket", type="primary", use_container_width=False):
                generate_pre_market_from_daily(pre_market_date, prior_report)
                st.rerun()
        else:
            st.warning(f"⚠️ No daily report found for {selected_date}.")
            st.caption("You can still generate a pre-market report with just economic events/earnings.")
            if st.button("📊 Generate Pre-market (Economic Events Only)", key="gen_premarket_no_prior", type="secondary", use_container_width=False):
                generate_pre_market_from_daily(pre_market_date, None)
                st.rerun()


def generate_pre_market_from_daily(target_date: date, prior_report: DailyReport = None):
    """Generate pre-market notes from previous day's daily report (optional)."""
    from src.core.extractor import generate_pre_market_fallback
    from src.data.fetchers.economic_earnings import fetch_pre_market_data, format_economic_for_pre_market, format_earnings_for_watchlist
    from src.core.models import EconomicEvent, PreMarketNotes
    import yaml

    # Get economic events for target date
    events = fetch_pre_market_data(target_date)
    econ_formatted = format_economic_for_pre_market(events.get("economic_events", []))
    earn_watchlist = format_earnings_for_watchlist(events.get("earnings", []))

    # Generate pre-market using fallback
    pre_market_data = generate_pre_market_fallback(prior_report, econ_formatted)

    # If no prior daily report, add a note
    if prior_report is None:
        prior_date = target_date - timedelta(days=1)
        while prior_date.weekday() >= 5:
            prior_date -= timedelta(days=1)
        no_prior_note = f"No prior daily journal for {prior_date.isoformat()} — showing economic events only"
        pre_market_data["carry_forward"].insert(0, no_prior_note)

    # Merge earnings into watchlist
    watchlist = pre_market_data.get("watchlist_candidates", [])
    for ew in earn_watchlist:
        if ew not in str(watchlist):
            watchlist.append(ew)
    watchlist = watchlist[:15]

    # Build PreMarketNotes
    econ_events = [EconomicEvent(
        date=target_date,
        time=e["time"],
        event=e["event"],
        impact=e["impact"]
    ) for e in econ_formatted]

    pre_market = PreMarketNotes(
        date=target_date,
        carry_forward=pre_market_data.get("carry_forward", []),
        economic_events=econ_events,
        active_rules=pre_market_data.get("active_rules", []),
        watchlist_candidates=watchlist,
        earnings_data=events.get("earnings", [])
    )

    # Save
    path = Path("data/pre_market") / f"{target_date.isoformat()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pre_market.model_dump_json(indent=2), encoding="utf-8")

    st.sidebar.success(f"Generated pre-market for {target_date}")
    load_pre_market.clear()


def page_weekly_review(selected_week: str, reviews: list[WeeklyReview]):
    """Weekly review page."""
    if not reviews:
        st.warning("No weekly reviews found. Run weekly synthesis first.")
        return

    if not selected_week:
        st.info("Select a week from the sidebar.")
        return

    review = next((r for r in reviews if r.week == selected_week), None)
    if review:
        render_weekly_review(review)


def page_settings():
    """Settings page."""
    st.header("⚙️ Settings")

    st.subheader("Active Rules")

    # Load current settings
    SETTINGS_FILE = Path("config/settings.yaml")
    if SETTINGS_FILE.exists():
        current_settings = yaml.safe_load(SETTINGS_FILE.read_text())
    else:
        current_settings = {}

    active_rules = current_settings.get("active_rules", [])

    # Display current rules with delete buttons
    if active_rules:
        for i, rule in enumerate(active_rules):
            col1, col2 = st.columns([0.9, 0.1])
            with col1:
                st.markdown(f"• {rule}")
            with col2:
                if st.button("✕", key=f"del_rule_{i}", help="Remove this rule"):
                    new_rules = active_rules[:i] + active_rules[i+1:]
                    save_active_rules(new_rules)
                    st.rerun()
    else:
        st.caption("No active rules set. Add rules below from your weekly review.")

    # Add new rule
    with st.expander("➕ Add Active Rule", expanded=not active_rules):
        new_rule = st.text_input("Rule text", placeholder="e.g., NO FOMO entries - wait for M5 pullback close")
        if st.button("Add Rule", type="primary", key="add_rule_btn"):
            if new_rule.strip():
                updated_rules = active_rules + [new_rule.strip()]
                save_active_rules(updated_rules)
                st.success(f"Added rule: {new_rule.strip()}")
                st.rerun()
            else:
                st.error("Rule text cannot be empty")

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("Quick Actions")


def save_active_rules(rules: list[str]):
    """Save active rules to settings.yaml."""
    SETTINGS_FILE = Path("config/settings.yaml")
    if SETTINGS_FILE.exists():
        current_settings = yaml.safe_load(SETTINGS_FILE.read_text())
    else:
        current_settings = {}

    current_settings["active_rules"] = rules

    SETTINGS_FILE.write_text(yaml.dump(current_settings, default_flow_style=False, sort_keys=False))

    # Reload the global settings variable
    global settings
    settings = current_settings

    # Use raw HTML buttons instead of st.columns to have full control
    st.markdown("""
    <style>
    /* Target columns containing quick action buttons ONLY */
    div[data-testid="column"]:has(.stButton > button[key="qa_reload"]),
    div[data-testid="column"]:has(.stButton > button[key="qa_daily"]),
    div[data-testid="column"]:has(.stButton > button[key="qa_weekly"]) {
        flex: 0 0 10rem !important;
        width: 10rem !important;
        min-width: 10rem !important;
        max-width: 10rem !important;
    }
    div[data-testid="column"]:has(.stButton > button[key="qa_reload"]) > div,
    div[data-testid="column"]:has(.stButton > button[key="qa_daily"]) > div,
    div[data-testid="column"]:has(.stButton > button[key="qa_weekly"]) > div {
        width: 10rem !important;
        min-width: 10rem !important;
        max-width: 10rem !important;
    }
    /* Quick action buttons themselves */
    .stButton > button[key="qa_reload"],
    .stButton > button[key="qa_daily"],
    .stButton > button[key="qa_weekly"] {
        width: 10rem !important;
        min-width: 10rem !important;
        max-width: 10rem !important;
        padding: 0.25rem 0.5rem !important;
        font-size: 0.6rem !important;
        line-height: 1.2 !important;
        white-space: nowrap !important;
        text-align: center !important;
        flex: 0 0 10rem !important;
    }
    .stButton > button[key="qa_reload"] > *,
    .stButton > button[key="qa_daily"] > *,
    .stButton > button[key="qa_weekly"] > * {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Use st.columns but with fixed width via CSS
    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        if st.button("📅 Run Daily Sync", help="Process today's DRC file and generate Daily Report + Pre-Market notes", use_container_width=False, key="qa_daily"):
            st.info("Run from CLI: `python -m src.cli.daily_sync run --date YYYY-MM-DD`")

    with col2:
        if st.button("📊 Run Weekly Synthesis", help="Aggregate daily reports into weekly review with patterns", use_container_width=False, key="qa_weekly"):
            st.info("Run from CLI: `python scripts/weekly_synthesis.py`")

    with col3:
        if st.button("🔄 Reload Data", help="Clear all cached data and reload from JSON files", use_container_width=False, key="qa_reload"):
            st.cache_data.clear()
            st.success("Cache cleared!")

    st.markdown("---")

    st.subheader("🗑️ Delete Data")

    # --- Daily Reports ---
    st.markdown("**Daily Reports**")
    reports = load_daily_reports()
    if reports:
        available_dates = sorted([r.date for r in reports])
        c1, _ = st.columns([2, 5])
        with c1:
            date_to_delete = st.selectbox(
                "Select daily report to delete",
                available_dates,
                format_func=lambda d: d.isoformat(),
                key="delete_daily_date"
            )
            confirm_daily = st.checkbox(f"Confirm: delete {date_to_delete.isoformat()} daily report", key="confirm_delete_daily")
            if st.button("🗑️ Delete Daily Report", type="secondary", key="delete_daily_btn", disabled=not confirm_daily):
                delete_daily_report(date_to_delete)
                st.rerun()
    else:
        st.caption("No daily reports to delete.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Pre-Market Notes ---
    st.markdown("**Pre-Market Notes**")
    pre_files = sorted(PRE_DIR.glob("*.json"))
    if pre_files:
        pre_dates = sorted([date.fromisoformat(f.stem) for f in pre_files if f.stem.count("-") == 2])
        if pre_dates:
            c2, _ = st.columns([2, 5])
            with c2:
                pre_date_to_delete = st.selectbox(
                    "Select pre-market to delete",
                    pre_dates,
                    format_func=lambda d: d.isoformat(),
                    key="delete_pre_date"
                )
                confirm_pre = st.checkbox(f"Confirm: delete {pre_date_to_delete.isoformat()} pre-market", key="confirm_delete_pre")
                if st.button("🗑️ Delete Pre-Market", type="secondary", key="delete_pre_btn", disabled=not confirm_pre):
                    delete_pre_market(pre_date_to_delete)
                    st.rerun()
        else:
            st.caption("No pre-market notes to delete.")
    else:
        st.caption("No pre-market notes to delete.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Weekly Reviews ---
    st.markdown("**Weekly Reviews**")
    reviews = load_weekly_reviews()
    if reviews:
        week_labels = [r.week for r in reviews]
        c3, _ = st.columns([2, 5])
        with c3:
            week_to_delete = st.selectbox(
                "Select weekly review to delete",
                week_labels,
                key="delete_weekly_week"
            )
            confirm_weekly = st.checkbox(f"Confirm: delete {week_to_delete} weekly review", key="confirm_delete_weekly")
            if st.button("🗑️ Delete Weekly Review", type="secondary", key="delete_weekly_btn", disabled=not confirm_weekly):
                delete_weekly_review(week_to_delete)
                st.rerun()
    else:
        st.caption("No weekly reviews to delete.")

    st.markdown("---")

    st.subheader("Project Paths")
    st.markdown("""
**Data Locations:** Configured in `config/settings.yaml` under the `data_locations` section. Edit that file directly to change paths (requires app restart).

**Key Paths in settings.yaml:**
- `data_locations.data_dir` — Root data directory (default: `data/`)
- `data_locations.daily_reports_dir` — Daily reports subdirectory (default: `daily_reports/`)
- `data_locations.pre_market_dir` — Pre-market notes subdirectory (default: `pre_market/`)
- `data_locations.weekly_reviews_dir` — Weekly reviews subdirectory (default: `weekly_reviews/`)
- `data_locations.monthly_reviews_dir` — Monthly reviews subdirectory (default: `monthly_reviews/`)
- `data_locations.cache_dir` — LLM cache subdirectory (default: `cache/llm/`)

**Other Important Settings in settings.yaml:**
- `vault_path` — Path to your Obsidian vault (read-only, set once during setup)
- `llm.provider` / `model` / `temperature` — LLM provider configuration (Groq, Google, OpenRouter, Ollama)
- `fmp_api_key_env` — Environment variable name for FMP API key (for earnings/calendar)
- `active_rules` — Add trading rules here after weekly review to track them
- `metrics` — Define custom metrics to track in weekly reviews
**Economic Calendar & Earnings (FMP API):**
- Set `FMP_API_KEY` in `.env` to enable automatic fetching from Financial Modeling Prep
- When configured, `src/data/fetchers/economic_earnings.py` auto-fetches events & earnings for pre-market
- `economic_calendar.events_2026_q3` in settings.yaml serves as a manual fallback/supplement for major recurring events (FOMC, CPI, NFP, Jackson Hole) if API is unavailable or for far-future dates
- `earnings_min_market_cap` filters earnings to large caps only (default $50B+)

**Quick Actions from this page** (buttons above) clear cache or show CLI commands for daily/weekly sync.
""")


# ================================
# Main App
# ================================

# Render sidebar and get navigation
page, selected_date, selected_week, reports, reviews = render_sidebar()

# Route to pages
if page == "Daily Report":
    page_daily_report(selected_date, reports)
elif page == "Pre-Market":
    page_pre_market(selected_date)
elif page == "Weekly Review":
    page_weekly_review(selected_week, reviews)
elif page == "Settings":
    page_settings()