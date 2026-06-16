from dataclasses import dataclass
import math

import pandas as pd
import yfinance as yf

import config
from db.database import (
    BacktestEquityCurve,
    BacktestRejectedTrade,
    BacktestRun,
    BacktestTrade,
    get_session,
    init_db,
)
from strategy.indicators import calculate_indicators
from strategy.regime import classify_market_regime
from strategy.signal_engine import generate_signal


REQUIRED_SIGNAL_COLUMNS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "SMA_20",
    "SMA_50",
    "SMA_200",
    "RSI_14",
    "ATR_14",
    "Volume_Avg_20",
    "Perf_3M",
    "Vol_20D",
]


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    max_holding_days: int = 30
    max_positions_total: int = 5
    max_position_pct: float = 0.20
    spread_slippage_pct: float = 0.001
    currency_conversion_pct: float = 0.0


@dataclass
class BacktestResult:
    run_id: int
    metrics: dict
    trades: list[dict]
    rejected_trades: list[dict]
    equity_curve: list[dict]
    failed_tickers: dict


def fetch_historical_data(ticker, start, end, warmup_days=370):
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days)).strftime("%Y-%m-%d")
    fetch_end = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    data = yf.download(ticker, start=fetch_start, end=fetch_end, progress=False, auto_adjust=False)
    if data is None or data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data.index = pd.to_datetime(data.index).tz_localize(None)
    return calculate_indicators(data)


def has_complete_signal_data(df):
    if df is None or df.empty:
        return False

    last_row = df.iloc[-1]
    for column in REQUIRED_SIGNAL_COLUMNS:
        if column not in last_row.index or pd.isna(last_row[column]):
            return False
    return True


def get_next_trading_date(df, as_of_date, end_date):
    future = df.loc[(df.index > as_of_date) & (df.index <= end_date)]
    if future.empty:
        return None
    return future.index[0]


def get_price(df, date_value, column):
    if df is None or date_value not in df.index or column not in df.columns:
        return None
    value = df.loc[date_value, column]
    if pd.isna(value):
        return None
    return float(value)


def execution_cost_pct(config_obj):
    return config_obj.spread_slippage_pct + config_obj.currency_conversion_pct


def buy_price(raw_open, config_obj):
    return raw_open * (1 + execution_cost_pct(config_obj))


def sell_price(raw_price, config_obj):
    return raw_price * (1 - execution_cost_pct(config_obj))


def make_rejection(signal, reason):
    return {
        "signal_id": signal.get("signal_id"),
        "signal_date": signal.get("date"),
        "ticker": signal.get("ticker"),
        "action": signal.get("action"),
        "reason": reason,
        "final_score": signal.get("final_score"),
    }


