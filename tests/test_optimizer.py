from strategy.optimizer import build_parameter_grid, detect_overfit_risk, rank_results, score_optimization_result


def test_parameter_grid_builds_range_and_values():
    grid = build_parameter_grid(
        {
            "min_score": {"start": 0.70, "end": 0.80, "step": 0.05},
            "max_positions_total": {"values": [3, 5]},
        }
    )

    assert len(grid) == 6
    assert {"min_score": 0.7, "max_positions_total": 3} in grid
    assert {"min_score": 0.8, "max_positions_total": 5} in grid


def test_rank_results_ranks_total_return_and_robust_score():
    ranked = rank_results(
        [
            {"total_return": 10, "cagr": 8, "sharpe": 0.8, "calmar": 0.5, "alpha_vs_spy": 1, "max_drawdown": -10, "turnover": 1},
            {"total_return": 20, "cagr": 5, "sharpe": 0.2, "calmar": 0.2, "alpha_vs_spy": -2, "max_drawdown": -30, "turnover": 5},
        ]
    )

    best_return = next(row for row in ranked if row["total_return"] == 20)
    assert best_return["rank_total_return"] == 1
    assert ranked[0]["rank_robust_score"] == 1


def test_score_optimization_result_prefers_balanced_metrics():
    good = score_optimization_result({"cagr": 15, "sharpe": 1.0, "calmar": 1.5, "alpha_vs_spy": 10, "max_drawdown": -12, "turnover": 1})
    bad = score_optimization_result({"cagr": 20, "sharpe": 0.2, "calmar": 0.1, "alpha_vs_spy": 5, "max_drawdown": -45, "turnover": 8})

    assert good > bad


def test_detect_overfit_risk_rules():
    assert detect_overfit_risk(
        {"sharpe": 1.2, "cagr": 20, "total_return": 80, "spy_return": 30},
        {},
        {"sharpe": 0.1, "cagr": -5, "total_return": 0, "spy_return": 30, "max_drawdown": -10, "total_trades": 30},
    )
    assert detect_overfit_risk(
        {"sharpe": 0.7, "cagr": 8, "total_return": 20, "spy_return": 10},
        {},
        {"sharpe": 0.6, "cagr": 6, "total_return": 10, "spy_return": 8, "max_drawdown": -10, "total_trades": 10},
    )
