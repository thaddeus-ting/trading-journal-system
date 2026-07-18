================================================================================
EXAMPLE REPORTS - Trading Journal System
================================================================================
Based on actual DRC content from your vault (March 2026)

================================================================================
1. DAILY REPORT (Generated from Market Notes)
================================================================================
SOURCE: DRC-120326.md (March 12, 2026) - Market Notes section
GENERATED: 2026-03-13 06:45 (post-market daily_sync)

{
  "date": "2026-03-12",
  "market_notes": [
    {
      "timestamp": "09:30",
      "raw_text": "SPY gap down, watching NKE short - D1 breakdown into gap",
      "tickers": ["SPY", "NKE"],
      "is_trade": false
    },
    {
      "timestamp": "09:35",
      "raw_text": "NKE D1 looks weak, but SPY gapped down - need market confirmation",
      "tickers": ["SPY", "NKE"],
      "is_trade": false
    },
    {
      "timestamp": "09:49",
      "raw_text": "FOMO entry NKE short @ 55.10, 4 shares - D1 breakdown",
      "tickers": ["NKE"],
      "is_trade": true,
      "trade": {
        "direction": "short",
        "ticker": "NKE",
        "price": 55.10,
        "size": 4,
        "reason": "D1 breakdown",
        "type": "entry"
      }
    },
    {
      "timestamp": "09:55",
      "raw_text": "NKE holding VWAP-, SPY bouncing off PDL",
      "tickers": ["NKE", "SPY"],
      "is_trade": false
    },
    {
      "timestamp": "10:02",
      "raw_text": "KKR breaking D1 horizontal line with volume - watching for short",
      "tickers": ["KKR"],
      "is_trade": false
    },
    {
      "timestamp": "10:16",
      "raw_text": "exit NKE @ 54.97 - SPY closed above VWAP+, don't like this",
      "tickers": ["NKE", "SPY"],
      "is_trade": true,
      "trade": {
        "direction": "exit",
        "ticker": "NKE",
        "price": 54.97,
        "size": 4,
        "reason": "SPY closed above VWAP+",
        "type": "exit"
      }
    },
    {
      "timestamp": "10:35",
      "raw_text": "FOMO and panic out of KKR, Dave gets beautiful short on TSLA which I identified earlier",
      "tickers": ["KKR", "TSLA"],
      "is_trade": false
    },
    {
      "timestamp": "10:42",
      "raw_text": "IREN compressing on M5 - watching for flush short",
      "tickers": ["IREN"],
      "is_trade": false
    },
    {
      "timestamp": "10:50",
      "raw_text": "CHASED IREN flush short @ 8.45, 20 shares - no confirmation",
      "tickers": ["IREN"],
      "is_trade": true,
      "trade": {
        "direction": "short",
        "ticker": "IREN",
        "price": 8.45,
        "size": 20,
        "reason": "M5 flush",
        "type": "entry"
      }
    },
    {
      "timestamp": "11:07",
      "raw_text": "wait for this candle to close, ideally on its low near LOD",
      "tickers": ["IREN"],
      "is_trade": false
    },
    {
      "timestamp": "11:19",
      "raw_text": "swinging KR long @ 58.20, 5 shares - wimpy pullback held VWAP",
      "tickers": ["KR"],
      "is_trade": true,
      "trade": {
        "direction": "long",
        "ticker": "KR",
        "price": 58.20,
        "size": 5,
        "reason": "wimpy pullback held VWAP",
        "type": "entry"
      }
    },
    {
      "timestamp": "11:45",
      "raw_text": "TEAM short @ 58.80, 4 shares - anticipatory, no pullback",
      "tickers": ["TEAM"],
      "is_trade": true,
      "trade": {
        "direction": "short",
        "ticker": "TEAM",
        "price": 58.80,
        "size": 4,
        "reason": "anticipatory, no pullback",
        "type": "entry"
      }
    },
    {
      "timestamp": "12:10",
      "raw_text": "market choppy, taking KR profit @ 58.75",
      "tickers": ["KR"],
      "is_trade": true,
      "trade": {
        "direction": "exit",
        "ticker": "KR",
        "price": 58.75,
        "size": 5,
        "reason": "market choppy",
        "type": "exit"
      }
    },
    {
      "timestamp": "13:30",
      "raw_text": "IREN stopped out @ 8.62 - flush reversed",
      "tickers": ["IREN"],
      "is_trade": true,
      "trade": {
        "direction": "exit",
        "ticker": "IREN",
        "price": 8.62,
        "size": 20,
        "reason": "flush reversed",
        "type": "exit"
      }
    }
  ],
  "trades": [
    {
      "timestamp": "09:49",
      "direction": "short",
      "ticker": "NKE",
      "price": 55.10,
      "size": 4,
      "reason": "D1 breakdown"
    },
    {
      "timestamp": "10:16",
      "direction": "exit",
      "ticker": "NKE",
      "price": 54.97,
      "size": 4,
      "reason": "SPY closed above VWAP+"
    },
    {
      "timestamp": "10:50",
      "direction": "short",
      "ticker": "IREN",
      "price": 8.45,
      "size": 20,
      "reason": "M5 flush"
    },
    {
      "timestamp": "11:19",
      "direction": "long",
      "ticker": "KR",
      "price": 58.20,
      "size": 5,
      "reason": "wimpy pullback held VWAP"
    },
    {
      "timestamp": "11:45",
      "direction": "short",
      "ticker": "TEAM",
      "price": 58.80,
      "size": 4,
      "reason": "anticipatory, no pullback"
    },
    {
      "timestamp": "12:10",
      "direction": "exit",
      "ticker": "KR",
      "price": 58.75,
      "size": 5,
      "reason": "market choppy"
    },
    {
      "timestamp": "13:30",
      "direction": "exit",
      "ticker": "IREN",
      "price": 8.62,
      "size": 20,
      "reason": "flush reversed"
    }
  ],
  "highlights": [
    "NKE: Watch for follow-through short if SPY confirms lower (D1 breakdown valid but entry timing off)",
    "KKR: D1 horizontal line break with volume - valid setup missed due to FOMO exit",
    "Rule: NO short entries on gap days without M5 pullback confirmation",
    "Rule: Don't exit winner on single M5 candle - need 2 stacked reds + volume",
    "Rule: NO FOMO entries - wait for M5 pullback close",
    "Bias: LPTE environment - favour shorts with confirmation, avoid anticipatory entries",
    "IREN: Flush reversal pattern - watch for compression then flush on high volume"
  ]
}

