from dataclasses import dataclass
import math

import pandas as pd
import yfinance as yf

import config
from db.database import BacktestRun, BacktestTrade, get_session, init_db
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
class BacktestResult:
    run_id: int
    metrics: dict
    trades: list[dict]
    failed_tickers: dict


def fetch_historical_data(ticker, start, end, warmup_days=370, exit_buffer_days=45):
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days)).strftime("%Y-%m-%d")
    fetch_end = (pd.Timestamp(end) + pd.Timedelta(days=exit_buffer_days)).strftime("%Y-%m-%d")

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


def simulate_trade(signal, ticker_df, signal_date, max_holding_days=30, position_size=100.0):
    future = ticker_df.loc[ticker_df.index > signal_date]
    if future.empty:
        return None

    entry_bar = future.iloc[0]
    if pd.isna(entry_bar.get("Open")):
        return None

    entry_date = future.index[0]
    entry_price = float(entry_bar["Open"])
    invalidation = float(signal["invalidation"])
    target_1 = float(signal["target_1"])

    holding_bars = future.iloc[:max_holding_days]
    for current_date, row in holding_bars.iterrows():
        if pd.isna(row.get("High")) or pd.isna(row.get("Low")) or pd.isna(row.get("Close")):
            continue

        # Conservative intraday ambiguity handling: if both levels are touched,
        # count stop/invalidation first because OHLC does not reveal sequence.
        if float(row["Low"]) <= invalidation:
            exit_price = invalidation
            exit_reason = "STOP"
        elif float(row["High"]) >= target_1:
            exit_price = target_1
            exit_reason = "TARGET_1"
        elif len(holding_bars.loc[:current_date]) >= max_holding_days:
            exit_price = float(row["Close"])
            exit_reason = "MAX_HOLDING_DAYS"
        else:
            continue

        return_pct = (exit_price / entry_price - 1) * 100
        pnl = position_size * (return_pct / 100)
        return {
            "signal_id": signal["signal_id"],
            "signal_date": signal["date"],
            "ticker": signal["ticker"],
            "market_regime": signal["market_regime"],
            "entry_date": entry_date.strftime("%Y-%m-%d"),
            "entry_price": entry_price,
            "exit_date": current_date.strftime("%Y-%m-%d"),
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "return_pct": return_pct,
            "pnl": pnl,
            "technical_score": signal["technical_score"],
            "regime_score": signal["regime_score"],
            "final_score": signal["final_score"],
        }

    return None


def calculate_metrics(trades, spy_df, start, end):
    returns = [trade["return_pct"] for trade in trades]
    wins = [ret for ret in returns if ret > 0]
    losses = [ret for ret in returns if ret <= 0]

    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    total = len(returns)
    win_rate = (len(wins) / total * 100) if total else 0.0
    average_win = sum(wins) / len(wins) if wins else 0.0
    average_loss = sum(losses) / len(losses) if losses else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss else (math.inf if gross_win else 0.0)
    expectancy = sum(returns) / total if total else 0.0
    average_return = expectancy
    max_drawdown = calculate_approx_max_drawdown(returns)
    spy_return = calculate_spy_return(spy_df, start, end)

    return {
        "total_trades": total,
        "win_rate": win_rate,
        "average_win": average_win,
        "average_loss": average_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "average_return": average_return,
        "max_drawdown": max_drawdown,
        "spy_return": spy_return,
    }


def calculate_approx_max_drawdown(returns):
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0

    for ret in returns:
        equity *= 1 + (ret / 100)
        peak = max(peak, equity)
        drawdown = (equity / peak - 1) * 100
        max_drawdown = min(max_drawdown, drawdown)

    return max_drawdown


def calculate_spy_return(spy_df, start, end):
    if spy_df is None or spy_df.empty:
        return 0.0

    period = spy_df.loc[(spy_df.index >= pd.Timestamp(start)) & (spy_df.index <= pd.Timestamp(end))]
    closes = period["Close"].dropna()
    if len(closes) < 2:
        return 0.0

    return (float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100


def run_backtest(start, end, watchlist=None, max_holding_days=30):
    init_db()
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

    all_signal_dates = sorted(
        {
            date
            for df in historical_data.values()
            for date in df.loc[(df.index >= start_ts) & (df.index <= end_ts)].index
        }
    )

    trades = []
    for as_of_date in all_signal_dates:
        scoped_market = {
            ticker: df.loc[:as_of_date]
            for ticker, df in historical_data.items()
            if not df.loc[:as_of_date].empty and has_complete_signal_data(df.loc[:as_of_date])
        }
        if not scoped_market:
            continue

        regime = classify_market_regime(scoped_market)
        for ticker, df in historical_data.items():
            scoped_df = df.loc[:as_of_date]
            if not has_complete_signal_data(scoped_df):
                continue

            signal = generate_signal(ticker, scoped_df, regime, as_of_date=as_of_date)
            if signal is None or signal["action"] != "BUY":
                continue

            signal["market_regime"] = regime
            trade = simulate_trade(signal, df, as_of_date, max_holding_days=max_holding_days)
            if trade:
                trades.append(trade)

    metrics = calculate_metrics(trades, historical_data.get("SPY"), start_ts, end_ts)
    run_id = save_backtest_results(start_ts, end_ts, watchlist, metrics, trades)

    return BacktestResult(
        run_id=run_id,
        metrics=metrics,
        trades=trades,
        failed_tickers=failed_tickers,
    )


def save_backtest_results(start, end, watchlist, metrics, trades):
    session = get_session()
    try:
        db_run = BacktestRun(
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            watchlist=",".join(watchlist),
            total_trades=metrics["total_trades"],
            win_rate=metrics["win_rate"],
            average_win=metrics["average_win"],
            average_loss=metrics["average_loss"],
            profit_factor=None if math.isinf(metrics["profit_factor"]) else metrics["profit_factor"],
            expectancy=metrics["expectancy"],
            average_return=metrics["average_return"],
            max_drawdown=metrics["max_drawdown"],
            spy_return=metrics["spy_return"],
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
                )
            )

        session.commit()
        return db_run.id
    finally:
        session.close()
