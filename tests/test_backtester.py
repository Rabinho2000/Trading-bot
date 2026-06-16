import pandas as pd

from strategy.backtester import calculate_metrics, simulate_trade
from strategy.indicators import calculate_indicators
from strategy.signal_engine import generate_signal


def make_signal(**overrides):
    signal = {
        "signal_id": "abc123",
        "date": "2020-01-02",
        "ticker": "ABC",
        "market_regime": "RISK_ON",
        "invalidation": 95.0,
        "target_1": 110.0,
        "technical_score": 0.8,
        "regime_score": 1.2,
        "final_score": 0.96,
    }
    signal.update(overrides)
    return signal


def test_simulate_trade_enters_next_open_and_hits_target():
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 105.0],
            "High": [102.0, 109.0, 111.0],
            "Low": [99.0, 100.0, 104.0],
            "Close": [101.0, 108.0, 110.0],
            "Volume": [1000, 1000, 1000],
        },
        index=dates,
    )

    trade = simulate_trade(make_signal(), df, dates[0], max_holding_days=30)

    assert trade["entry_date"] == "2020-01-03"
    assert trade["entry_price"] == 101.0
    assert trade["exit_date"] == "2020-01-06"
    assert trade["exit_reason"] == "TARGET_1"
    assert round(trade["return_pct"], 4) == round((110.0 / 101.0 - 1) * 100, 4)


def test_simulate_trade_uses_stop_first_when_stop_and_target_same_day():
    dates = pd.to_datetime(["2020-01-02", "2020-01-03"])
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [102.0, 111.0],
            "Low": [99.0, 94.0],
            "Close": [101.0, 108.0],
            "Volume": [1000, 1000],
        },
        index=dates,
    )

    trade = simulate_trade(make_signal(), df, dates[0], max_holding_days=30)

    assert trade["exit_reason"] == "STOP"
    assert trade["exit_price"] == 95.0


def test_calculate_metrics_includes_spy_return_and_drawdown():
    spy = pd.DataFrame(
        {"Close": [100.0, 110.0]},
        index=pd.to_datetime(["2020-01-01", "2020-01-31"]),
    )
    trades = [{"return_pct": 10.0}, {"return_pct": -5.0}, {"return_pct": 5.0}]

    metrics = calculate_metrics(trades, spy, "2020-01-01", "2020-01-31")

    assert metrics["total_trades"] == 3
    assert round(metrics["win_rate"], 2) == 66.67
    assert metrics["average_win"] == 7.5
    assert metrics["average_loss"] == -5.0
    assert metrics["profit_factor"] == 3.0
    assert round(metrics["spy_return"], 2) == 10.0
    assert metrics["max_drawdown"] < 0


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
