import hashlib

import pandas as pd

import config
from strategy.scoring import calculate_final_score
from strategy.signal_engine import generate_signal


ETF_ROTATION_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA", "XLK", "XLV", "XLF", "XLE",
    "XLU", "XLY", "XLP", "XLI", "SMH", "TLT", "GLD",
]
DEFENSIVE_UNIVERSE = ["XLP", "XLU", "XLV", "GLD", "TLT", "SPY"]
MEAN_REVERSION_ETF_UNIVERSE = ["SPY", "QQQ", "IWM", "XLK", "SMH", "XLV"]
DEFAULT_PAIRS = [("QQQ", "SPY"), ("SMH", "QQQ"), ("XLK", "SPY"), ("XLY", "XLP")]
TARGET_POSITION_ENGINES = {
    "ETF_ROTATION_TOP_N_ENGINE",
    "INDEX_TREND_BASELINE_ENGINE",
    "LOW_VOL_DEFENSIVE_ENGINE",
    "PAIR_RELATIVE_RATIO_ENGINE",
}


def stable_signal_id(strategy_name, strategy_version, date_str, ticker, action):
    return hashlib.md5(f"{strategy_name}_{strategy_version}_{date_str}_{ticker}_{action}".encode()).hexdigest()[:12]


def safe_value(row, column, default=0.0):
    value = row.get(column, default)
    if pd.isna(value):
        return default
    return float(value)


def cfg(config_obj, name, default=None):
    if hasattr(config_obj, name):
        return getattr(config_obj, name)
    params = getattr(config_obj, "strategy_params", {}) or {}
    return params.get(name, default)


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


