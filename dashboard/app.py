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
    OptimizationResult,
    OptimizationRun,
    Run,
    Signal,
    get_session,
    init_db,
)
from main import run_analysis
from strategy.backtester import run_backtest, run_parameter_sweep, run_walk_forward
from strategy.engines import ETF_ROTATION_UNIVERSE
from strategy.optimizer import ROBUST_SCORE_FORMULA, build_parameter_grid, run_optimization
from strategy.diagnostics import build_diagnostics


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
ENGINE_OPTIONS = [
    "SIGNAL_ENGINE",
    "ETF_ROTATION_ENGINE",
    "ETF_ROTATION_TOP_N_ENGINE",
    "INDEX_TREND_BASELINE_ENGINE",
    "RELATIVE_STRENGTH_STOCK_ENGINE",
    "RELATIVE_STRENGTH_STOCK_ENGINE_V2",
    "BREAKOUT_52W_ENGINE",
    "PULLBACK_TREND_ENGINE",
    "LOW_VOL_DEFENSIVE_ENGINE",
    "MEAN_REVERSION_ETF_ENGINE",
    "PAIR_RELATIVE_RATIO_ENGINE",
]

bt_engine = st.sidebar.selectbox("ENGINE", ENGINE_OPTIONS)
bt_universe = st.sidebar.selectbox("UNIVERSE", ["DEFAULT", "ETF_ONLY"])
bt_start = st.sidebar.date_input("START", value=date(2015, 1, 1))
bt_end = st.sidebar.date_input("END", value=date(2025, 12, 31))
bt_initial_capital = st.sidebar.number_input("CAPITAL", min_value=100.0, value=10000.0, step=500.0)
bt_min_score = st.sidebar.number_input("MIN_SCORE", min_value=0.0, max_value=1.0, value=0.75, step=0.01)
bt_max_days = st.sidebar.number_input("MAX_HOLD", min_value=1, max_value=252, value=30, step=1)
bt_max_positions = st.sidebar.number_input("MAX_POSITIONS", min_value=1, max_value=50, value=5, step=1)
bt_position_pct = st.sidebar.number_input("MAX_POS_PCT", min_value=0.01, max_value=1.0, value=0.20, step=0.01)
bt_max_total_exposure = st.sidebar.number_input("MAX_TOTAL_EXPOSURE", min_value=0.01, max_value=1.0, value=0.30, step=0.01)
bt_slippage = st.sidebar.number_input("SPREAD_SLIPPAGE", min_value=0.0, max_value=0.10, value=0.001, step=0.001, format="%.4f")
bt_fx = st.sidebar.number_input("FX_COST", min_value=0.0, max_value=0.10, value=0.0, step=0.001, format="%.4f")
bt_benchmark = st.sidebar.selectbox("BENCHMARK", ["SPY", "QQQ"])
bt_adjusted = st.sidebar.checkbox("ADJUSTED_DATA", value=False)
bt_rebalance = st.sidebar.selectbox("REBALANCE", ["weekly", "monthly"])
bt_risk_backtest = st.sidebar.multiselect("BACKTEST_RISK", ["LOW", "MEDIUM", "HIGH"], default=["LOW", "MEDIUM", "HIGH"])

def selected_watchlist():
    if bt_universe == "ETF_ONLY" or bt_engine in {"ETF_ROTATION_ENGINE", "ETF_ROTATION_TOP_N_ENGINE", "LOW_VOL_DEFENSIVE_ENGINE", "MEAN_REVERSION_ETF_ENGINE", "PAIR_RELATIVE_RATIO_ENGINE", "INDEX_TREND_BASELINE_ENGINE"}:
        return ETF_ROTATION_UNIVERSE
    return None

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
                    min_score=float(bt_min_score),
                    allowed_risk_ratings=bt_risk_backtest,
                    max_total_exposure=float(bt_max_total_exposure),
                    spread_slippage_pct=float(bt_slippage),
                    currency_conversion_pct=float(bt_fx),
                    use_adjusted_data=bt_adjusted,
                    benchmark_ticker=bt_benchmark,
                    strategy_name=bt_engine,
                    strategy_version=f"ui_{bt_min_score:.2f}",
                    strategy_engine=bt_engine,
                    rebalance_frequency=bt_rebalance,
                    watchlist=selected_watchlist(),
                )
                st.sidebar.success(f"RUN #{result.run_id} SAVED")
                if result.failed_tickers:
                    failed = ", ".join(result.failed_tickers.keys())
                    st.sidebar.warning(f"SKIPPED: {failed}")
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"BACKTEST FAILED: {exc}")

