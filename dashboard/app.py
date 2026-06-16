import os
import sys
from datetime import date

import pandas as pd
import streamlit as st

# Add parent dir to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import (
    BacktestEquityCurve,
    BacktestRejectedTrade,
    BacktestRun,
    BacktestTrade,
    Run,
    Signal,
    get_session,
    init_db,
)
from main import run_analysis
from strategy.backtester import run_backtest


st.set_page_config(page_title="t212-signal-lab", layout="wide")

TERMINAL_CSS = """
<style>
:root {
    --terminal-bg: #020403;
    --terminal-panel: #06110b;
    --terminal-green: #39ff88;
    --terminal-dim: #7bdba2;
    --terminal-line: rgba(57, 255, 136, 0.34);
    --terminal-red: #ff4d6d;
    --terminal-yellow: #ffe66d;
}

.stApp {
    background:
        linear-gradient(rgba(57, 255, 136, 0.025) 50%, rgba(0, 0, 0, 0.025) 50%),
        var(--terminal-bg);
    background-size: 100% 4px;
    color: var(--terminal-green);
}

html, body, [class*="css"] {
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
}

section[data-testid="stSidebar"] {
    background: #000;
    border-right: 1px solid var(--terminal-line);
}

h1, h2, h3, p, label, span, div {
    color: var(--terminal-green);
}

h1, h2, h3 {
    letter-spacing: 0;
    text-transform: uppercase;
}

h2 {
    border-bottom: 1px solid var(--terminal-line);
    padding-bottom: 0.35rem;
}

div[data-testid="stMetric"],
div[data-testid="stDataFrame"],
div[data-testid="stAlert"],
.terminal-panel {
    background: rgba(6, 17, 11, 0.92);
    border: 1px solid var(--terminal-line);
    border-radius: 0;
    box-shadow: 0 0 18px rgba(57, 255, 136, 0.08);
}

div[data-testid="stMetric"] {
    padding: 0.75rem;
}

div[data-testid="stMetricLabel"],
div[data-testid="stMetricValue"],
div[data-testid="stMetricDelta"] {
    color: var(--terminal-green);
}

.stDataFrame {
    border: 1px solid var(--terminal-line);
}

button, [data-baseweb="select"] > div, [data-baseweb="tag"] {
    background: #000;
    border-color: var(--terminal-line);
    border-radius: 0;
    color: var(--terminal-green);
}

code, pre {
    color: var(--terminal-green);
    background: #000;
}

.terminal-title {
    color: var(--terminal-green);
    font-size: 0.92rem;
    line-height: 1.05;
    margin: 0 0 1.15rem 0;
    text-shadow: 0 0 10px rgba(57, 255, 136, 0.65);
    white-space: pre;
}

.terminal-panel {
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
}

.terminal-line {
    color: var(--terminal-dim);
    margin: 0.15rem 0;
}

.status-buy {
    color: var(--terminal-green);
}

.status-watch {
    color: var(--terminal-yellow);
}

.status-skip {
    color: var(--terminal-red);
}

.bankrupt-alert {
    background: rgba(255, 77, 109, 0.18);
    border: 1px solid var(--terminal-red);
    color: var(--terminal-red);
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
    text-transform: uppercase;
}
</style>
"""

ASCII_HEADER = r"""
 _______  ___   __   __  _______  ___      _______  _______
|       ||   | |  |_|  ||       ||   |    |   _   ||  _    |
|_     _||   | |       ||    ___||   |    |  |_|  || |_|   |
  |   |  |   | |       ||   |___ |   |    |       ||       |
  |   |  |   | |       ||    ___||   |___ |       ||  _   |
  |   |  |   | | ||_|| ||   |___ |       ||   _   || |_|   |
  |___|  |___| |_|   |_||_______||_______||__| |__||_______|
"""


def format_pct(value):
    if value is None:
        return "0.00%"
    return f"{value:.2f}%"


