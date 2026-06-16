import pandas as pd

from strategy.diagnostics import build_diagnostics, exposure_diagnostics, performance_by_exit_reason


def make_trades_df():
    return pd.DataFrame(
        [
            {
                "ticker": "AAA",
                "market_regime": "RISK_ON",
                "exit_date": "2020-01-10",
                "exit_reason": "TARGET_1",
                "return_pct": 8.0,
                "pnl": 80.0,
                "final_score": 0.92,
                "holding_days": 5,
            },
            {
                "ticker": "BBB",
                "market_regime": "RISK_OFF",
                "exit_date": "2020-02-10",
                "exit_reason": "STOP",
                "return_pct": -6.0,
                "pnl": -60.0,
                "final_score": 0.74,
                "holding_days": 12,
            },
            {
                "ticker": "BBB",
                "market_regime": "RISK_OFF",
                "exit_date": "2021-02-10",
                "exit_reason": "STOP",
                "return_pct": -4.0,
                "pnl": -40.0,
                "final_score": 0.76,
                "holding_days": 18,
            },
            {
                "ticker": "BBB",
                "market_regime": "RISK_OFF",
                "exit_date": "2021-03-10",
                "exit_reason": "MAX_HOLDING_DAYS",
                "return_pct": -2.0,
                "pnl": -20.0,
                "final_score": 0.79,
                "holding_days": 30,
            },
        ]
    )


def test_build_diagnostics_flags_bad_ticker_and_regime():
    equity = pd.DataFrame(
        [
            {"equity": 1000, "cash": 1000, "positions_value": 0, "open_positions": 0},
            {"equity": 1100, "cash": 500, "positions_value": 600, "open_positions": 1},
        ]
    )

    diagnostics = build_diagnostics(make_trades_df(), equity)

    assert "BBB" in diagnostics["recommendations"]["tickers_to_remove"]
    assert "RISK_OFF" in diagnostics["recommendations"]["regimes_to_avoid"]
    assert "0.90-1.00" in diagnostics["by_score_bucket"]["score_bucket"].tolist()


def test_exposure_diagnostics_calculates_cash_and_time_in_market():
    equity = pd.DataFrame(
        [
            {"equity": 1000, "cash": 1000, "positions_value": 0, "open_positions": 0},
            {"equity": 1000, "cash": 400, "positions_value": 600, "open_positions": 2},
            {"equity": 1000, "cash": 200, "positions_value": 800, "open_positions": 3},
        ]
    )

    result = exposure_diagnostics(equity)

    assert round(result["average_portfolio_exposure"], 2) == 46.67
    assert result["max_exposure"] == 80.0
    assert round(result["average_cash_pct"], 2) == 53.33
    assert round(result["time_in_market"], 2) == 66.67
    assert round(result["average_open_positions"], 2) == 1.67


def test_exit_reason_diagnostics_includes_rejected_buckets():
    rejected = pd.DataFrame(
        [
            {"reason": "NO_NEXT_OPEN_WITHIN_BACKTEST_WINDOW"},
            {"reason": "MAX_POSITIONS_TOTAL"},
        ]
    )

    result = performance_by_exit_reason(make_trades_df(), rejected)

    entry_missed = result[result["reason"] == "ENTRY_ZONE_MISSED"].iloc[0]
    risk_rejected = result[result["reason"] == "RISK_REJECTED"].iloc[0]
    assert entry_missed["rejected"] == 1
    assert risk_rejected["rejected"] == 1