================================================================================
2. PRE-MARKET NOTES (Generated for Next Day - March 13)
================================================================================
SOURCE: Daily Report highlights + Economic Calendar + Active User Rules
GENERATED: 2026-03-13 06:45

{
  "date": "2026-03-13",
  "carry_forward": [
    "NKE: Watch for follow-through short if SPY confirms lower (D1 breakdown valid but entry timing off)",
    "KKR: D1 horizontal line break with volume - valid setup missed, watch for re-entry on pullback",
    "IREN: Compression/flush pattern - watch for high volume flush after tight range",
    "Bias: LPTE environment - favour shorts WITH confirmation, avoid anticipatory entries",
    "Market context: SPY at key level - PDL holds? If breaks, trend day down likely"
  ],
  "economic_events": [
    {
      "time": "08:30",
      "event": "CPI MoM",
      "impact": "HIGH",
      "forecast": "0.4%",
      "prior": "0.3%"
    },
    {
      "time": "08:30",
      "event": "CPI YoY",
      "impact": "HIGH",
      "forecast": "3.1%",
      "prior": "3.0%"
    },
    {
      "time": "10:00",
      "event": "Initial Jobless Claims",
      "impact": "MEDIUM",
      "forecast": "210K",
      "prior": "209K"
    }
  ],
  "user_rules": [
    "NO FOMO entries - wait for M5 pullback close",
    "Don't exit winner on single M5 candle - need 2 stacked reds + volume confirmation",
    "NO short entries on gap days without M5 pullback confirmation",
    "No anticipatory entries - wait for trigger candle close"
  ],
  "watchlist_candidates": [
    "NKE (D1 breakdown, need SPY confirmation)",
    "KKR (D1 horizontal break, pullback entry)",
    "IREN (compression, high volume flush candidate)",
    "SPY key levels: PDL 432.50, VWAP 433.20, 200 SMA 435.80"
  ]
}