if st.sidebar.button("RUN SWEEP", use_container_width=True):
    with st.spinner("RUNNING PARAMETER SWEEP..."):
        try:
            rows = run_parameter_sweep(
                bt_start.strftime("%Y-%m-%d"),
                bt_end.strftime("%Y-%m-%d"),
                watchlist=selected_watchlist(),
                strategy_engine=bt_engine,
                initial_capital=float(bt_initial_capital),
                max_positions_total=int(bt_max_positions),
                max_position_pct=float(bt_position_pct),
                allowed_risk_ratings=bt_risk_backtest,
                max_total_exposure=float(bt_max_total_exposure),
                spread_slippage_pct=float(bt_slippage),
                currency_conversion_pct=float(bt_fx),
                use_adjusted_data=bt_adjusted,
                benchmark_ticker=bt_benchmark,
                rebalance_frequency=bt_rebalance,
            )
            st.session_state["sweep_rows"] = rows
            st.sidebar.success("SWEEP COMPLETE")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"SWEEP FAILED: {exc}")

if st.sidebar.button("RUN WALK_FORWARD", use_container_width=True):
    with st.spinner("RUNNING WALK-FORWARD..."):
        try:
            rows = run_walk_forward(
                watchlist=selected_watchlist(),
                strategy_engine=bt_engine,
                initial_capital=float(bt_initial_capital),
                max_positions_total=int(bt_max_positions),
                max_position_pct=float(bt_position_pct),
                min_score=float(bt_min_score),
                allowed_risk_ratings=bt_risk_backtest,
                max_total_exposure=float(bt_max_total_exposure),
                spread_slippage_pct=float(bt_slippage),
                currency_conversion_pct=float(bt_fx),
                use_adjusted_data=bt_adjusted,
                benchmark_ticker=bt_benchmark,
                rebalance_frequency=bt_rebalance,
            )
            st.session_state["walk_forward_rows"] = rows
            st.sidebar.success("WALK_FORWARD COMPLETE")
            st.rerun()
        except Exception as exc:
            st.sidebar.error(f"WALK_FORWARD FAILED: {exc}")

st.sidebar.markdown("## OPTIMIZER")
opt_engine = st.sidebar.selectbox("OPT_ENGINE", ENGINE_OPTIONS, index=ENGINE_OPTIONS.index(bt_engine))
opt_universe = st.sidebar.selectbox("OPT_UNIVERSE", ["DEFAULT", "ETF_ONLY"])
opt_benchmark = st.sidebar.selectbox("OPT_BENCHMARK", ["SPY", "QQQ"])
opt_adjusted = st.sidebar.checkbox("OPT_ADJUSTED_DATA", value=bt_adjusted)
opt_start = st.sidebar.date_input("OPT_START", value=bt_start)
opt_end = st.sidebar.date_input("OPT_END", value=bt_end)
opt_mode = st.sidebar.selectbox("OPT_MODE", ["single_period", "walk_forward"])
opt_confirm_large = st.sidebar.checkbox("CONFIRM >500 COMBOS", value=False)

opt_min_score_start = st.sidebar.number_input("MIN_SCORE_START", 0.0, 1.0, 0.70, 0.01)
opt_min_score_end = st.sidebar.number_input("MIN_SCORE_END", 0.0, 1.0, 0.90, 0.01)
opt_min_score_step = st.sidebar.number_input("MIN_SCORE_STEP", 0.01, 0.50, 0.05, 0.01)
opt_hold_start = st.sidebar.number_input("HOLD_START", 1, 252, 10, 1)
opt_hold_end = st.sidebar.number_input("HOLD_END", 1, 252, 60, 1)
opt_hold_step = st.sidebar.number_input("HOLD_STEP", 1, 252, 10, 1)
opt_max_positions = st.sidebar.multiselect("OPT_MAX_POSITIONS", [1, 2, 3, 5, 8, 10], default=[3, 5])
opt_position_pct = st.sidebar.multiselect("OPT_MAX_POS_PCT", [0.05, 0.10, 0.20, 0.30], default=[0.10, 0.20])
opt_total_exposure = st.sidebar.multiselect("OPT_MAX_EXPOSURE", [0.30, 0.50, 1.00], default=[0.30, 0.50])
opt_top_n = st.sidebar.multiselect("OPT_TOP_N", [1, 2, 3, 5], default=[2, 3])
opt_rebalance = st.sidebar.multiselect("OPT_REBALANCE", ["weekly", "monthly"], default=["weekly"])
opt_slippage = st.sidebar.multiselect("OPT_SLIPPAGE", [0.0, 0.001, 0.002], default=[0.001])
opt_fx = st.sidebar.multiselect("OPT_FX", [0.0, 0.001, 0.002], default=[0.0])
opt_sma_filter = st.sidebar.multiselect("OPT_SMA200", [True, False], default=[True])
opt_vol_penalty = st.sidebar.multiselect("OPT_VOL_PENALTY", [0.5, 1.0, 2.0], default=[1.0])

