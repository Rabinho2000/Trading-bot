import pandas as pd

from strategy import backtester
from strategy.backtester import (
    BacktestConfig,
    calculate_equity_drawdowns,
    calculate_metrics,
    calculate_trade_stats,
    simulate_portfolio,
)
from strategy.indicators import calculate_indicators
from strategy.signal_engine import generate_signal


def test_drawdown_uses_equity_curve_not_trade_multiplication():
    drawdowns, max_dd_value, max_dd_pct = calculate_equity_drawdowns([10000, 12000, 9000, 11000])

    assert drawdowns[2] == (-3000, -25.0)
    assert max_dd_value == -3000
    assert max_dd_pct == -25.0


def test_profit_factor_and_expectancy_are_trade_based():
    stats = calculate_trade_stats(
        [
            {"return_pct": 10.0, "holding_days": 5},
            {"return_pct": -5.0, "holding_days": 3},
            {"return_pct": 2.5, "holding_days": 2},
        ]
    )

    assert stats["total_trades"] == 3
    assert round(stats["win_rate"], 2) == 66.67
    assert stats["profit_factor"] == 2.5
    assert stats["expectancy"] == 2.5
    assert round(stats["avg_holding_days"], 2) == 3.33


def test_calculate_metrics_uses_daily_equity_for_return_and_drawdown():
    equity_curve = [
        {
            "date": "2020-01-01",
            "equity": 10000,
            "drawdown_value": 0,
            "drawdown_pct": 0,
            "daily_return": 0,
        },
        {
            "date": "2020-01-02",
            "equity": 12000,
            "drawdown_value": 0,
            "drawdown_pct": 0,
            "daily_return": 20,
        },
        {
            "date": "2020-01-03",
            "equity": 9000,
            "drawdown_value": -3000,
            "drawdown_pct": -25,
            "daily_return": -25,
        },
    ]
    spy = pd.DataFrame(
        {"Close": [100.0, 110.0]},
        index=pd.to_datetime(["2020-01-01", "2020-01-03"]),
    )

    metrics = calculate_metrics(
        [{"return_pct": -10.0, "holding_days": 2}],
        equity_curve,
        {"SPY": spy, "QQQ": spy.copy()},
        "2020-01-01",
        "2020-01-03",
        10000,
    )

    assert round(metrics["total_return"], 2) == -10.0
    assert metrics["max_drawdown"] == -25
    assert metrics["max_drawdown_value"] == -3000
    assert round(metrics["spy_return"], 2) == 10.0
    assert round(metrics["alpha_vs_spy"], 2) == -20.0


def test_simulate_portfolio_builds_daily_equity_and_closed_trades(monkeypatch):
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    abc = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0],
            "High": [101.0, 101.0, 112.0],
            "Low": [99.0, 99.0, 99.0],
            "Close": [100.0, 100.0, 110.0],
            "Volume": [1000, 1000, 1000],
        },
        index=dates,
    )
    market = {"ABC": abc, "SPY": abc.copy(), "QQQ": abc.copy()}

    def fake_complete(_df):
        return True

    def fake_regime(_market):
        return "RISK_ON"

    def fake_engine_signals(_engine, ticker, _df, _regime, as_of_date, _config, market_data=None, all_dates=None):
        if ticker != "ABC" or as_of_date != dates[0]:
            return []
        return [{
            "signal_id": "abc-buy",
            "date": "2020-01-01",
            "ticker": "ABC",
            "action": "BUY",
            "entry_zone": {"min": 99.0, "max": 101.0},
            "invalidation": 95.0,
            "target_1": 110.0,
            "risk_rating": "LOW",
            "technical_score": 0.8,
            "regime_score": 1.2,
            "final_score": 0.96,
        }]

    monkeypatch.setattr(backtester, "has_complete_signal_data", fake_complete)
    monkeypatch.setattr(backtester, "classify_market_regime", fake_regime)
    monkeypatch.setattr(backtester, "generate_engine_signals", fake_engine_signals)

    result = simulate_portfolio(
        market,
        dates[0],
        dates[-1],
        BacktestConfig(
            initial_capital=10000,
            max_holding_days=30,
            max_positions_total=1,
            max_position_pct=0.5,
            max_exposure_per_ticker=0.5,
            max_total_exposure=1.0,
            max_risk_per_trade=1.0,
            spread_slippage_pct=0.0,
            currency_conversion_pct=0.0,
        ),
    )

    assert len(result["equity_curve"]) == 3
    assert len(result["trades"]) == 1
    assert result["trades"][0]["entry_date"] == "2020-01-02"
    assert result["trades"][0]["exit_date"] == "2020-01-03"
    assert result["trades"][0]["exit_reason"] == "TARGET_1"
    assert result["equity_curve"][-1]["equity"] == 10500.0
    assert result["max_concurrent_positions"] == 1