================================================================================
3. WEEKLY REVIEW (Generated Saturday - Week 11, Mar 10-14)
================================================================================
SOURCE: 5 Daily Reports (Mon-Fri) + User Confirmed Metrics
GENERATED: 2026-03-15 10:00

{
  "week": "W11",
  "date_range": ["2026-03-10", "2026-03-14"],
  "trading_days": 5,
  "total_trades": 23,
  "net_r": 1.8,
  "win_rate": 0.52,
  "pattern_suggestions": [
    {
      "pattern": "FOMO entries on gap days without M5 pullback confirmation",
      "supporting_days": ["2026-03-10", "2026-03-11", "2026-03-12", "2026-03-14"],
      "evidence_quotes": [
        "was a FOMO entry on NKE. Didnt wait for market confirmation of moving lower",
        "FOMO and panic out, Dave gets beautiful short on TSLA which I identified earlier",
        "chased IREN flush at 10:50 without confirmation",
        "FOMO TEAM short at 10:12 - entered anticipatory trade"
      ],
      "frequency": 4,
      "user_confirmed": null
    },
    {
      "pattern": "Early exit on winners due to single M5 candle fear",
      "supporting_days": ["2026-03-10", "2026-03-12", "2026-03-13"],
      "evidence_quotes": [
        "exited early on M5 shooting star - should have held for VWAP test",
        "exit NKE @ 54.97 - i don't like that SPY closed above VWAP+ this was a LPTE trade",
        "scared exit on FSLY - single red candle on M5, bounced immediately after"
      ],
      "frequency": 3,
      "user_confirmed": null
    },
    {
      "pattern": "Tall bounces on shorts = avoid shorts that day",
      "supporting_days": ["2026-03-10", "2026-03-12", "2026-03-14"],
      "evidence_quotes": [
        "not many leakers today - lots of tall bounces on shorts",
        "today was just not a good day for shorts - many tall bounces",
        "shorts keeps having tall bounces all day - market not trending down cleanly"
      ],
      "frequency": 3,
      "user_confirmed": null
    },
    {
      "pattern": "VWAP rejection longs work in HPTE",
      "supporting_days": ["2026-03-11", "2026-03-13"],
      "evidence_quotes": [
        "FSLY perfect early rally thru D1 8 EMA but had deep pullback back below before rallying - VWAP hold",
        "JPM VWAP rejection on M5 - clean bounce to ATRH"
      ],
      "frequency": 2,
      "user_confirmed": null
    },
    {
      "pattern": "Grinder/leaker shorts need wimpy pullback confirmation",
      "supporting_days": ["2026-03-11", "2026-03-14"],
      "evidence_quotes": [
        "BA ENTG KKR - Dave entered BA and it performed really nicely - leaker pattern",
        "KR wimpy pullback held VWAP - good long, but for short need opposite: wimpy pullback to VWAP then fail"
      ],
      "frequency": 2,
      "user_confirmed": null
    }
  ],
  "metric_tracking": {
    "FOMO_frequency": {
      "metric": "FOMO_frequency",
      "series": [
        {"date": "2026-03-10", "value": 2},
        {"date": "2026-03-11", "value": 1},
        {"date": "2026-03-12", "value": 3},
        {"date": "2026-03-13", "value": 1},
        {"date": "2026-03-14", "value": 2}
      ],
      "weekly_avg": 1.8,
      "trend": "stable_high"
    },
    "early_exit_instances": {
      "metric": "early_exit_instances",
      "series": [
        {"date": "2026-03-10", "value": 1},
        {"date": "2026-03-11", "value": 0},
        {"date": "2026-03-12", "value": 1},
        {"date": "2026-03-13", "value": 1},
        {"date": "2026-03-14", "value": 0}
      ],
      "weekly_avg": 0.6,
      "trend": "stable"
    },
    "VWAP_rejection_HPTE_winrate": {
      "metric": "VWAP_rejection_HPTE_winrate",
      "series": [
        {"date": "2026-03-11", "value": 1.0, "sample": 2},
        {"date": "2026-03-13", "value": 1.0, "sample": 1}
      ],
      "weekly_avg": 1.0,
      "trend": "insufficient_data"
    },
    "market_condition_accuracy": {
      "metric": "market_condition_accuracy",
      "series": [
        {"date": "2026-03-10", "value": "correct", "bias": "LPTE", "actual": "LPTE"},
        {"date": "2026-03-11", "value": "correct", "bias": "HPTE", "actual": "HPTE"},
        {"date": "2026-03-12", "value": "correct", "bias": "LPTE", "actual": "LPTE"},
        {"date": "2026-03-13", "value": "correct", "bias": "LPTE", "actual": "LPTE"},
        {"date": "2026-03-14", "value": "partial", "bias": "chop", "actual": "LPTE"}
      ],
      "weekly_accuracy": 0.8,
      "trend": "good"
    }
  },
  "user_notes": ""
}