def optimizer_watchlist():
    if opt_universe == "ETF_ONLY" or opt_engine in {"ETF_ROTATION_TOP_N_ENGINE", "LOW_VOL_DEFENSIVE_ENGINE", "MEAN_REVERSION_ETF_ENGINE", "PAIR_RELATIVE_RATIO_ENGINE", "INDEX_TREND_BASELINE_ENGINE"}:
        return ETF_ROTATION_UNIVERSE
    return None

def optimizer_param_ranges():
    return {
        "min_score": {"start": opt_min_score_start, "end": opt_min_score_end, "step": opt_min_score_step},
        "max_holding_days": {"start": int(opt_hold_start), "end": int(opt_hold_end), "step": int(opt_hold_step)},
        "max_positions_total": {"values": opt_max_positions or [5]},
        "max_position_pct": {"values": opt_position_pct or [0.20]},
        "max_total_exposure": {"values": opt_total_exposure or [0.30]},
        "top_n": {"values": opt_top_n or [3]},
        "rebalance_frequency": {"values": opt_rebalance or ["weekly"]},
        "spread_slippage_pct": {"values": opt_slippage or [0.001]},
        "currency_conversion_pct": {"values": opt_fx or [0.0]},
        "use_sma200_filter": {"values": opt_sma_filter or [True]},
        "volatility_penalty_weight": {"values": opt_vol_penalty or [1.0]},
    }

if st.sidebar.button("PREVIEW COMBINATIONS", use_container_width=True):
    ranges = optimizer_param_ranges()
    grid = build_parameter_grid(ranges)
    st.session_state["optimizer_preview"] = {"count": len(grid), "ranges": ranges}
    st.sidebar.info(f"{len(grid)} COMBINATIONS")

if st.sidebar.button("RUN OPTIMIZATION", use_container_width=True):
    if opt_start >= opt_end and opt_mode == "single_period":
        st.sidebar.error("OPT_START must be before OPT_END")
    else:
        with st.spinner("RUNNING OPTIMIZATION..."):
            try:
                outcome = run_optimization(
                    opt_start.strftime("%Y-%m-%d"),
                    opt_end.strftime("%Y-%m-%d"),
                    optimizer_param_ranges(),
                    strategy_engine=opt_engine,
                    watchlist=optimizer_watchlist(),
                    optimization_mode=opt_mode,
                    confirm_large_grid=opt_confirm_large,
                    initial_capital=float(bt_initial_capital),
                    allowed_risk_ratings=bt_risk_backtest,
                    use_adjusted_data=opt_adjusted,
                    benchmark_ticker=opt_benchmark,
                )
                st.session_state["optimizer_results"] = outcome["results"]
                st.sidebar.success(f"OPT RUN #{outcome['optimization_run_id']} COMPLETE")
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"OPTIMIZATION FAILED: {exc}")

latest_run = session.query(Run).order_by(Run.timestamp.desc()).first()
latest_backtest = session.query(BacktestRun).order_by(BacktestRun.timestamp.desc()).first()
trades_df = pd.DataFrame()
equity_df = pd.DataFrame()
rejected_df = pd.DataFrame()

if "sweep_rows" in st.session_state:
    st.markdown("## PARAMETER SWEEP")
    sweep_df = pd.DataFrame(st.session_state["sweep_rows"])
    st.dataframe(sweep_df, use_container_width=True, hide_index=True)
    if not sweep_df.empty:
        st.bar_chart(sweep_df.set_index("run_id")[["cagr", "sharpe", "calmar", "max_drawdown"]], use_container_width=True)

if "walk_forward_rows" in st.session_state:
    st.markdown("## WALK_FORWARD")
    wf_df = pd.DataFrame(st.session_state["walk_forward_rows"])
    st.dataframe(wf_df, use_container_width=True, hide_index=True)
    if not wf_df.empty:
        st.bar_chart(wf_df.set_index("segment")[["cagr", "sharpe", "calmar", "max_drawdown"]], use_container_width=True)

