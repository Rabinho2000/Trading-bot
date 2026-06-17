import pandas as pd

from strategy.backtester import BacktestConfig, simulate_portfolio
from strategy.engines import generate_target_positions, is_rebalance_date


def market_frame(close_values):
    dates = pd.date_range("2020-01-01", periods=len(close_values), freq="B")
    close = pd.Series(close_values, index=dates)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1000000,
            "SMA_20": close.rolling(2, min_periods=1).mean(),
            "SMA_50": close.rolling(2, min_periods=1).mean(),
            "SMA_200": close * 0.8,
            "RSI_14": 55,
            "ATR_14": close * 0.02,
            "Volume_Avg_20": 1000000,
            "Perf_1M": close.pct_change(2).fillna(0) * 100,
            "Perf_3M": close.pct_change(3).fillna(0) * 100,
            "Perf_6M": close.pct_change(4).fillna(0) * 100,
            "High_52W": close.rolling(5, min_periods=1).max(),
            "Dist_52W_High": close / close.rolling(5, min_periods=1).max() * 100 - 100,
            "Returns": close.pct_change().fillna(0),
            "Vol_20D": 10,
        },
        index=dates,
    )


def test_etf_rotation_top_n_selects_best_scores():
    data = {
        "SPY": market_frame([100, 101, 102, 103, 104]),
        "AAA": market_frame([100, 102, 104, 108, 112]),
        "BBB": market_frame([100, 101, 102, 103, 104]),
        "CCC": market_frame([100, 99, 98, 97, 96]),
    }
    dates = list(data["SPY"].index)
    config = BacktestConfig(
        strategy_engine="ETF_ROTATION_TOP_N_ENGINE",
        top_n=2,
        min_score=0.0,
        max_total_exposure=1.0,
        strategy_params={"universe": ["AAA", "BBB", "CCC"]},
    )

    targets = generate_target_positions("ETF_ROTATION_TOP_N_ENGINE", data, "RISK_ON", dates[-1], config, [dates[-1]])

    assert set(targets) == {"AAA", "BBB"}
    assert targets["AAA"] == 0.5


def test_is_rebalance_date_weekly_and_monthly():
    dates = list(pd.to_datetime(["2020-01-03", "2020-01-06", "2020-01-07", "2020-02-03"]))

    assert is_rebalance_date(dates[0], dates, "weekly")
    assert is_rebalance_date(dates[1], dates, "weekly")
    assert not is_rebalance_date(dates[2], dates, "weekly")
    assert is_rebalance_date(dates[3], dates, "monthly")


def test_target_rotation_sells_assets_outside_top_n(monkeypatch):
    dates = pd.date_range("2020-01-01", periods=4, freq="B")
    data = {
        "AAA": market_frame([100, 105, 100, 99]),
        "BBB": market_frame([100, 99, 110, 112]),
        "SPY": market_frame([100, 101, 102, 103]),
        "QQQ": market_frame([100, 101, 102, 103]),
    }
    targets_by_date = {
        dates[0]: {"AAA": 1.0},
        dates[1]: {"AAA": 1.0},
        dates[2]: {"BBB": 1.0},
        dates[3]: {"BBB": 1.0},
    }

    monkeypatch.setattr("strategy.backtester.has_complete_signal_data", lambda _df: True)
    monkeypatch.setattr("strategy.backtester.classify_market_regime", lambda _market: "RISK_ON")
    monkeypatch.setattr(
        "strategy.backtester.generate_target_positions",
        lambda _engine, _data, _regime, as_of_date, _config, _dates: targets_by_date[as_of_date],
    )

    result = simulate_portfolio(
        data,
        dates[0],
        dates[-1],
        BacktestConfig(
            strategy_engine="ETF_ROTATION_TOP_N_ENGINE",
            initial_capital=10000,
            max_total_exposure=1.0,
            max_position_pct=1.0,
            max_exposure_per_ticker=1.0,
            spread_slippage_pct=0.0,
        ),
    )

    assert any(trade["ticker"] == "AAA" and trade["exit_reason"] == "REBALANCE_EXIT" for trade in result["trades"])