def format_num(value):
    if value is None:
        return "0.00"
    return f"{value:.2f}"


def signal_class(action):
    return {
        "BUY": "status-buy",
        "WATCH": "status-watch",
        "SKIP": "status-skip",
    }.get(action, "status-watch")


st.markdown(TERMINAL_CSS, unsafe_allow_html=True)
st.markdown(f"<pre class='terminal-title'>{ASCII_HEADER}</pre>", unsafe_allow_html=True)

init_db()
session = get_session()

st.sidebar.markdown("## FILTERS")
action_filter = st.sidebar.multiselect("ACTION", ["BUY", "WATCH", "SKIP", "SELL"], default=["BUY", "WATCH"])
risk_filter = st.sidebar.multiselect("RISK", ["LOW", "MEDIUM", "HIGH"], default=["LOW", "MEDIUM", "HIGH"])

st.sidebar.markdown("## SIGNAL CONTROL")
if st.sidebar.button("RUN SIGNALS", use_container_width=True):
    with st.spinner("RUNNING SIGNAL SCAN..."):
        try:
            run_analysis()
            st.sidebar.success("SIGNALS UPDATED")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"SIGNAL SCAN FAILED: {exc}")

st.sidebar.markdown("## BACKTEST CONTROL")
bt_start = st.sidebar.date_input("START", value=date(2015, 1, 1))
bt_end = st.sidebar.date_input("END", value=date(2025, 12, 31))
bt_initial_capital = st.sidebar.number_input("CAPITAL", min_value=100.0, value=10000.0, step=500.0)
bt_max_days = st.sidebar.number_input("MAX_HOLD", min_value=1, max_value=252, value=30, step=1)
bt_max_positions = st.sidebar.number_input("MAX_POSITIONS", min_value=1, max_value=50, value=5, step=1)
bt_position_pct = st.sidebar.number_input("MAX_POS_PCT", min_value=0.01, max_value=1.0, value=0.20, step=0.01)
bt_slippage = st.sidebar.number_input("SPREAD_SLIPPAGE", min_value=0.0, max_value=0.10, value=0.001, step=0.001, format="%.4f")
bt_fx = st.sidebar.number_input("FX_COST", min_value=0.0, max_value=0.10, value=0.0, step=0.001, format="%.4f")

if st.sidebar.button("RUN BACKTEST", use_container_width=True):
    if bt_start >= bt_end:
        st.sidebar.error("START must be before END")
    else:
        with st.spinner("RUNNING BACKTEST..."):
            try:
                result = run_backtest(
                    bt_start.strftime("%Y-%m-%d"),
                    bt_end.strftime("%Y-%m-%d"),
                    max_holding_days=int(bt_max_days),
                    initial_capital=float(bt_initial_capital),
                    max_positions_total=int(bt_max_positions),
                    max_position_pct=float(bt_position_pct),
                    spread_slippage_pct=float(bt_slippage),
                    currency_conversion_pct=float(bt_fx),
                )
                st.sidebar.success(f"RUN #{result.run_id} SAVED")
                if result.failed_tickers:
                    failed = ", ".join(result.failed_tickers.keys())
                    st.sidebar.warning(f"SKIPPED: {failed}")
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"BACKTEST FAILED: {exc}")

latest_run = session.query(Run).order_by(Run.timestamp.desc()).first()
latest_backtest = session.query(BacktestRun).order_by(BacktestRun.timestamp.desc()).first()

st.markdown("## SYSTEM")
if latest_run:
    st.markdown(
        "<div class='terminal-panel'>"
        f"<p class='terminal-line'>> MARKET_REGIME: {latest_run.market_regime}</p>"
        f"<p class='terminal-line'>> LAST_SCAN: {latest_run.timestamp}</p>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='terminal-panel'><p class='terminal-line'>> MARKET_REGIME: NO_RUN</p></div>",
        unsafe_allow_html=True,
    )