if "optimizer_preview" in st.session_state:
    st.markdown("## OPTIMIZER PREVIEW")
    st.markdown(
        "<div class='terminal-panel'>"
        f"<p class='terminal-line'>> COMBINATIONS: {st.session_state['optimizer_preview']['count']}</p>"
        f"<p class='terminal-line'>> ROBUST_SCORE: {ROBUST_SCORE_FORMULA}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

latest_optimization = session.query(OptimizationRun).order_by(OptimizationRun.timestamp.desc()).first()
optimizer_rows = st.session_state.get("optimizer_results")
if optimizer_rows is None and latest_optimization:
    db_rows = (
        session.query(OptimizationResult)
        .filter(OptimizationResult.optimization_run_id == latest_optimization.id)
        .order_by(OptimizationResult.rank_robust_score.asc())
        .all()
    )
    optimizer_rows = [
        {
            "rank_robust_score": row.rank_robust_score,
            "rank_total_return": row.rank_total_return,
            "rank_cagr": row.rank_cagr,
            "rank_sharpe": row.rank_sharpe,
            "rank_calmar": row.rank_calmar,
            "strategy_engine": latest_optimization.strategy_engine,
            "parameters": row.parameters_json,
            "total_return": row.total_return,
            "cagr": row.cagr,
            "sharpe": row.sharpe,
            "calmar": row.calmar,
            "max_drawdown": row.max_drawdown,
            "alpha_vs_spy": row.alpha_vs_spy,
            "robust_score": row.robust_score,
            "overfit_risk": row.overfit_risk,
            "run_id": row.backtest_run_id,
            "total_trades": row.total_trades,
            "beats_spy": row.total_return > row.benchmark_return,
        }
        for row in db_rows
    ]

if optimizer_rows:
    st.markdown("## OPTIMIZER")
    opt_df = pd.DataFrame(optimizer_rows)
    if "parameters" in opt_df:
        opt_df["parameters"] = opt_df["parameters"].astype(str)
    min_trades_filter = st.number_input("OPT_FILTER_MIN_TRADES", min_value=0, value=0, step=1)
    max_drawdown_filter = st.number_input("OPT_FILTER_MAX_DRAWDOWN", min_value=-100.0, max_value=0.0, value=-100.0, step=1.0)
    beats_spy_filter = st.checkbox("OPT_FILTER_BEATS_SPY_ONLY", value=False)
    no_overfit_filter = st.checkbox("OPT_FILTER_OVERFIT_FALSE_ONLY", value=False)
    filtered = opt_df.copy()
    if "total_trades" in filtered:
        filtered = filtered[filtered["total_trades"].fillna(0) >= min_trades_filter]
    if "max_drawdown" in filtered:
        filtered = filtered[filtered["max_drawdown"].fillna(0) >= max_drawdown_filter]
    if beats_spy_filter and "beats_spy" in filtered:
        filtered = filtered[filtered["beats_spy"] == True]
    if no_overfit_filter and "overfit_risk" in filtered:
        filtered = filtered[filtered["overfit_risk"] == False]

    def overfit_style(row):
        if row.get("overfit_risk") is True:
            return ["background-color: rgba(255, 77, 109, 0.22)"] * len(row)
        return [""] * len(row)

    display_columns = [
        column for column in [
            "rank_robust_score", "strategy_engine", "parameters", "total_return", "cagr",
            "sharpe", "calmar", "max_drawdown", "alpha_vs_spy", "robust_score",
            "overfit_risk", "run_id",
        ] if column in filtered.columns
    ]
    st.dataframe(filtered[display_columns].style.apply(overfit_style, axis=1), use_container_width=True, hide_index=True)
    st.download_button(
        "EXPORT RESULTS CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="optimization_results.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if not filtered.empty:
        cols = st.columns(6)
        best_specs = [
            ("BEST_RETURN", "total_return"),
            ("BEST_CAGR", "cagr"),
            ("BEST_SHARPE", "sharpe"),
            ("BEST_CALMAR", "calmar"),
            ("BEST_ROBUST", "robust_score"),
            ("BEST_TEST", "test_cagr" if "test_cagr" in filtered.columns else "cagr"),
        ]
        for col, (label, metric) in zip(cols, best_specs):
            row = filtered.sort_values(metric, ascending=False).iloc[0]
            col.metric(label, f"{row.get(metric, 0.0):.2f}", f"RUN {row.get('run_id', 'N/A')}")

        st.markdown("## OPTIMIZER CHARTS")
        if {"cagr", "max_drawdown"}.issubset(filtered.columns):
            st.scatter_chart(filtered, x="max_drawdown", y="cagr", color="robust_score", use_container_width=True)
        if {"sharpe", "calmar"}.issubset(filtered.columns):
            st.scatter_chart(filtered, x="sharpe", y="calmar", color="robust_score", use_container_width=True)
        if {"robust_score", "run_id"}.issubset(filtered.columns):
            top_robust = filtered.sort_values("robust_score", ascending=False).head(10)
            st.bar_chart(top_robust.set_index("run_id")[["robust_score"]], use_container_width=True)
        if "parameters" in filtered.columns and {"cagr"}.issubset(filtered.columns):
            expanded = filtered.copy()
            raw_params = opt_df.loc[expanded.index, "parameters"] if "parameters" in opt_df else None
            if raw_params is not None:
                try:
                    param_df = pd.DataFrame([row.get("parameters_json", row.get("parameters", {})) if isinstance(row, dict) else {} for row in optimizer_rows])
                    if {"min_score", "max_holding_days"}.issubset(param_df.columns):
                        heat = pd.concat([param_df, opt_df[["cagr"]]], axis=1)
                        heat = heat.pivot_table(index="min_score", columns="max_holding_days", values="cagr", aggfunc="mean")
                        st.dataframe(heat, use_container_width=True)
                except Exception:
                    pass

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
        f"<p class='terminal-line'>> ENGINE: {latest_backtest.strategy_engine}</p>"
        f"<p class='terminal-line'>> MIN_SCORE: {format_num(latest_backtest.min_score)}</p>"
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

    cols = st.columns(3)
    cols[0].metric("SPY_RETURN", format_pct(latest_backtest.spy_return))
    cols[1].metric("QQQ_RETURN", format_pct(latest_backtest.qqq_return))
    cols[2].metric("SPY_SMA200_RETURN", format_pct(latest_backtest.spy_sma200_return))

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
                    "POSITIONS_VALUE": row.positions_value,
                    "OPEN_POSITIONS": row.open_positions,
                    "DAILY_RETURN_%": row.daily_return,
                    "BENCHMARK_DAILY_RETURN_%": row.benchmark_daily_return,
                    "SPY_DAILY_RETURN_%": row.spy_daily_return,
                    "QQQ_DAILY_RETURN_%": row.qqq_daily_return,
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
                    "ENTRY_VALUE": t.entry_value,
                    "EXIT_VALUE": t.exit_value,
                    "RISK_AMOUNT": t.risk_amount,
                    "RISK_%": t.risk_pct,
                    "COST": t.cost_amount,
                }
                for t in trades
            ]
        )
        st.dataframe(trades_df, use_container_width=True, hide_index=True)

    rejected = (
        session.query(BacktestRejectedTrade)
        .filter(BacktestRejectedTrade.run_id == latest_backtest.id)
        .order_by(BacktestRejectedTrade.signal_date.desc())
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

    if not trades_df.empty or not equity_df.empty:
        diagnostic_trades = trades_df.rename(
            columns={
                "SIG_DATE": "signal_date",
                "TICKER": "ticker",
                "REGIME": "market_regime",
                "ENTRY": "entry_date",
                "EXIT": "exit_date",
                "REASON": "exit_reason",
                "RET_%": "return_pct",
                "PNL": "pnl",
                "HOLD": "holding_days",
                "SCORE": "final_score",
            }
        )
        diagnostic_equity = equity_df.rename(
            columns={
                "DATE": "date",
                "EQUITY": "equity",
                "DRAWDOWN_%": "drawdown_pct",
                "CASH": "cash",
                "POSITIONS_VALUE": "positions_value",
                "OPEN_POSITIONS": "open_positions",
                "DAILY_RETURN_%": "daily_return",
                "BENCHMARK_DAILY_RETURN_%": "benchmark_daily_return",
                "SPY_DAILY_RETURN_%": "spy_daily_return",
                "QQQ_DAILY_RETURN_%": "qqq_daily_return",
            }
        )
        if "positions_value" not in diagnostic_equity and equity_rows:
            diagnostic_equity["positions_value"] = [row.positions_value for row in equity_rows]
        diagnostic_rejected = rejected_df.rename(
            columns={
                "SIG_DATE": "signal_date",
                "TICKER": "ticker",
                "ACTION": "action",
                "REASON": "reason",
                "SCORE": "final_score",
                "ENTRY_VALUE": "entry_value",
                "EXIT_VALUE": "exit_value",
                "RISK_AMOUNT": "risk_amount",
                "RISK_%": "risk_pct",
                "COST": "cost_amount",
            }
        )
        diagnostics = build_diagnostics(diagnostic_trades, diagnostic_equity, diagnostic_rejected)

        st.markdown("## STRATEGY DIAGNOSTICS")
        rec = diagnostics["recommendations"]
        st.markdown(
            "<div class='terminal-panel'>"
            f"<p class='terminal-line'>> TICKERS_TO_REMOVE: {', '.join(rec['tickers_to_remove']) or 'NONE'}</p>"
            f"<p class='terminal-line'>> REGIMES_TO_AVOID: {', '.join(rec['regimes_to_avoid']) or 'NONE'}</p>"
            f"<p class='terminal-line'>> SCORE_MIN_RECOMMENDED: {format_num(rec['score_minimum_recommended']) if rec['score_minimum_recommended'] is not None else 'N/A'}</p>"
            f"<p class='terminal-line'>> MAX_HOLDING_IDEAL: {rec['max_holding_ideal'] if rec['max_holding_ideal'] is not None else 'N/A'}</p>"
            f"<p class='terminal-line'>> FILTERS_IMPROVING_SHARPE_CAGR: {' | '.join(rec['filters']) or 'NONE FOUND'}</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        exposure = diagnostics["exposure"]
        efficiency = diagnostics["efficiency"]
        cols = st.columns(5)
        cols[0].metric("AVG_EXPOSURE", format_pct(exposure["average_portfolio_exposure"]))
        cols[1].metric("MAX_EXPOSURE", format_pct(exposure["max_exposure"]))
        cols[2].metric("AVG_CASH", format_pct(exposure["average_cash_pct"]))
        cols[3].metric("TIME_IN_MARKET", format_pct(exposure["time_in_market"]))
        cols[4].metric("AVG_OPEN_POS", format_num(exposure["average_open_positions"]))

        cols = st.columns(5)
        cols[0].metric("TURNOVER", format_num(efficiency["turnover"]))
        cols[1].metric("COST_DRAG", format_pct(efficiency["cost_drag"]))
        cols[2].metric("BETA_VS_SPY", format_num(efficiency["beta_vs_spy"]))
        cols[3].metric("CORR_VS_SPY", format_num(efficiency["correlation_vs_spy"]))
        cols[4].metric("INFO_RATIO", format_num(efficiency["information_ratio"]))

        st.markdown("## PERFORMANCE BY TICKER")
        by_ticker = diagnostics["by_ticker"]
        if not by_ticker.empty:
            st.dataframe(by_ticker, use_container_width=True, hide_index=True)
            st.bar_chart(by_ticker.set_index("ticker")[["total_pnl", "expectancy"]], use_container_width=True)

        st.markdown("## PERFORMANCE BY MARKET_REGIME")
        by_regime = diagnostics["by_regime"]
        st.dataframe(by_regime, use_container_width=True, hide_index=True)
        if not by_regime.empty:
            st.bar_chart(by_regime.set_index("market_regime")[["total_pnl", "expectancy"]], use_container_width=True)

        st.markdown("## PERFORMANCE BY YEAR")
        by_year = diagnostics["by_year"]
        st.dataframe(by_year, use_container_width=True, hide_index=True)
        if not by_year.empty:
            st.bar_chart(by_year.set_index("year")[["total_return", "max_drawdown"]], use_container_width=True)

        st.markdown("## PERFORMANCE BY EXIT_REASON")
        by_exit = diagnostics["by_exit_reason"]
        st.dataframe(by_exit, use_container_width=True, hide_index=True)
        if not by_exit.empty:
            st.bar_chart(by_exit.set_index("reason")[["total_pnl", "expectancy", "rejected"]], use_container_width=True)

        st.markdown("## REJECTED TRADES BY REASON")
        by_rejection = diagnostics["by_rejection_reason"]
        st.dataframe(by_rejection, use_container_width=True, hide_index=True)
        if not by_rejection.empty:
            st.bar_chart(by_rejection.set_index("reason")[["rejected"]], use_container_width=True)

        st.markdown("## PERFORMANCE BY SCORE BUCKET")
        by_score = diagnostics["by_score_bucket"]
        st.dataframe(by_score, use_container_width=True, hide_index=True)
        if not by_score.empty:
            st.bar_chart(by_score.set_index("score_bucket")[["total_pnl", "expectancy"]], use_container_width=True)
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
