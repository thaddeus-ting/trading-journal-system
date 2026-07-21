def render_pre_market(pre: PreMarketNotes):
    """Render pre-market notes in a nice format."""
    if not pre.carry_forward and not pre.economic_events and not pre.active_rules and not pre.watchlist_candidates:
        st.info("No pre-market data available")
        return

    # Check if this pre-market was generated without a prior daily report
    has_prior_daily = True
    if pre.carry_forward:
        first_item = pre.carry_forward[0]
        if "No prior daily journal" in first_item and "showing economic events only" in first_item:
            has_prior_daily = False

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

    # Watchlist Candidates - only show if we have a prior daily report
    if has_prior_daily and pre.watchlist_candidates:
        st.markdown('<hr style="margin: 0.25rem 0; border: none; border-top: 0.1px solid white;">', unsafe_allow_html=True)
        st.markdown('<div class="premarket-section watchlist-section">', unsafe_allow_html=True)
        st.markdown("### Watchlist Candidates")
        # Extract just ticker names from "Watch X" format, filter out non-ticker items
        longs = []
        shorts = []
        for w in pre.watchlist_candidates:
            # Skip non-ticker items (Focus:, Improve:, Rule:, etc.)
            skip_prefixes = ("Focus:", "Improve:", "Rule:", "Strength:", "Market context:", "Bias:")
            if w.startswith(skip_prefixes):
                continue
            ticker = w[6:].strip() if w.startswith("Watch ") else w
            # Skip invalid tickers (RS, HOD, EOD are not valid tickers)
            if ticker.upper() in ("RS", "HOD", "EOD"):
                continue
            # Check for ' short' suffix and strip it
            if ticker.lower().endswith(" short"):
                ticker = ticker[:-6].strip()
                # Skip invalid tickers
                if ticker.upper() in ("RS", "HOD", "EOD"):
                    continue
                # Only add if valid ticker (1-5 uppercase letters)
                if re.match(r'^[A-Z]{1,5}$', ticker):
                    shorts.append(ticker)
            else:
                # Also strip ' long' suffix if present
                if ticker.lower().endswith(" long"):
                    ticker = ticker[:-5].strip()
                # Skip invalid tickers
                if ticker.upper() in ("RS", "HOD", "EOD"):
                    continue
                # Only add if valid ticker (1-5 uppercase letters)
                if re.match(r'^[A-Z]{1,5}$', ticker):
                    longs.append(ticker)

        # Sort tickers: XL* tickers (XLE, XLF, XLV, XLRE, etc.) and sector ETFs (SMH, IGV, MAGS) go to the end
        def sort_key(ticker):
            # XL* tickers (any length) and SMH, IGV, MAGS get a higher sort key so they appear at the end
            is_sector_etf = ticker.startswith("XL") or ticker in ("SMH", "IGV", "MAGS")
            return (is_sector_etf, ticker)
        longs.sort(key=sort_key)
        shorts.sort(key=sort_key)

        # Display as aligned HTML table
        if longs or shorts:
            long_str = ', '.join(longs) if longs else '—'
            short_str = ', '.join(shorts) if shorts else '—'
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
        elif pre.watchlist_candidates:
            # Fallback for non-standard formats
            all_tickers = [w[6:].strip() if w.startswith("Watch ") else w for w in pre.watchlist_candidates]
            valid_tickers = [t for t in all_tickers if re.match(r'^[A-Z]{1,5}$', t)]
            st.markdown(f"**Watch** — {', '.join(sorted(set(valid_tickers)))}")
        st.markdown('</div>', unsafe_allow_html=True)