================================================================================
4. WEEKLY REVIEW - AFTER USER CONFIRMATION (Sunday)
================================================================================
USER ACTIONS in Streamlit Weekly Review page:
- Pattern 1: CONFIRMED → "FOMO entry without pullback" (added to active rules)
- Pattern 2: CONFIRMED → "Early exit on single candle fear"
- Pattern 3: CONFIRMED → "Tall bounces on shorts = avoid shorts"
- Pattern 4: CONFIRMED → "VWAP rejection longs in HPTE"
- Pattern 5: DISMISSED (not distinct enough from pattern 2)
- Added metric: "pullback_quality_score" (wimpy vs strong - from your words)

{
  "week": "W11",
  "date_range": ["2026-03-10", "2026-03-14"],
  "pattern_suggestions": [
    {
      "pattern": "FOMO entry without pullback",
      "supporting_days": ["2026-03-10", "2026-03-11", "2026-03-12", "2026-03-14"],
      "evidence_quotes": [...],
      "frequency": 4,
      "user_confirmed": true,
      "confirmed_at": "2026-03-15T14:30:00",
      "added_to_rules": true
    },
    {
      "pattern": "Early exit on single candle fear",
      "supporting_days": ["2026-03-10", "2026-03-12", "2026-03-13"],
      "evidence_quotes": [...],
      "frequency": 3,
      "user_confirmed": true,
      "confirmed_at": "2026-03-15T14:32:00",
      "added_to_rules": true
    },
    {
      "pattern": "Tall bounces on shorts = avoid shorts",
      "supporting_days": ["2026-03-10", "2026-03-12", "2026-03-14"],
      "evidence_quotes": [...],
      "frequency": 3,
      "user_confirmed": true,
      "confirmed_at": "2026-03-15T14:33:00",
      "added_to_rules": true
    },
    {
      "pattern": "VWAP rejection longs work in HPTE",
      "supporting_days": ["2026-03-11", "2026-03-13"],
      "evidence_quotes": [...],
      "frequency": 2,
      "user_confirmed": true,
      "confirmed_at": "2026-03-15T14:34:00",
      "added_to_rules": true
    }
  ],
  "active_rules_for_next_week": [
    "NO FOMO entries - wait for M5 pullback close",
    "Don't exit winner on single M5 candle - need 2 stacked reds + volume",
    "NO short entries on gap days without M5 pullback confirmation",
    "No anticipatory entries - wait for trigger candle close",
    "If tall bounces on shorts all day = avoid shorts"
  ],
  "metric_tracking": {
    "FOMO_frequency": {...},
    "early_exit_instances": {...},
    "VWAP_rejection_HPTE_winrate": {...},
    "market_condition_accuracy": {...},
    "pullback_quality_score": {
      "metric": "pullback_quality_score",
      "series": [],
      "weekly_avg": null,
      "trend": "new"
    }
  },
  "user_notes": "Week 11: FOMO still high (1.8/day). Rule adoption started Thursday - Friday showed improvement (only 1 FOMO vs 3 on Mon). Tall bounce pattern clear - need systematic short filter. VWAP rejection in HPTE 3/3 this week - double down next week."
}

