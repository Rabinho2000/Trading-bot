from __future__ import annotations

import itertools
import math
from decimal import Decimal

import pandas as pd

from db.database import OptimizationResult, OptimizationRun, get_session, init_db
from strategy.backtester import run_backtest


ROBUST_SCORE_FORMULA = (
    "robust_score = 0.30*normalized_cagr + 0.25*normalized_sharpe "
    "+ 0.20*normalized_calmar + 0.15*normalized_alpha_vs_spy "
    "- 0.10*drawdown_penalty - 0.10*turnover_penalty"
)


def _range_values(spec):
    if "values" in spec:
        return list(spec["values"])
    start = Decimal(str(spec["start"]))
    end = Decimal(str(spec["end"]))
    step = Decimal(str(spec["step"]))
    values = []
    current = start
    while current <= end:
        value = float(current)
        if value.is_integer():
            value = int(value)
        values.append(value)
        current += step
    return values


def build_parameter_grid(param_ranges):
    keys = list(param_ranges.keys())
    values = [_range_values(param_ranges[key]) for key in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _bounded(value, low, high):
    if value is None or math.isnan(float(value)):
        return 0.0
    if high == low:
        return 0.0
    return max(0.0, min(1.0, (float(value) - low) / (high - low)))


def score_optimization_result(metrics):
    normalized_cagr = _bounded(metrics.get("cagr", 0.0), -10.0, 30.0)
    normalized_sharpe = _bounded(metrics.get("sharpe", 0.0), 0.0, 2.0)
    normalized_calmar = _bounded(metrics.get("calmar", 0.0), 0.0, 3.0)
    normalized_alpha = _bounded(metrics.get("alpha_vs_spy", 0.0), -20.0, 40.0)
    drawdown_penalty = _bounded(abs(metrics.get("max_drawdown", 0.0)), 10.0, 50.0)
    turnover_penalty = _bounded(metrics.get("turnover", 0.0), 1.0, 10.0)
    return (
        0.30 * normalized_cagr
        + 0.25 * normalized_sharpe
        + 0.20 * normalized_calmar
        + 0.15 * normalized_alpha
        - 0.10 * drawdown_penalty
        - 0.10 * turnover_penalty
    )


def detect_overfit_risk(train_metrics, validation_metrics=None, test_metrics=None):
    test_metrics = test_metrics or validation_metrics or {}
    train_metrics = train_metrics or {}
    train_return = train_metrics.get("total_return", 0.0)
    test_return = test_metrics.get("total_return", 0.0)
    test_spy = test_metrics.get("spy_return", test_metrics.get("benchmark_return", 0.0))
    train_spy = train_metrics.get("spy_return", train_metrics.get("benchmark_return", 0.0))
    return bool(
        (train_metrics.get("sharpe", 0.0) > 0.8 and test_metrics.get("sharpe", 0.0) < 0.3)
        or (train_metrics.get("cagr", 0.0) > 10.0 and test_metrics.get("cagr", 0.0) < 0.0)
        or (train_return > train_spy and (test_spy - test_return) > 20.0)
        or (test_metrics.get("max_drawdown", 0.0) < -25.0)
        or (test_metrics.get("total_trades", 0) < 20)
    )


def _rank(items, key):
    sorted_items = sorted(items, key=lambda item: item.get(key, 0.0), reverse=True)
    for rank, item in enumerate(sorted_items, start=1):
        item[f"rank_{key}"] = rank


def rank_results(results):
    output = [dict(row) for row in results]
    for row in output:
        row["robust_score"] = row.get("robust_score", score_optimization_result(row))
    for key in ["total_return", "cagr", "sharpe", "calmar", "robust_score"]:
        _rank(output, key)
    return sorted(output, key=lambda row: row.get("rank_robust_score", 999999))


def _result_row(parameters, backtest_result, strategy_engine):
    metrics = dict(backtest_result.metrics)
    metrics["strategy_engine"] = strategy_engine
    metrics["parameters"] = parameters
    metrics["parameters_json"] = parameters
    metrics["run_id"] = backtest_result.run_id
    metrics["backtest_run_id"] = backtest_result.run_id
    metrics["robust_score"] = score_optimization_result(metrics)
    metrics["overfit_risk"] = False
    return metrics


def _save_results(opt_run_id, ranked):
    session = get_session()
    try:
        for row in ranked:
            session.add(
                OptimizationResult(
                    optimization_run_id=opt_run_id,
                    backtest_run_id=row.get("backtest_run_id"),
                    rank_total_return=row.get("rank_total_return"),
                    rank_cagr=row.get("rank_cagr"),
                    rank_sharpe=row.get("rank_sharpe"),
                    rank_calmar=row.get("rank_calmar"),
                    rank_robust_score=row.get("rank_robust_score"),
                    parameters_json=row.get("parameters_json", row.get("parameters", {})),
                    total_return=row.get("total_return", 0.0),
                    cagr=row.get("cagr", 0.0),
                    sharpe=row.get("sharpe", 0.0),
                    sortino=row.get("sortino", 0.0),
                    calmar=row.get("calmar", 0.0),
                    max_drawdown=row.get("max_drawdown", 0.0),
                    profit_factor=None if math.isinf(row.get("profit_factor", 0.0)) else row.get("profit_factor", 0.0),
                    expectancy=row.get("expectancy", 0.0),
                    win_rate=row.get("win_rate", 0.0),
                    total_trades=row.get("total_trades", 0),
                    benchmark_return=row.get("benchmark_return", 0.0),
                    alpha_vs_spy=row.get("alpha_vs_spy", 0.0),
                    robust_score=row.get("robust_score", 0.0),
                    overfit_risk=row.get("overfit_risk", False),
                    train_metrics_json=row.get("train_metrics"),
                    validation_metrics_json=row.get("validation_metrics"),
                    test_metrics_json=row.get("test_metrics"),
                )
            )
        opt_run = session.query(OptimizationRun).filter(OptimizationRun.id == opt_run_id).first()
        if opt_run:
            opt_run.completed_combinations = len(ranked)
            opt_run.status = "COMPLETED"
        session.commit()
    finally:
        session.close()


def _create_run(strategy_engine, start, end, optimization_mode, param_ranges, total_combinations):
    session = get_session()
    try:
        opt_run = OptimizationRun(
            strategy_engine=strategy_engine,
            start_date=str(start),
            end_date=str(end),
            optimization_mode=optimization_mode,
            parameter_ranges_json=param_ranges,
            total_combinations=total_combinations,
            completed_combinations=0,
            status="RUNNING",
            notes=ROBUST_SCORE_FORMULA,
        )
        session.add(opt_run)
        session.commit()
        return opt_run.id
    finally:
        session.close()


def _run_walk_forward_combo(parameters, strategy_engine, watchlist, common_kwargs):
    segments = {
        "train": ("2015-01-01", "2020-12-31"),
        "validation": ("2021-01-01", "2022-12-31"),
        "test": ("2023-01-01", "2025-12-31"),
    }
    segment_results = {}
    for segment_name, (start, end) in segments.items():
        result = run_backtest(
            start,
            end,
            watchlist=watchlist,
            strategy_engine=strategy_engine,
            strategy_name=strategy_engine,
            strategy_version=f"optimizer_{segment_name}",
            segment_name=segment_name,
            **common_kwargs,
            **parameters,
        )
        segment_results[segment_name] = result
    train = segment_results["train"].metrics
    validation = segment_results["validation"].metrics
    test = segment_results["test"].metrics
    row = _result_row(parameters, segment_results["test"], strategy_engine)
    row.update(
        {
            "train_cagr": train.get("cagr", 0.0),
            "validation_cagr": validation.get("cagr", 0.0),
            "test_cagr": test.get("cagr", 0.0),
            "train_sharpe": train.get("sharpe", 0.0),
            "validation_sharpe": validation.get("sharpe", 0.0),
            "test_sharpe": test.get("sharpe", 0.0),
            "train_calmar": train.get("calmar", 0.0),
            "validation_calmar": validation.get("calmar", 0.0),
            "test_calmar": test.get("calmar", 0.0),
            "train_max_drawdown": train.get("max_drawdown", 0.0),
            "validation_max_drawdown": validation.get("max_drawdown", 0.0),
            "test_max_drawdown": test.get("max_drawdown", 0.0),
            "test_alpha_vs_spy": test.get("alpha_vs_spy", 0.0),
            "train_metrics": train,
            "validation_metrics": validation,
            "test_metrics": test,
            "overfit_risk": detect_overfit_risk(train, validation, test),
        }
    )
    return row


def run_optimization(
    start,
    end,
    param_ranges,
    strategy_engine="SIGNAL_ENGINE",
    watchlist=None,
    optimization_mode="single_period",
    confirm_large_grid=False,
    **common_kwargs,
):
    init_db()
    grid = build_parameter_grid(param_ranges)
    if len(grid) > 500 and not confirm_large_grid:
        raise ValueError(f"Optimization grid has {len(grid)} combinations. Pass confirm_large_grid=True to run more than 500.")

    opt_run_id = _create_run(strategy_engine, start, end, optimization_mode, param_ranges, len(grid))
    rows = []
    for parameters in grid:
        if optimization_mode == "walk_forward":
            row = _run_walk_forward_combo(parameters, strategy_engine, watchlist, common_kwargs)
        else:
            result = run_backtest(
                start,
                end,
                watchlist=watchlist,
                strategy_engine=strategy_engine,
                strategy_name=strategy_engine,
                strategy_version="optimizer",
                segment_name="optimizer",
                **common_kwargs,
                **parameters,
            )
            row = _result_row(parameters, result, strategy_engine)
        rows.append(row)

    ranked = rank_results(rows)
    _save_results(opt_run_id, ranked)
    return {"optimization_run_id": opt_run_id, "total_combinations": len(grid), "results": ranked}


def results_to_frame(results):
    return pd.DataFrame(results)
