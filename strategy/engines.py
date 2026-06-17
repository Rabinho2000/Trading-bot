import hashlib

import pandas as pd

from strategy.scoring import calculate_final_score
from strategy.signal_engine import generate_signal


ETF_ROTATION_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "XLK", "XLV", "XLF", "XLE",
    "XLU", "XLY", "XLP", "SMH", "TLT", "GLD",
]


def stable_signal_id(strategy_name, strategy_version, date_str, ticker, action):
    return hashlib.md5(f"{strategy_name}_{strategy_version}_{date_str}_{ticker}_{action}".encode()).hexdigest()[:12]


def safe_value(row, column, default=0.0):
    value = row.get(column, default)
    if pd.isna(value):
        return default
    return float(value)


def make_signal(ticker, row, regime, final_score, technical_score, reason, strategy_name, strategy_version, action="BUY"):
    date_str = row.name.strftime("%Y-%m-%d")
    curr_price = safe_value(row, "Close")
    atr = safe_value(row, "ATR_14", curr_price * 0.03)
    entry_min = curr_price * 0.99
    entry_max = curr_price * 1.01
    invalidation = curr_price - (2 * atr)
    target_1 = curr_price + (2 * atr)
    target_2 = curr_price + (4 * atr)
    vol = safe_value(row, "Vol_20D")
    risk_rating = "LOW"
    if vol > 30:
        risk_rating = "HIGH"
    elif vol > 15:
        risk_rating = "MEDIUM"

    return {
        "signal_id": stable_signal_id(strategy_name, strategy_version, date_str, ticker, action),
        "date": date_str,
        "ticker": ticker,
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "action": action,
        "entry_zone": {"min": round(entry_min, 2), "max": round(entry_max, 2)},
        "invalidation": round(invalidation, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "risk_rating": risk_rating,
        "time_horizon": "2-6 weeks",
        "technical_score": round(technical_score, 2),
        "regime_score": round(final_score / technical_score, 2) if technical_score else 0.0,
        "final_score": round(final_score, 2),
        "reason": reason,
    }


def is_rebalance_date(date_value, all_dates, frequency):
    idx = all_dates.index(date_value)
    if idx == 0:
        return True
    previous = all_dates[idx - 1]
    if frequency == "monthly":
        return date_value.month != previous.month
    return date_value.isocalendar().week != previous.isocalendar().week


def etf_rotation_score(ticker, df, spy_df):
    row = df.iloc[-1]
    spy_row = spy_df.iloc[-1] if spy_df is not None and not spy_df.empty else None
    perf_3m = safe_value(row, "Perf_3M")
    perf_6m = safe_value(row, "Perf_6M")
    perf_12m = (safe_value(row, "Close") / float(df["Close"].shift(252).iloc[-1]) - 1) * 100 if len(df) > 252 and not pd.isna(df["Close"].shift(252).iloc[-1]) else perf_6m
    vol = max(safe_value(row, "Vol_20D", 1.0), 1.0)
    vol_adj_mom = (perf_3m + perf_6m) / vol
    above_200 = 1.0 if safe_value(row, "Close") > safe_value(row, "SMA_200") else 0.0
    spy_perf_3m = safe_value(spy_row, "Perf_3M") if spy_row is not None else 0.0
    relative_strength = perf_3m - spy_perf_3m

    raw = (
        0.25 * perf_3m
        + 0.25 * perf_6m
        + 0.20 * perf_12m
        + 8.0 * vol_adj_mom
        + 10.0 * above_200
        + 0.20 * relative_strength
    )
    score = max(0.0, min(1.0, raw / 50.0))
    return score, {
        "perf_3m": perf_3m,
        "perf_6m": perf_6m,
        "perf_12m": perf_12m,
        "relative_strength": relative_strength,
    }


def relative_strength_stock_score(df, spy_df):
    row = df.iloc[-1]
    spy_row = spy_df.iloc[-1] if spy_df is not None and not spy_df.empty else None
    spy_3m = safe_value(spy_row, "Perf_3M") if spy_row is not None else 0.0
    spy_6m = safe_value(spy_row, "Perf_6M") if spy_row is not None else 0.0
    rs_3m = safe_value(row, "Perf_3M") - spy_3m
    rs_6m = safe_value(row, "Perf_6M") - spy_6m
    above_200 = 1.0 if safe_value(row, "Close") > safe_value(row, "SMA_200") else 0.0
    above_50 = 1.0 if safe_value(row, "Close") > safe_value(row, "SMA_50") else 0.0
    vol_penalty = safe_value(row, "Vol_20D") / 100.0
    dist_52w = abs(safe_value(row, "Dist_52W_High")) / 100.0
    raw = 0.35 * rs_3m + 0.30 * rs_6m + 15 * above_200 + 10 * above_50 - 20 * vol_penalty - 10 * dist_52w
    score = max(0.0, min(1.0, raw / 50.0))
    return score, {"rs_3m": rs_3m, "rs_6m": rs_6m}


def generate_engine_signals(engine_name, ticker, scoped_df, regime, as_of_date, config_obj, market_data=None, all_dates=None):
    strategy_name = config_obj.strategy_name
    strategy_version = config_obj.strategy_version

    if engine_name == "SIGNAL_ENGINE":
        signal = generate_signal(
            ticker,
            scoped_df,
            regime,
            as_of_date=as_of_date,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
        )
        return [signal] if signal else []

    row = scoped_df.iloc[-1]
    spy_df = None
    if market_data and "SPY" in market_data:
        spy_df = market_data["SPY"].loc[:as_of_date]

    if engine_name == "ETF_ROTATION_ENGINE":
        if all_dates and not is_rebalance_date(as_of_date, all_dates, config_obj.rebalance_frequency):
            return []
        if ticker not in ETF_ROTATION_UNIVERSE:
            return []
        score, details = etf_rotation_score(ticker, scoped_df, spy_df)
        final_score, _ = calculate_final_score(score, regime)
        action = "BUY" if final_score >= config_obj.min_score and safe_value(row, "Close") > safe_value(row, "SMA_200") else "SKIP"
        reason = f"ETF rotation score. RS vs SPY 3M: {details['relative_strength']:.2f}."
        return [make_signal(ticker, row, regime, final_score, score, reason, strategy_name, strategy_version, action)]

    if engine_name == "RELATIVE_STRENGTH_STOCK_ENGINE":
        score, details = relative_strength_stock_score(scoped_df, spy_df)
        final_score, _ = calculate_final_score(score, regime)
        positive_rs = details["rs_3m"] > 0 and details["rs_6m"] > 0
        trend_ok = safe_value(row, "Close") > safe_value(row, "SMA_200") and safe_value(row, "Close") > safe_value(row, "SMA_50")
        action = "BUY" if final_score >= config_obj.min_score and positive_rs and trend_ok and regime != "RISK_OFF" else "SKIP"
        reason = f"Relative strength stock score. RS 3M {details['rs_3m']:.2f}, RS 6M {details['rs_6m']:.2f}."
        return [make_signal(ticker, row, regime, final_score, score, reason, strategy_name, strategy_version, action)]

    raise ValueError(f"Unknown strategy engine: {engine_name}")