================================================================================
5. MONTHLY TRAJECTORY (Generated Month-End - March 2026)
================================================================================
SOURCE: 4 Weekly Reviews (W10-W13) + Confirmed Patterns + Metrics
GENERATED: 2026-03-29 10:00

{
  "month": "2026-03",
  "date_range": ["2026-03-02", "2026-03-28"],
  "trading_days": 19,
  "total_trades": 87,
  "net_r": 12.4,
  "win_rate": 0.58,
  "max_drawdown_r": -3.2,
  "weekly_summaries": [
    {"week": "W10", "net_r": 2.1, "wr": 0.65, "trades": 18, "key_insight": "HPTE longs working, shorts challenged"},
    {"week": "W11", "net_r": 1.8, "wr": 0.52, "trades": 23, "key_insight": "FOMO high (1.8/day), tall bounce pattern identified"},
    {"week": "W12", "net_r": 4.2, "wr": 0.61, "trades": 22, "key_insight": "Rule adoption showing - FOMO down to 0.8/day"},
    {"week": "W13", "net_r": 4.3, "wr": 0.56, "trades": 24, "key_insight": "VWAP rejection HPTE 8/8, grinder longs consistent"}
  ],
  "confirmed_patterns_evolution": [
    {
      "pattern": "FOMO entry without pullback",
      "first_seen": "W10",
      "frequency_trend": "W10: 2.5/day → W11: 1.8/day → W12: 0.8/day → W13: 0.3/day",
      "status": "resolving",
      "rule_active_since": "W11"
    },
    {
      "pattern": "Early exit on single candle fear",
      "first_seen": "W10",
      "frequency_trend": "W10: 1.2/day → W11: 0.6/day → W12: 0.4/day → W13: 0.5/day",
      "status": "improving",
      "rule_active_since": "W11"
    },
    {
      "pattern": "Tall bounces on shorts = avoid shorts",
      "first_seen": "W10",
      "frequency_trend": "W10: 0.8/day → W11: 0.6/day → W12: 0.3/day → W13: 0.1/day",
      "status": "resolved",
      "rule_active_since": "W11"
    },
    {
      "pattern": "VWAP rejection longs work in HPTE",
      "first_seen": "W11",
      "frequency_trend": "W11: 1.5/day → W12: 2.0/day → W13: 2.0/day",
      "status": "strengthening",
      "rule_active_since": "W11"
    }
  ],
  "setup_performance_by_condition": {
    "VWAP_rejection_HPTE": {"trades": 14, "wins": 12, "wr": 0.86, "avg_r": 1.8},
    "Break_horizontal_HPTE": {"trades": 8, "wins": 5, "wr": 0.63, "avg_r": 1.2},
    "Grinder_long_HPTE": {"trades": 6, "wins": 5, "wr": 0.83, "avg_r": 1.5},
    "Short_LPTE": {"trades": 18, "wins": 8, "wr": 0.44, "avg_r": -0.3},
    "FOMO_entries": {"trades": 31, "wins": 12, "wr": 0.39, "avg_r": -0.7}
  },
  "summary": "March: Major shift from chaotic FOMO-driven trading (Week 10) to rule-based execution (Week 13). FOMO frequency dropped 88% after Week 11 rule adoption. Best edge: VWAP rejection longs in HPTE (86% WR, 1.8R). Short side remains negative expectancy - tall bounce filter working but shorts still challenged in transitional markets. Grinder longs emerging as consistent secondary setup. Net +12.4R best month YTD.",
  "focus_areas_next_month": [
    "Test grinder/pullback entries in HPTE systematically (track separately)",
    "Develop short selection filter: require wimpy pullback fail + volume confirmation",
    "Maintain FOMO discipline - target <0.2/day",
    "Track pullback quality score (wimpy/strong) as new metric"
  ]
}