def test_entry_zone_rejects_gap_above_zone(monkeypatch):
    dates = pd.to_datetime(["2020-01-01", "2020-01-02"])
    abc = pd.DataFrame(
        {
            "Open": [100.0, 105.0],
            "High": [101.0, 106.0],
            "Low": [99.0, 104.0],
            "Close": [100.0, 105.0],
            "Volume": [1000, 1000],
        },
        index=dates,
    )

    monkeypatch.setattr(backtester, "has_complete_signal_data", lambda _df: True)
    monkeypatch.setattr(backtester, "classify_market_regime", lambda _market: "RISK_ON")
    monkeypatch.setattr(
        backtester,
        "generate_engine_signals",
        lambda _engine, ticker, _df, _regime, as_of_date, _config, **_kwargs: [{
            "signal_id": "gap",
            "date": "2020-01-01",
            "ticker": "ABC",
            "action": "BUY",
            "entry_zone": {"min": 99.0, "max": 101.0},
            "invalidation": 95.0,
            "target_1": 110.0,
            "risk_rating": "LOW",
            "technical_score": 0.8,
            "regime_score": 1.2,
            "final_score": 0.96,
        }] if ticker == "ABC" and as_of_date == dates[0] else [],
    )

    result = simulate_portfolio({"ABC": abc, "SPY": abc.copy(), "QQQ": abc.copy()}, dates[0], dates[-1], BacktestConfig())

    assert result["trades"] == []
    assert result["rejected_trades"][0]["reason"] == "ENTRY_GAP_ABOVE_ZONE"


def test_entry_zone_rejects_not_reached(monkeypatch):
    dates = pd.to_datetime(["2020-01-01", "2020-01-02"])
    abc = pd.DataFrame(
        {
            "Open": [100.0, 95.0],
            "High": [101.0, 96.0],
            "Low": [99.0, 94.0],
            "Close": [100.0, 95.0],
            "Volume": [1000, 1000],
        },
        index=dates,
    )

    monkeypatch.setattr(backtester, "has_complete_signal_data", lambda _df: True)
    monkeypatch.setattr(backtester, "classify_market_regime", lambda _market: "RISK_ON")
    monkeypatch.setattr(
        backtester,
        "generate_engine_signals",
        lambda _engine, ticker, _df, _regime, as_of_date, _config, **_kwargs: [{
            "signal_id": "not-reached",
            "date": "2020-01-01",
            "ticker": "ABC",
            "action": "BUY",
            "entry_zone": {"min": 99.0, "max": 101.0},
            "invalidation": 90.0,
            "target_1": 110.0,
            "risk_rating": "LOW",
            "technical_score": 0.8,
            "regime_score": 1.2,
            "final_score": 0.96,
        }] if ticker == "ABC" and as_of_date == dates[0] else [],
    )

    result = simulate_portfolio({"ABC": abc, "SPY": abc.copy(), "QQQ": abc.copy()}, dates[0], dates[-1], BacktestConfig())

    assert result["trades"] == []
    assert result["rejected_trades"][0]["reason"] == "ENTRY_NOT_REACHED"