def weighted_etf_rotation_score(ticker, df, spy_df, config_obj):
    row = df.iloc[-1]
    spy_row = spy_df.iloc[-1] if spy_df is not None and not spy_df.empty else None
    perf_3m = safe_value(row, "Perf_3M")
    perf_6m = safe_value(row, "Perf_6M")
    perf_12m = (safe_value(row, "Close") / float(df["Close"].shift(252).iloc[-1]) - 1) * 100 if len(df) > 252 and not pd.isna(df["Close"].shift(252).iloc[-1]) else perf_6m
    spy_3m = safe_value(spy_row, "Perf_3M") if spy_row is not None else 0.0
    spy_6m = safe_value(spy_row, "Perf_6M") if spy_row is not None else 0.0
    rs_3m = perf_3m - spy_3m
    rs_6m = perf_6m - spy_6m
    vol = max(safe_value(row, "Vol_20D", 1.0), 1.0)
    vol_adj_mom = (perf_3m + perf_6m) / vol
    above_200 = 1.0 if safe_value(row, "Close") > safe_value(row, "SMA_200") else 0.0
    raw = (
        cfg(config_obj, "momentum_3m_weight", 0.25) * perf_3m
        + cfg(config_obj, "momentum_6m_weight", 0.25) * perf_6m
        + cfg(config_obj, "momentum_12m_weight", 0.20) * perf_12m
        + cfg(config_obj, "rs_weight", 0.20) * (rs_3m + rs_6m) / 2
        + 8.0 * vol_adj_mom
        + 10.0 * above_200
        - cfg(config_obj, "volatility_penalty_weight", 1.0) * vol
    )
    return max(0.0, min(1.0, raw / 50.0)), {
        "rs_3m": rs_3m,
        "rs_6m": rs_6m,
        "perf_3m": perf_3m,
        "perf_6m": perf_6m,
        "perf_12m": perf_12m,
        "above_200": above_200,
        "vol": vol,
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


def relative_strength_stock_score_v2(df, spy_df, config_obj):
    row = df.iloc[-1]
    spy_row = spy_df.iloc[-1] if spy_df is not None and not spy_df.empty else None
    spy_3m = safe_value(spy_row, "Perf_3M") if spy_row is not None else 0.0
    spy_6m = safe_value(spy_row, "Perf_6M") if spy_row is not None else 0.0
    spy_12m = (safe_value(spy_row, "Close") / float(spy_df["Close"].shift(252).iloc[-1]) - 1) * 100 if spy_df is not None and len(spy_df) > 252 and not pd.isna(spy_df["Close"].shift(252).iloc[-1]) else spy_6m
    perf_12m = (safe_value(row, "Close") / float(df["Close"].shift(252).iloc[-1]) - 1) * 100 if len(df) > 252 and not pd.isna(df["Close"].shift(252).iloc[-1]) else safe_value(row, "Perf_6M")
    rs_3m = safe_value(row, "Perf_3M") - spy_3m
    rs_6m = safe_value(row, "Perf_6M") - spy_6m
    rs_12m = perf_12m - spy_12m
    above_50 = 1.0 if safe_value(row, "Close") > safe_value(row, "SMA_50") else 0.0
    above_200 = 1.0 if safe_value(row, "Close") > safe_value(row, "SMA_200") else 0.0
    atr_pct = safe_value(row, "ATR_14") / safe_value(row, "Close", 1.0) * 100
    dist_52w_penalty = abs(safe_value(row, "Dist_52W_High")) / 2
    raw = (
        cfg(config_obj, "rs_3m_weight", 0.35) * rs_3m
        + cfg(config_obj, "rs_6m_weight", 0.30) * rs_6m
        + cfg(config_obj, "rs_12m_weight", 0.20) * rs_12m
        + 10 * above_50
        + 15 * above_200
        - cfg(config_obj, "volatility_penalty_weight", 1.0) * safe_value(row, "Vol_20D")
        - atr_pct
        - dist_52w_penalty
    )
    return max(0.0, min(1.0, raw / 50.0)), {"rs_3m": rs_3m, "rs_6m": rs_6m, "rs_12m": rs_12m, "atr_pct": atr_pct}


def is_liquid(row):
    volume = safe_value(row, "Volume")
    volume_avg = safe_value(row, "Volume_Avg_20", volume)
    return volume > 0 and volume_avg > 0


def generate_target_positions(engine_name, market_data, regime, as_of_date, config_obj, trading_dates):
    if not is_rebalance_date(as_of_date, trading_dates, cfg(config_obj, "rebalance_frequency", "weekly")):
        return None

    scoped = {
        ticker: df.loc[:as_of_date]
        for ticker, df in market_data.items()
        if not df.loc[:as_of_date].empty
    }
    spy_df = scoped.get("SPY")

    if engine_name == "ETF_ROTATION_TOP_N_ENGINE":
        candidates = []
        for ticker in cfg(config_obj, "universe", ETF_ROTATION_UNIVERSE) or ETF_ROTATION_UNIVERSE:
            df = scoped.get(ticker)
            if df is None or df.empty:
                continue
            score, details = weighted_etf_rotation_score(ticker, df, spy_df, config_obj)
            row = df.iloc[-1]
            if cfg(config_obj, "use_sma200_filter", True) and safe_value(row, "Close") < safe_value(row, "SMA_200"):
                continue
            final_score, _ = calculate_final_score(score, regime)
            if final_score >= cfg(config_obj, "min_score", 0.0):
                candidates.append((ticker, final_score, details))
        top_n = int(cfg(config_obj, "top_n", 3))
        winners = sorted(candidates, key=lambda item: item[1], reverse=True)[:top_n]
        weight = min(cfg(config_obj, "max_total_exposure", 1.0), 1.0) / len(winners) if winners else 0.0
        return {ticker: weight for ticker, _, _ in winners}

    if engine_name == "INDEX_TREND_BASELINE_ENGINE":
        primary = cfg(config_obj, "index_primary", "QQQ")
        secondary = cfg(config_obj, "index_secondary", "SPY")
        defensive = cfg(config_obj, "defensive_asset", "CASH")
        sma_col = f"SMA_{int(cfg(config_obj, 'sma_window', 200))}"
        for ticker in [primary, secondary]:
            df = scoped.get(ticker)
            if df is not None and not df.empty and regime != "RISK_OFF":
                row = df.iloc[-1]
                sma = safe_value(row, sma_col, safe_value(row, "SMA_200"))
                if safe_value(row, "Close") > sma:
                    return {ticker: min(cfg(config_obj, "max_total_exposure", 1.0), 1.0)}
        if defensive in {"TLT", "GLD"}:
            return {defensive: min(cfg(config_obj, "max_total_exposure", 1.0), 1.0)}
        return {}

    if engine_name == "LOW_VOL_DEFENSIVE_ENGINE":
        if regime not in {"RISK_OFF", "HIGH_VOLATILITY"}:
            return {}
        rows = []
        window = int(cfg(config_obj, "momentum_window", 63))
        for ticker in DEFENSIVE_UNIVERSE:
            df = scoped.get(ticker)
            if df is None or len(df) <= window:
                continue
            row = df.iloc[-1]
            momentum = safe_value(row, "Close") / float(df["Close"].shift(window).iloc[-1]) - 1
            vol = safe_value(row, "Vol_20D")
            if vol <= cfg(config_obj, "max_volatility", 35.0) and momentum > 0:
                rows.append((ticker, momentum - vol / 100))
        winners = sorted(rows, key=lambda item: item[1], reverse=True)[: int(cfg(config_obj, "top_n", 2))]
        weight = min(cfg(config_obj, "max_total_exposure", 1.0), 1.0) / len(winners) if winners else 0.0
        return {ticker: weight for ticker, _ in winners}

    if engine_name == "PAIR_RELATIVE_RATIO_ENGINE":
        picks = []
        ratio_sma_window = int(cfg(config_obj, "ratio_sma_window", 50))
        ratio_momentum_window = int(cfg(config_obj, "ratio_momentum_window", 20))
        for first, second in cfg(config_obj, "pairs", DEFAULT_PAIRS) or DEFAULT_PAIRS:
            first_df = scoped.get(first)
            second_df = scoped.get(second)
            if first_df is None or second_df is None:
                continue
            common = first_df[["Close"]].join(second_df[["Close"]], lsuffix="_first", rsuffix="_second", how="inner")
            if len(common) <= max(ratio_sma_window, ratio_momentum_window):
                continue
            ratio = common["Close_first"] / common["Close_second"]
            if ratio.iloc[-1] > ratio.rolling(ratio_sma_window).mean().iloc[-1] and ratio.iloc[-1] > ratio.shift(ratio_momentum_window).iloc[-1]:
                picks.append(first)
            else:
                picks.append(second)
        winners = list(dict.fromkeys(picks))
        weight = min(cfg(config_obj, "max_total_exposure", 1.0), 1.0) / len(winners) if winners else 0.0
        return {ticker: weight for ticker in winners}

    return None


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

    if engine_name == "RELATIVE_STRENGTH_STOCK_ENGINE_V2":
        score, details = relative_strength_stock_score_v2(scoped_df, spy_df, config_obj)
        final_score, _ = calculate_final_score(score, regime)
        row = scoped_df.iloc[-1]
        positive_rs = details["rs_3m"] > 0 and details["rs_6m"] > 0
        trend_ok = safe_value(row, "Close") > safe_value(row, "SMA_50") and safe_value(row, "Close") > safe_value(row, "SMA_200")
        atr_ok = details["atr_pct"] <= cfg(config_obj, "max_atr_pct", 12.0)
        action = "BUY" if final_score >= config_obj.min_score and positive_rs and trend_ok and atr_ok and regime != "RISK_OFF" else "SKIP"
        reason = f"RS stock v2. RS 3M {details['rs_3m']:.2f}, RS 6M {details['rs_6m']:.2f}, ATR% {details['atr_pct']:.2f}."
        return [make_signal(ticker, row, regime, final_score, score, reason, strategy_name, strategy_version, action)]

    if engine_name == "BREAKOUT_52W_ENGINE":
        row = scoped_df.iloc[-1]
        spy_perf = safe_value(spy_df.iloc[-1], "Perf_3M") if spy_df is not None and not spy_df.empty else 0.0
        rs_3m = safe_value(row, "Perf_3M") - spy_perf
        high_52w = safe_value(row, "High_52W", safe_value(row, "Close"))
        vol_ok = (not cfg(config_obj, "use_volume_filter", True)) or is_liquid(row)
        score = max(0.0, min(1.0, (safe_value(row, "Perf_3M") + rs_3m + 20) / 60))
        final_score, _ = calculate_final_score(score, regime)
        action = "BUY" if (
            safe_value(row, "Close") >= high_52w * cfg(config_obj, "breakout_threshold", 0.97)
            and rs_3m >= cfg(config_obj, "min_rs_3m", 0.0)
            and final_score >= config_obj.min_score
            and safe_value(row, "Close") > safe_value(row, "SMA_200")
            and safe_value(row, "Vol_20D") <= cfg(config_obj, "max_volatility", 60.0)
            and vol_ok
            and regime != "RISK_OFF"
        ) else "SKIP"
        return [make_signal(ticker, row, regime, final_score, score, f"52W breakout candidate. RS 3M {rs_3m:.2f}.", strategy_name, strategy_version, action)]

    if engine_name == "PULLBACK_TREND_ENGINE":
        row = scoped_df.iloc[-1]
        spy_perf = safe_value(spy_df.iloc[-1], "Perf_3M") if spy_df is not None and not spy_df.empty else 0.0
        rs_3m = safe_value(row, "Perf_3M") - spy_perf
        ma_col = "SMA_50" if cfg(config_obj, "pullback_ma", "SMA20") == "SMA50" else "SMA_20"
        ma = safe_value(row, ma_col, safe_value(row, "Close"))
        distance = abs(safe_value(row, "Close") / ma - 1) * 100 if ma else 0.0
        trend_ok = safe_value(row, "Close") > safe_value(row, "SMA_200") and safe_value(row, "SMA_50") > safe_value(row, "SMA_200")
        rsi = safe_value(row, "RSI_14")
        score = max(0.0, min(1.0, (rs_3m + safe_value(row, "Perf_6M") + 20 - distance) / 60))
        final_score, _ = calculate_final_score(score, regime)
        action = "BUY" if (
            trend_ok and rs_3m >= cfg(config_obj, "min_rs_3m", 0.0)
            and cfg(config_obj, "rsi_min", 40.0) <= rsi <= cfg(config_obj, "rsi_max", 55.0)
            and distance <= cfg(config_obj, "max_distance_from_ma_pct", 3.0)
            and final_score >= config_obj.min_score
            and regime != "RISK_OFF"
        ) else "SKIP"
        return [make_signal(ticker, row, regime, final_score, score, f"Pullback in trend. RS 3M {rs_3m:.2f}, distance {distance:.2f}%.", strategy_name, strategy_version, action)]

    if engine_name == "MEAN_REVERSION_ETF_ENGINE":
        if ticker not in MEAN_REVERSION_ETF_UNIVERSE:
            return []
        row = scoped_df.iloc[-1]
        atr_pct = safe_value(row, "ATR_14") / safe_value(row, "Close", 1.0) * 100
        recent_drop_atr = abs(min(safe_value(row, "Perf_1M"), 0.0)) / max(atr_pct, 0.01)
        score = max(0.0, min(1.0, (cfg(config_obj, "rsi_oversold", 35.0) - safe_value(row, "RSI_14") + recent_drop_atr) / 20))
        final_score, _ = calculate_final_score(score, regime)
        action = "BUY" if (
            safe_value(row, "Close") > safe_value(row, "SMA_200")
            and safe_value(row, "RSI_14") < cfg(config_obj, "rsi_oversold", 35.0)
            and recent_drop_atr >= cfg(config_obj, "atr_drop_threshold", 1.0)
            and regime != "RISK_OFF"
        ) else "SKIP"
        return [make_signal(ticker, row, regime, final_score, score, f"ETF mean reversion. RSI {safe_value(row, 'RSI_14'):.2f}.", strategy_name, strategy_version, action)]

    raise ValueError(f"Unknown strategy engine: {engine_name}")