================================================================================
6. STREAMLIT UI PREVIEWS
================================================================================

--- DAILY REPORT PAGE ---
┌─────────────────────────────────────────────────────────────────────────────┐
│  Daily Report  |  2026-03-12  ▼  [Prev Day] [Today] [Next Day]              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MARKET NOTES (Review yesterday's calls)                        [7 trades] │
│  ├─ 09:30  SPY gap down, watching NKE short - D1 breakdown into gap       │
│  ├─ 09:35  NKE D1 looks weak, but SPY gapped down - need market confir... │
│  ├─ 09:49  🔴 FOMO entry NKE short @ 55.10, 4 shares - D1 breakdown       │
│  ├─ 09:55  NKE holding VWAP-, SPY bouncing off PDL                        │
│  ├─ 10:02  KKR breaking D1 horizontal line with volume - watching...      │
│  ├─ 10:16  🟢 exit NKE @ 54.97 - SPY closed above VWAP+, don't like this  │
│  ├─ 10:35  FOMO and panic out of KKR, Dave gets beautiful short on TSLA.. │
│  ├─ 10:42  IREN compressing on M5 - watching for flush short              │
│  ├─ 10:50  🔴 CHASED IREN flush short @ 8.45, 20 shares - no confirmation │
│  ├─ 11:07  wait for this candle to close, ideally on its low near LOD    │
│  ├─ 11:19  🟢 swinging KR long @ 58.20, 5 shares - wimpy pullback held... │
│  ├─ 11:45  🔴 TEAM short @ 58.80, 4 shares - anticipatory, no pullback    │
│  ├─ 12:10  🟢 market choppy, taking KR profit @ 58.75                     │
│  └─ 13:30  🔴 IREN stopped out @ 8.62 - flush reversed                    │
│                                                                             │
│  TRADES EXTRACTED                                                           │
│  ┌────┬─────┬────┬───────┬─────┬────────────────────────────────────────┐ │
│  │Time│ Dir │Sym │ Price │Size │ Reason                                   │ │
│  ├────┼─────┼────┼───────┼─────┼────────────────────────────────────────┤ │
│  │09:49│ S   │NKE │ 55.10 │  4  │ D1 breakdown                             │ │
│  │10:16│ X   │NKE │ 54.97 │  4  │ SPY closed above VWAP+                  │ │
│  │10:50│ S   │IREN│  8.45 │ 20  │ M5 flush                                 │ │
│  │11:19│ L   │KR  │ 58.20 │  5  │ wimpy pullback held VWAP                 │ │
│  │11:45│ S   │TEAM│ 58.80 │  4  │ anticipatory, no pullback               │ │
│  │12:10│ X   │KR  │ 58.75 │  5  │ market choppy                            │ │
│  │13:30│ X   │IREN│  8.62 │ 20  │ flush reversed                           │ │
│  └────┴─────┴────┴───────┴─────┴────────────────────────────────────────┘ │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  PRE-MARKET NOTES FOR TODAY (2026-03-13)                                    │
│  ════════════════════════════════════════════════════════════════════════   │
│  📌 CARRY-FORWARD                                                          │
│  • NKE: Watch for follow-through short if SPY confirms lower               │
│  • KKR: D1 horizontal line break with volume - valid setup missed          │
│  • IREN: Compression/flush pattern - watch for high volume flush           │
│  • Bias: LPTE - favour shorts WITH confirmation, avoid anticipatory        │
│  • SPY key: PDL 432.50 | VWAP 433.20 | 200 SMA 435.80                     │
│                                                                             │
│  📅 ECONOMIC EVENTS (Major only)                                           │
│  • 08:30  CPI MoM (HIGH) - Forecast 0.4% | Prior 0.3%                     │
│  • 08:30  CPI YoY (HIGH) - Forecast 3.1% | Prior 3.0%                     │
│  • 10:00  Initial Jobless Claims (MEDIUM) - Forecast 210K | Prior 209K    │
│                                                                             │
│  ⚡ ACTIVE RULES                                                            │
│  • NO FOMO entries - wait for M5 pullback close                            │
│  • Don't exit winner on single M5 candle - need 2 stacked reds + vol       │
│  • NO short entries on gap days without M5 pullback confirmation           │
│  • No anticipatory entries - wait for trigger candle close                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

--- WEEKLY REVIEW PAGE ---
┌─────────────────────────────────────────────────────────────────────────────┐
│  Weekly Review  |  W11 (Mar 10-14)  ▼  [Confirm Patterns] [Metrics] [Notes]│
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STATS: 5 days | 23 trades | Net +1.8R | 52% WR | Max DD -1.4R            │
│                                                                             │
│  ───── PATTERN SUGGESTIONS (Click to Confirm/Dismiss) ─────               │
│                                                                             │
│  ☐ FOMO entry without pullback                    [4 days] [CONFIRM]      │
│     "was a FOMO entry on NKE. Didnt wait for market confirmation..."       │
│     "FOMO and panic out, Dave gets beautiful short on TSLA..."             │
│     "chased IREN flush at 10:50 without confirmation"                      │
│     "FOMO TEAM short at 10:12 - entered anticipatory trade"                │
│                                                                             │
│  ☐ Early exit on single candle fear                 [3 days] [CONFIRM]    │
│     "exited early on M5 shooting star - should have held for VWAP test"    │
│     "exit NKE @ 54.97 - i don't like that SPY closed above VWAP+"          │
│     "scared exit on FSLY - single red candle on M5, bounced immediately"   │
│                                                                             │
│  ☐ Tall bounces on shorts = avoid shorts            [3 days] [CONFIRM]    │
│     "not many leakers today - lots of tall bounces on shorts"              │
│     "today was just not a good day for shorts - many tall bounces"         │
│     "shorts keeps having tall bounces all day - market not trending..."    │
│                                                                             │
│  ☐ VWAP rejection longs work in HPTE                [2 days] [CONFIRM]    │
│     "FSLY perfect early rally thru D1 8 EMA... VWAP hold"                  │
│     "JPM VWAP rejection on M5 - clean bounce to ATRH"                      │
│                                                                             │
│  ☐ Grinder/leaker shorts need wimpy pullback...     [2 days] [DISMISS]    │
│                                                                             │
│  ───── METRIC TRACKING (Your Subprojects) ─────                           │
│                                                                             │
│  FOMO Frequency          ████████████░░░░  1.8/day  (target <0.5)        │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Mon Tue Wed Thu Fri  │  2   1   3   1   2  →  Rule adopted Thu      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  Early Exit Instances    ████░░░░░░░░░░  0.6/day  (target 0)            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  Mon Tue Wed Thu Fri  │  1   0   1   1   0                          │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  VWAP Rejection HPTE WR  ████████████████  100%   (3/3 this week)        │
│                                                                             │
│  Market Condition Acc.   ██████████████░░  80%   (4/5 correct)           │
│                                                                             │
│  [+ Add Metric]  [Pullback Quality]  [Short Filter Effectiveness]        │
│                                                                             │
│  ───── YOUR WEEKLY NOTES ─────                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ Week 11: FOMO still high...                                          │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
END OF EXAMPLES
================================================================================