st.markdown("## BACKTEST")
if latest_backtest:
    if latest_backtest.bankrupt:
        st.markdown(
            "<div class='bankrupt-alert'>> ALERT: STRATEGY BANKRUPT</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div class='terminal-panel'>"
        f"<p class='terminal-line'>> RUN: #{latest_backtest.id}</p>"
        f"<p class='terminal-line'>> PERIOD: {latest_backtest.start_date} / {latest_backtest.end_date}</p>"
        f"<p class='terminal-line'>> UPDATED: {latest_backtest.timestamp}</p>"
        f"<p class='terminal-line'>> INITIAL_CAPITAL: {format_num(latest_backtest.initial_capital)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cols[0].metric("STRATEGY_RETURN", format_pct(latest_backtest.total_return))
    cols[1].metric("CAGR", format_pct(latest_backtest.cagr))
    cols[2].metric("SHARPE", format_num(latest_backtest.sharpe))
    cols[3].metric("SORTINO", format_num(latest_backtest.sortino))

    cols = st.columns(4)
    cols[0].metric("MAX_DRAWDOWN", format_pct(latest_backtest.max_drawdown))
    cols[1].metric("CALMAR", format_num(latest_backtest.calmar))
    cols[2].metric("AVG_HOLDING_DAYS", format_num(latest_backtest.avg_holding_days))
    cols[3].metric("MAX_CONCURRENT_POSITIONS", latest_backtest.max_concurrent_positions or 0)

    cols = st.columns(4)
    cols[0].metric("TRADES_CLOSED", latest_backtest.total_trades)
    cols[1].metric("SIGNALS_GENERATED", latest_backtest.generated_signals or 0)
    cols[2].metric("TRADES_REJECTED", latest_backtest.rejected_trades or 0)
    cols[3].metric("WIN_RATE", format_pct(latest_backtest.win_rate))

    cols = st.columns(4)
    cols[0].metric("PROFIT_FACTOR", format_num(latest_backtest.profit_factor))
    cols[1].metric("EXPECTANCY", format_pct(latest_backtest.expectancy))
    cols[2].metric("BENCHMARK_RETURN", format_pct(latest_backtest.benchmark_return or latest_backtest.spy_return))
    cols[3].metric("ALPHA_VS_SPY", format_pct(latest_backtest.alpha_vs_spy))

    equity_rows = (
        session.query(BacktestEquityCurve)
        .filter(BacktestEquityCurve.run_id == latest_backtest.id)
        .order_by(BacktestEquityCurve.date.asc())
        .all()
    )
    if equity_rows:
        equity_df = pd.DataFrame(
            [
                {
                    "DATE": row.date,
                    "EQUITY": row.equity,
                    "DRAWDOWN_%": row.drawdown_pct,
                    "CASH": row.cash,
                    "OPEN_POSITIONS": row.open_positions,
                    "DAILY_RETURN_%": row.daily_return,
                }
                for row in equity_rows
            ]
        )
        chart_df = equity_df.set_index("DATE")[["EQUITY"]]
        st.markdown("## EQUITY CURVE")
        st.line_chart(chart_df, use_container_width=True)

        st.markdown("## DRAWDOWN CURVE")
        st.line_chart(equity_df.set_index("DATE")[["DRAWDOWN_%"]], use_container_width=True)

        monthly = equity_df.copy()
        monthly["DATE"] = pd.to_datetime(monthly["DATE"])
        monthly["MONTH"] = monthly["DATE"].dt.to_period("M").astype(str)
        monthly_returns = (
            monthly.groupby("MONTH")["EQUITY"]
            .agg(["first", "last"])
            .assign(RETURN_PCT=lambda df: (df["last"] / df["first"] - 1) * 100)
            .reset_index()[["MONTH", "RETURN_PCT"]]
        )
        st.markdown("## MONTHLY RETURNS")
        st.dataframe(monthly_returns, use_container_width=True, hide_index=True)

    trades = (
        session.query(BacktestTrade)
        .filter(BacktestTrade.run_id == latest_backtest.id)
        .order_by(BacktestTrade.signal_date.desc())
        .limit(80)
        .all()
    )
    if trades:
        st.markdown("## CLOSED TRADES")
        trades_df = pd.DataFrame(
            [
                {
                    "SIG_DATE": t.signal_date,
                    "TICKER": t.ticker,
                    "REGIME": t.market_regime,
                    "ENTRY": t.entry_date,
                    "EXIT": t.exit_date,
                    "REASON": t.exit_reason,
                    "RET_%": round(t.return_pct, 2),
                    "PNL": round(t.pnl, 2),
                    "HOLD": t.holding_days,
                    "SCORE": round(t.final_score, 2),
                }
                for t in trades
            ]
        )
        st.dataframe(trades_df, use_container_width=True, hide_index=True)

    rejected = (
        session.query(BacktestRejectedTrade)
        .filter(BacktestRejectedTrade.run_id == latest_backtest.id)
        .order_by(BacktestRejectedTrade.signal_date.desc())
        .limit(80)
        .all()
    )
    if rejected:
        st.markdown("## REJECTED TRADES")
        rejected_df = pd.DataFrame(
            [
                {
                    "SIG_DATE": row.signal_date,
                    "TICKER": row.ticker,
                    "ACTION": row.action,
                    "REASON": row.reason,
                    "SCORE": round(row.final_score, 2) if row.final_score is not None else None,
                }
                for row in rejected
            ]
        )
        st.dataframe(rejected_df, use_container_width=True, hide_index=True)
else:
    st.markdown(
        "<div class='terminal-panel'><p class='terminal-line'>> BACKTEST: EMPTY</p></div>",
        unsafe_allow_html=True,
    )

st.markdown("## SIGNALS")
if latest_run:
    query = session.query(Signal).filter(Signal.run_id == latest_run.id)
else:
    query = session.query(Signal)

if action_filter:
    query = query.filter(Signal.action.in_(action_filter))
if risk_filter:
    query = query.filter(Signal.risk_rating.in_(risk_filter))

signals = query.order_by(Signal.date.desc(), Signal.final_score.desc()).limit(100).all()

if signals:
    signal_rows = []
    for signal in signals:
        signal_rows.append(
            {
                "TICKER": signal.ticker,
                "ACTION": signal.action,
                "SCORE": signal.final_score,
                "RISK": signal.risk_rating,
                "ENTRY": f"{signal.entry_min} - {signal.entry_max}",
                "STOP": signal.invalidation,
                "T1": signal.target_1,
                "REASON": signal.reason,
            }
        )
    st.dataframe(pd.DataFrame(signal_rows), use_container_width=True, hide_index=True)

    selected_ticker = st.selectbox("DETAIL", [signal.ticker for signal in signals])
    selected = next(signal for signal in signals if signal.ticker == selected_ticker)
    st.markdown(
        "<div class='terminal-panel'>"
        f"<p class='terminal-line'>> TICKER: {selected.ticker}</p>"
        f"<p class='terminal-line'>> ACTION: <span class='{signal_class(selected.action)}'>{selected.action}</span></p>"
        f"<p class='terminal-line'>> TECH_SCORE: {format_num(selected.technical_score)}</p>"
        f"<p class='terminal-line'>> REGIME_SCORE: {format_num(selected.regime_score)}</p>"
        f"<p class='terminal-line'>> FINAL_SCORE: {format_num(selected.final_score)}</p>"
        f"<p class='terminal-line'>> REASON: {selected.reason}</p>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        "<div class='terminal-panel'>"
        "<p class='terminal-line'>> SIGNALS: EMPTY</p>"
        "<p class='terminal-line'>> RUN CLI: python main.py run</p>"
        "</div>",
        unsafe_allow_html=True,
    )

session.close()