def calculate_trade_stats(trades):
    returns = [trade["return_pct"] for trade in trades]
    wins = [ret for ret in returns if ret > 0]
    losses = [ret for ret in returns if ret <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    total = len(returns)

    return {
        "total_trades": total,
        "win_rate": (len(wins) / total * 100) if total else 0.0,
        "average_win": sum(wins) / len(wins) if wins else 0.0,
        "average_loss": sum(losses) / len(losses) if losses else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss else (math.inf if gross_win else 0.0),
        "expectancy": sum(returns) / total if total else 0.0,
        "average_return": sum(returns) / total if total else 0.0,
        "avg_holding_days": (
            sum(trade["holding_days"] for trade in trades) / total
            if total
            else 0.0
        ),
    }


def calculate_equity_drawdowns(equity_values):
    peak = None
    rows = []
    max_drawdown_pct = 0.0
    max_drawdown_value = 0.0

    for equity in equity_values:
        peak = equity if peak is None else max(peak, equity)
        drawdown_value = equity - peak
        drawdown_pct = (drawdown_value / peak * 100) if peak and peak > 0 else 0.0
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
        max_drawdown_value = min(max_drawdown_value, drawdown_value)
        rows.append((drawdown_value, drawdown_pct))

    return rows, max_drawdown_value, max_drawdown_pct


def calculate_risk_metrics(equity_curve, initial_capital, start, end):
    if not equity_curve:
        return {
            "final_equity": initial_capital,
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "calmar": 0.0,
            "max_drawdown_value": 0.0,
            "max_drawdown": 0.0,
        }

    final_equity = equity_curve[-1]["equity"]
    total_return = (final_equity / initial_capital - 1) * 100 if initial_capital else 0.0
    years = max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 1 / 365.25)
    cagr = ((final_equity / initial_capital) ** (1 / years) - 1) * 100 if final_equity > 0 else -100.0

    daily_returns = pd.Series([row["daily_return"] / 100 for row in equity_curve[1:]])
    sharpe = 0.0
    sortino = 0.0
    if not daily_returns.empty:
        std = daily_returns.std(ddof=0)
        downside = daily_returns[daily_returns < 0].std(ddof=0)
        avg = daily_returns.mean()
        sharpe = (avg / std) * math.sqrt(252) if std and not math.isnan(std) else 0.0
        sortino = (avg / downside) * math.sqrt(252) if downside and not math.isnan(downside) else 0.0

    max_drawdown_value = min(row["drawdown_value"] for row in equity_curve)
    max_drawdown = min(row["drawdown_pct"] for row in equity_curve)
    calmar = (cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    return {
        "final_equity": final_equity,
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown_value": max_drawdown_value,
        "max_drawdown": max_drawdown,
    }


def calculate_spy_return(spy_df, start, end):
    if spy_df is None or spy_df.empty:
        return 0.0

    period = spy_df.loc[(spy_df.index >= pd.Timestamp(start)) & (spy_df.index <= pd.Timestamp(end))]
    closes = period["Close"].dropna()
    if len(closes) < 2:
        return 0.0

    return (float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100


def mark_positions_value(positions, historical_data, current_date, config_obj):
    total = 0.0
    for position in positions.values():
        close_price = get_price(historical_data[position["ticker"]], current_date, "Close")
        if close_price is None:
            close_price = position["last_price"]
        position["last_price"] = close_price
        total += position["shares"] * sell_price(close_price, config_obj)
    return total


def close_position(position, raw_exit_price, exit_date, exit_reason, config_obj):
    exec_exit_price = sell_price(raw_exit_price, config_obj)
    exit_value = position["shares"] * exec_exit_price
    pnl = exit_value - position["entry_value"]
    return_pct = (exit_value / position["entry_value"] - 1) * 100 if position["entry_value"] else 0.0
    holding_days = len(position["df"].loc[(position["df"].index >= position["entry_date"]) & (position["df"].index <= exit_date)])

    return {
        "signal_id": position["signal_id"],
        "signal_date": position["signal_date"],
        "ticker": position["ticker"],
        "market_regime": position["market_regime"],
        "entry_date": position["entry_date"].strftime("%Y-%m-%d"),
        "entry_price": position["entry_price"],
        "exit_date": exit_date.strftime("%Y-%m-%d"),
        "exit_price": exec_exit_price,
        "exit_reason": exit_reason,
        "return_pct": return_pct,
        "pnl": pnl,
        "technical_score": position["technical_score"],
        "regime_score": position["regime_score"],
        "final_score": position["final_score"],
        "holding_days": holding_days,
        "position_size": position["shares"],
        "entry_value": position["entry_value"],
        "exit_value": exit_value,
    }


def process_entries_for_date(pending_entries, positions, cash, equity, historical_data, current_date, config_obj):
    remaining = []
    trades_rejected = []
    max_position_value = max(equity * config_obj.max_position_pct, 0.0)

    for entry in pending_entries:
        if entry["entry_date"] != current_date:
            remaining.append(entry)
            continue

        signal = entry["signal"]
        ticker = signal["ticker"]
        open_price = get_price(historical_data[ticker], current_date, "Open")
        if open_price is None:
            trades_rejected.append(make_rejection(signal, "MISSING_NEXT_OPEN"))
            continue
        if ticker in positions:
            trades_rejected.append(make_rejection(signal, "TICKER_ALREADY_OPEN"))
            continue
        if len(positions) >= config_obj.max_positions_total:
            trades_rejected.append(make_rejection(signal, "MAX_POSITIONS_TOTAL"))
            continue
        if cash <= 0 or max_position_value <= 0:
            trades_rejected.append(make_rejection(signal, "NO_CASH_AVAILABLE"))
            continue

        allocation = min(cash, max_position_value)
        exec_entry_price = buy_price(open_price, config_obj)
        shares = allocation / exec_entry_price
        if shares <= 0:
            trades_rejected.append(make_rejection(signal, "POSITION_SIZE_ZERO"))
            continue

        cash -= allocation
        positions[ticker] = {
            "signal_id": signal["signal_id"],
            "signal_date": signal["date"],
            "ticker": ticker,
            "market_regime": signal["market_regime"],
            "entry_date": current_date,
            "entry_price": exec_entry_price,
            "entry_value": allocation,
            "shares": shares,
            "invalidation": float(signal["invalidation"]),
            "target_1": float(signal["target_1"]),
            "technical_score": signal["technical_score"],
            "regime_score": signal["regime_score"],
            "final_score": signal["final_score"],
            "last_price": open_price,
            "df": historical_data[ticker],
        }

    return remaining, positions, cash, trades_rejected


def process_exits_for_date(positions, historical_data, current_date, config_obj, max_holding_days, force_close=False):
    closed_trades = []
    cash_delta = 0.0

    for ticker, position in list(positions.items()):
        df = historical_data[ticker]
        if current_date not in df.index:
            continue

        row = df.loc[current_date]
        if pd.isna(row.get("High")) or pd.isna(row.get("Low")) or pd.isna(row.get("Close")):
            continue

        raw_exit_price = None
        exit_reason = None
        bars_held = len(df.loc[(df.index >= position["entry_date"]) & (df.index <= current_date)])

        if force_close:
            raw_exit_price = float(row["Close"])
            exit_reason = "END_OF_BACKTEST"
        elif float(row["Low"]) <= position["invalidation"]:
            raw_exit_price = position["invalidation"]
            exit_reason = "STOP"
        elif float(row["High"]) >= position["target_1"]:
            raw_exit_price = position["target_1"]
            exit_reason = "TARGET_1"
        elif bars_held >= max_holding_days:
            raw_exit_price = float(row["Close"])
            exit_reason = "MAX_HOLDING_DAYS"

        if exit_reason:
            trade = close_position(position, raw_exit_price, current_date, exit_reason, config_obj)
            cash_delta += trade["exit_value"]
            closed_trades.append(trade)
            del positions[ticker]

    return closed_trades, positions, cash_delta


def build_equity_point(date_value, cash, positions, historical_data, previous_equity, peak_equity, config_obj):
    positions_value = mark_positions_value(positions, historical_data, date_value, config_obj)
    equity = cash + positions_value
    peak_equity = max(peak_equity, equity)
    drawdown_value = equity - peak_equity
    drawdown_pct = (drawdown_value / peak_equity * 100) if peak_equity > 0 else 0.0
    daily_return = ((equity / previous_equity) - 1) * 100 if previous_equity > 0 else 0.0

    return {
        "date": date_value.strftime("%Y-%m-%d"),
        "cash": cash,
        "positions_value": positions_value,
        "equity": equity,
        "drawdown_value": drawdown_value,
        "drawdown_pct": drawdown_pct,
        "open_positions": len(positions),
        "daily_return": daily_return,
    }, equity, peak_equity


def simulate_portfolio(historical_data, start, end, config_obj):
    cash = config_obj.initial_capital
    positions = {}
    pending_entries = []
    trades = []
    rejected_trades = []
    equity_curve = []
    generated_signals = 0
    max_concurrent_positions = 0
    bankrupt = False
    previous_equity = config_obj.initial_capital
    peak_equity = config_obj.initial_capital

    trading_dates = sorted(
        {
            date_value
            for df in historical_data.values()
            for date_value in df.loc[(df.index >= start) & (df.index <= end)].index
        }
    )

    for current_date in trading_dates:
        pending_entries, positions, cash, entry_rejections = process_entries_for_date(
            pending_entries,
            positions,
            cash,
            previous_equity,
            historical_data,
            current_date,
            config_obj,
        )
        rejected_trades.extend(entry_rejections)

        closed_today, positions, cash_delta = process_exits_for_date(
            positions,
            historical_data,
            current_date,
            config_obj,
            config_obj.max_holding_days,
        )
        trades.extend(closed_today)
        cash += cash_delta

        equity_point, previous_equity, peak_equity = build_equity_point(
            current_date,
            cash,
            positions,
            historical_data,
            previous_equity,
            peak_equity,
            config_obj,
        )
        equity_curve.append(equity_point)
        max_concurrent_positions = max(max_concurrent_positions, len(positions))

        if equity_point["equity"] <= 0:
            bankrupt = True
            break

        scoped_market = {
            ticker: df.loc[:current_date]
            for ticker, df in historical_data.items()
            if not df.loc[:current_date].empty and has_complete_signal_data(df.loc[:current_date])
        }
        if not scoped_market:
            continue

        regime = classify_market_regime(scoped_market)
        pending_tickers = {entry["signal"]["ticker"] for entry in pending_entries}
        for ticker, df in historical_data.items():
            scoped_df = df.loc[:current_date]
            if not has_complete_signal_data(scoped_df):
                continue

            signal = generate_signal(ticker, scoped_df, regime, as_of_date=current_date)
            if signal is None or signal["action"] != "BUY":
                continue

            generated_signals += 1
            signal["market_regime"] = regime

            if ticker in positions:
                rejected_trades.append(make_rejection(signal, "TICKER_ALREADY_OPEN"))
                continue
            if ticker in pending_tickers:
                rejected_trades.append(make_rejection(signal, "ENTRY_ALREADY_PENDING"))
                continue
            if len(positions) + len(pending_entries) >= config_obj.max_positions_total:
                rejected_trades.append(make_rejection(signal, "MAX_POSITIONS_TOTAL"))
                continue

            entry_date = get_next_trading_date(df, current_date, end)
            if entry_date is None:
                rejected_trades.append(make_rejection(signal, "NO_NEXT_OPEN_WITHIN_BACKTEST_WINDOW"))
                continue

            pending_entries.append({"entry_date": entry_date, "signal": signal})
            pending_tickers.add(ticker)

    if trading_dates and positions and not bankrupt:
        final_date = trading_dates[-1]
        forced_trades, positions, cash_delta = process_exits_for_date(
            positions,
            historical_data,
            final_date,
            config_obj,
            config_obj.max_holding_days,
            force_close=True,
        )
        trades.extend(forced_trades)
        cash += cash_delta
        equity_point, previous_equity, peak_equity = build_equity_point(
            final_date,
            cash,
            positions,
            historical_data,
            previous_equity,
            peak_equity,
            config_obj,
        )
        equity_curve[-1] = equity_point

    return {
        "trades": trades,
        "rejected_trades": rejected_trades,
        "equity_curve": equity_curve,
        "generated_signals": generated_signals,
        "max_concurrent_positions": max_concurrent_positions,
        "bankrupt": bankrupt,
    }


def calculate_metrics(trades, equity_curve, spy_df, start, end, initial_capital, generated_signals=0, rejected_trades=None):
    rejected_trades = rejected_trades or []
    trade_stats = calculate_trade_stats(trades)
    risk_stats = calculate_risk_metrics(equity_curve, initial_capital, start, end)
    spy_return = calculate_spy_return(spy_df, start, end)

    return {
        **trade_stats,
        **risk_stats,
        "generated_signals": generated_signals,
        "rejected_trades": len(rejected_trades),
        "spy_return": spy_return,
        "benchmark_return": spy_return,
        "alpha_vs_spy": risk_stats["total_return"] - spy_return,
        "bankrupt": bool(equity_curve and equity_curve[-1]["equity"] <= 0),
    }


def run_backtest(
    start,
    end,
    watchlist=None,
    max_holding_days=30,
    initial_capital=10000.0,
    max_positions_total=5,
    max_position_pct=0.20,
    spread_slippage_pct=0.001,
    currency_conversion_pct=0.0,
):
    init_db()
    config_obj = BacktestConfig(
        initial_capital=float(initial_capital),
        max_holding_days=int(max_holding_days),
        max_positions_total=int(max_positions_total),
        max_position_pct=float(max_position_pct),
        spread_slippage_pct=float(spread_slippage_pct),
        currency_conversion_pct=float(currency_conversion_pct),
    )
    watchlist = list(watchlist or config.DEFAULT_WATCHLIST)
    if "SPY" not in watchlist:
        watchlist.append("SPY")
    if "QQQ" not in watchlist:
        watchlist.append("QQQ")

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    historical_data = {}
    failed_tickers = {}

    for ticker in watchlist:
        try:
            df = fetch_historical_data(ticker, start_ts, end_ts)
            if df is None or df.empty:
                failed_tickers[ticker] = "No historical data returned"
                continue
            historical_data[ticker] = df
        except Exception as exc:
            failed_tickers[ticker] = str(exc)

    simulation = simulate_portfolio(historical_data, start_ts, end_ts, config_obj)
    metrics = calculate_metrics(
        simulation["trades"],
        simulation["equity_curve"],
        historical_data.get("SPY"),
        start_ts,
        end_ts,
        config_obj.initial_capital,
        generated_signals=simulation["generated_signals"],
        rejected_trades=simulation["rejected_trades"],
    )
    metrics["max_concurrent_positions"] = simulation["max_concurrent_positions"]
    metrics["bankrupt"] = simulation["bankrupt"] or metrics["bankrupt"]

    run_id = save_backtest_results(
        start_ts,
        end_ts,
        watchlist,
        config_obj,
        metrics,
        simulation["trades"],
        simulation["rejected_trades"],
        simulation["equity_curve"],
    )

    return BacktestResult(
        run_id=run_id,
        metrics=metrics,
        trades=simulation["trades"],
        rejected_trades=simulation["rejected_trades"],
        equity_curve=simulation["equity_curve"],
        failed_tickers=failed_tickers,
    )


def save_backtest_results(start, end, watchlist, config_obj, metrics, trades, rejected_trades, equity_curve):
    session = get_session()
    try:
        db_run = BacktestRun(
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            watchlist=",".join(watchlist),
            initial_capital=config_obj.initial_capital,
            final_equity=metrics["final_equity"],
            total_return=metrics["total_return"],
            cagr=metrics["cagr"],
            sharpe=metrics["sharpe"],
            sortino=metrics["sortino"],
            calmar=metrics["calmar"],
            total_trades=metrics["total_trades"],
            generated_signals=metrics["generated_signals"],
            rejected_trades=metrics["rejected_trades"],
            win_rate=metrics["win_rate"],
            average_win=metrics["average_win"],
            average_loss=metrics["average_loss"],
            profit_factor=None if math.isinf(metrics["profit_factor"]) else metrics["profit_factor"],
            expectancy=metrics["expectancy"],
            average_return=metrics["average_return"],
            max_drawdown=metrics["max_drawdown"],
            max_drawdown_value=metrics["max_drawdown_value"],
            spy_return=metrics["spy_return"],
            benchmark_return=metrics["benchmark_return"],
            alpha_vs_spy=metrics["alpha_vs_spy"],
            avg_holding_days=metrics["avg_holding_days"],
            max_concurrent_positions=metrics["max_concurrent_positions"],
            max_positions_total=config_obj.max_positions_total,
            max_position_pct=config_obj.max_position_pct,
            spread_slippage_pct=config_obj.spread_slippage_pct,
            currency_conversion_pct=config_obj.currency_conversion_pct,
            bankrupt=metrics["bankrupt"],
        )
        session.add(db_run)
        session.flush()

        for trade in trades:
            session.add(
                BacktestTrade(
                    run_id=db_run.id,
                    signal_id=trade["signal_id"],
                    signal_date=trade["signal_date"],
                    ticker=trade["ticker"],
                    market_regime=trade["market_regime"],
                    entry_date=trade["entry_date"],
                    entry_price=trade["entry_price"],
                    exit_date=trade["exit_date"],
                    exit_price=trade["exit_price"],
                    exit_reason=trade["exit_reason"],
                    return_pct=trade["return_pct"],
                    pnl=trade["pnl"],
                    technical_score=trade["technical_score"],
                    regime_score=trade["regime_score"],
                    final_score=trade["final_score"],
                    holding_days=trade["holding_days"],
                    position_size=trade["position_size"],
                    entry_value=trade["entry_value"],
                    exit_value=trade["exit_value"],
                )
            )

        for row in equity_curve:
            session.add(
                BacktestEquityCurve(
                    run_id=db_run.id,
                    date=row["date"],
                    cash=row["cash"],
                    positions_value=row["positions_value"],
                    equity=row["equity"],
                    drawdown_value=row["drawdown_value"],
                    drawdown_pct=row["drawdown_pct"],
                    open_positions=row["open_positions"],
                    daily_return=row["daily_return"],
                )
            )

        for rejected in rejected_trades:
            session.add(
                BacktestRejectedTrade(
                    run_id=db_run.id,
                    signal_id=rejected["signal_id"],
                    signal_date=rejected["signal_date"],
                    ticker=rejected["ticker"],
                    action=rejected["action"],
                    reason=rejected["reason"],
                    final_score=rejected["final_score"],
                )
            )

        session.commit()
        return db_run.id
    finally:
        session.close()