def test_risk_based_position_sizing_caps_shares(monkeypatch):
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    abc = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0],
            "High": [101.0, 101.0, 110.0],
            "Low": [99.0, 99.0, 99.0],
            "Close": [100.0, 100.0, 110.0],
            "Volume": [1000, 1000, 1000],
        },
        index=dates,
    )

    monkeypatch.setattr(backtester, "has_complete_signal_data", lambda _df: True)
    monkeypatch.setattr(backtester, "classify_market_regime", lambda _market: "RISK_ON")
    monkeypatch.setattr(
        backtester,
        "generate_engine_signals",
        lambda _engine, ticker, _df, _regime, as_of_date, _config, **_kwargs: [{
            "signal_id": "risk",
            "date": "2020-01-01",
            "ticker": "ABC",
            "action": "BUY",
            "entry_zone": {"min": 99.0, "max": 101.0},
            "invalidation": 90.0,
            "target_1": 110.0,
            "risk_rating": "LOW",
            "technical_score": 0.8,
            "regime_score": 1.2,
            "final_score": 0.96,
        }] if ticker == "ABC" and as_of_date == dates[0] else [],
    )

    result = simulate_portfolio(
        {"ABC": abc, "SPY": abc.copy(), "QQQ": abc.copy()},
        dates[0],
        dates[-1],
        BacktestConfig(
            initial_capital=10000,
            max_position_pct=1.0,
            max_exposure_per_ticker=1.0,
            max_total_exposure=1.0,
            max_risk_per_trade=0.01,
            spread_slippage_pct=0.0,
        ),
    )

    trade = result["trades"][0]
    assert trade["position_size"] == 10.0
    assert trade["risk_amount"] == 100.0
    assert trade["risk_pct"] == 1.0


def test_position_sizing_respects_total_and_ticker_exposure(monkeypatch):
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    abc = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0],
            "High": [101.0, 101.0, 110.0],
            "Low": [99.0, 99.0, 99.0],
            "Close": [100.0, 100.0, 110.0],
            "Volume": [1000, 1000, 1000],
        },
        index=dates,
    )

    monkeypatch.setattr(backtester, "has_complete_signal_data", lambda _df: True)
    monkeypatch.setattr(backtester, "classify_market_regime", lambda _market: "RISK_ON")
    monkeypatch.setattr(
        backtester,
        "generate_engine_signals",
        lambda _engine, ticker, _df, _regime, as_of_date, _config, **_kwargs: [{
            "signal_id": "exposure",
            "date": "2020-01-01",
            "ticker": "ABC",
            "action": "BUY",
            "entry_zone": {"min": 99.0, "max": 101.0},
            "invalidation": 50.0,
            "target_1": 110.0,
            "risk_rating": "LOW",
            "technical_score": 0.8,
            "regime_score": 1.2,
            "final_score": 0.96,
        }] if ticker == "ABC" and as_of_date == dates[0] else [],
    )

    result = simulate_portfolio(
        {"ABC": abc, "SPY": abc.copy(), "QQQ": abc.copy()},
        dates[0],
        dates[-1],
        BacktestConfig(
            initial_capital=10000,
            max_position_pct=1.0,
            max_exposure_per_ticker=0.05,
            max_total_exposure=0.30,
            max_risk_per_trade=1.0,
            spread_slippage_pct=0.0,
        ),
    )

    trade = result["trades"][0]
    assert trade["entry_value"] == 500.0
    assert trade["position_size"] == 5.0


def test_generate_signal_as_of_date_ignores_future_rows():
    dates = pd.date_range("2020-01-01", periods=260, freq="B")
    df = pd.DataFrame(
        {
            "Open": [100.0] * 260,
            "High": [101.0] * 260,
            "Low": [99.0] * 260,
            "Close": [100.0] * 259 + [300.0],
            "Volume": [1000] * 260,
        },
        index=dates,
    )
    df = calculate_indicators(df)

    as_of_date = dates[-2]
    signal = generate_signal("ABC", df, "RISK_ON", as_of_date=as_of_date)

    assert signal["date"] == as_of_date.strftime("%Y-%m-%d")
    assert signal["entry_zone"]["min"] == 99.0
    sliced_signal = generate_signal("ABC", df.loc[:as_of_date], "RISK_ON", as_of_date=as_of_date)
    assert signal["signal_id"] == sliced_signal["signal_id"]
