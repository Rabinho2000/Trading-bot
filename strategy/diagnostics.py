import math

import pandas as pd


SCORE_BINS = [0.70, 0.75, 0.80, 0.85, 0.90, 1.000001]
SCORE_LABELS = ["0.70-0.75", "0.75-0.80", "0.80-0.85", "0.85-0.90", "0.90-1.00"]
REGIME_ORDER = ["RISK_ON", "NEUTRAL", "RISK_OFF", "HIGH_VOLATILITY"]
EXIT_REASON_ORDER = ["TARGET_1", "STOP", "MAX_HOLDING_DAYS", "END_OF_BACKTEST", "ENTRY_ZONE_MISSED", "RISK_REJECTED"]


def profit_factor(returns):
    wins = [ret for ret in returns if ret > 0]
    losses = [ret for ret in returns if ret <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss == 0:
        return math.inf if gross_win > 0 else 0.0
    return gross_win / gross_loss


def approximate_drawdown(returns):
    if len(returns) == 0:
        return 0.0

    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for ret in returns:
        equity *= 1 + (ret / 100)
        peak = max(peak, equity)
        drawdown = (equity / peak - 1) * 100 if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def compounded_return(returns):
    equity = 1.0
    for ret in returns:
        equity *= 1 + (ret / 100)
    return (equity - 1) * 100


def sharpe_like(returns):
    series = pd.Series(returns, dtype="float64")
    if len(series) < 2:
        return 0.0
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return 0.0
    return (series.mean() / std) * math.sqrt(len(series))


def cagr_like(trades_df):
    if trades_df.empty:
        return 0.0

    dates = pd.to_datetime(trades_df["exit_date"], errors="coerce").dropna()
    if dates.empty:
        return compounded_return(trades_df["return_pct"].dropna().tolist())

    years = max((dates.max() - dates.min()).days / 365.25, 1 / 365.25)
    total = compounded_return(trades_df["return_pct"].dropna().tolist()) / 100
    final_equity = max(1 + total, 0)
    if final_equity <= 0:
        return -100.0
    return (final_equity ** (1 / years) - 1) * 100


def summarize_trades(trades_df, group_col=None, categories=None):
    columns = [
        "trades",
        "win_rate",
        "average_return",
        "profit_factor",
        "expectancy",
        "total_pnl",
        "max_drawdown_approx",
    ]
    if trades_df.empty:
        group_name = group_col or "group"
        rows = [{group_name: item, **{column: 0 for column in columns}} for item in (categories or [])]
        return pd.DataFrame(rows, columns=[group_name, *columns])

    def summarize(group):
        returns = group["return_pct"].dropna().tolist()
        trades = len(group)
        wins = [ret for ret in returns if ret > 0]
        return pd.Series(
            {
                "trades": trades,
                "win_rate": (len(wins) / trades * 100) if trades else 0.0,
                "average_return": sum(returns) / trades if trades else 0.0,
                "profit_factor": profit_factor(returns),
                "expectancy": sum(returns) / trades if trades else 0.0,
                "total_pnl": group["pnl"].sum() if "pnl" in group else 0.0,
                "max_drawdown_approx": approximate_drawdown(returns),
            }
        )

    if group_col is None:
        return summarize(trades_df).to_frame().T

    result = trades_df.groupby(group_col, dropna=False).apply(summarize).reset_index()
    if categories:
        result = (
            result.set_index(group_col)
            .reindex(categories)
            .fillna(0)
            .reset_index()
        )
    return result


def add_score_bucket(trades_df):
    if trades_df.empty:
        return trades_df.copy()

    output = trades_df.copy()
    output["score_bucket"] = pd.cut(
        output["final_score"],
        bins=SCORE_BINS,
        labels=SCORE_LABELS,
        include_lowest=True,
        right=False,
    )
    output["score_bucket"] = output["score_bucket"].cat.add_categories(["OUT_OF_RANGE"]).fillna("OUT_OF_RANGE")
    return output


def performance_by_year(trades_df):
    if trades_df.empty:
        return pd.DataFrame(columns=["year", "total_return", "trades", "win_rate", "profit_factor", "max_drawdown"])

    output = trades_df.copy()
    output["year"] = pd.to_datetime(output["exit_date"], errors="coerce").dt.year
    rows = []
    for year, group in output.dropna(subset=["year"]).groupby("year"):
        returns = group["return_pct"].dropna().tolist()
        wins = [ret for ret in returns if ret > 0]
        rows.append(
            {
                "year": int(year),
                "total_return": compounded_return(returns),
                "trades": len(group),
                "win_rate": (len(wins) / len(group) * 100) if len(group) else 0.0,
                "profit_factor": profit_factor(returns),
                "max_drawdown": approximate_drawdown(returns),
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def normalize_rejection_reason(reason):
    if reason in {"NO_NEXT_OPEN_WITHIN_BACKTEST_WINDOW", "MISSING_NEXT_OPEN", "ENTRY_NOT_REACHED", "ENTRY_GAP_ABOVE_ZONE"}:
        return "ENTRY_ZONE_MISSED"
    return "RISK_REJECTED"


def performance_by_exit_reason(trades_df, rejected_df=None):
    closed = summarize_trades(trades_df, "exit_reason") if not trades_df.empty else pd.DataFrame()
    if not closed.empty:
        closed = closed.rename(columns={"exit_reason": "reason"})
        closed["rejected"] = 0

    rejected_rows = []
    if rejected_df is not None and not rejected_df.empty:
        rejected = rejected_df.copy()
        rejected["reason"] = rejected["reason"].apply(normalize_rejection_reason)
        rejected_rows = [
            {
                "reason": reason,
                "trades": 0,
                "win_rate": 0.0,
                "average_return": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "total_pnl": 0.0,
                "max_drawdown_approx": 0.0,
                "rejected": len(group),
            }
            for reason, group in rejected.groupby("reason")
        ]

    combined = pd.concat([closed, pd.DataFrame(rejected_rows)], ignore_index=True) if rejected_rows else closed
    if combined.empty:
        combined = pd.DataFrame(columns=["reason", "trades", "win_rate", "average_return", "profit_factor", "expectancy", "total_pnl", "max_drawdown_approx", "rejected"])

    combined = combined.groupby("reason", as_index=False).agg(
        {
            "trades": "sum",
            "win_rate": "mean",
            "average_return": "mean",
            "profit_factor": "mean",
            "expectancy": "mean",
            "total_pnl": "sum",
            "max_drawdown_approx": "min",
            "rejected": "sum",
        }
    )
    return combined.set_index("reason").reindex(EXIT_REASON_ORDER).fillna(0).reset_index()


def exposure_diagnostics(equity_df):
    if equity_df.empty:
        return {
            "average_portfolio_exposure": 0.0,
            "max_exposure": 0.0,
            "average_cash_pct": 0.0,
            "time_in_market": 0.0,
            "average_open_positions": 0.0,
        }

    safe_equity = equity_df["equity"].replace(0, pd.NA)
    exposure = (equity_df["positions_value"] / safe_equity * 100).fillna(0)
    cash_pct = (equity_df["cash"] / safe_equity * 100).fillna(0)
    return {
        "average_portfolio_exposure": exposure.mean(),
        "max_exposure": exposure.max(),
        "average_cash_pct": cash_pct.mean(),
        "time_in_market": (equity_df["open_positions"].gt(0).mean() * 100),
        "average_open_positions": equity_df["open_positions"].mean(),
    }


def rejection_reason_summary(rejected_df):
    if rejected_df is None or rejected_df.empty:
        return pd.DataFrame(columns=["reason", "rejected"])
    return rejected_df.groupby("reason").size().reset_index(name="rejected").sort_values("rejected", ascending=False)


def portfolio_efficiency_diagnostics(trades_df, equity_df):
    turnover = 0.0
    cost_drag = 0.0
    beta = 0.0
    correlation = 0.0
    information_ratio = 0.0

    if not trades_df.empty and not equity_df.empty and "entry_value" in trades_df:
        avg_equity = equity_df["equity"].mean()
        total_entry_value = trades_df["entry_value"].fillna(0).sum()
        turnover = total_entry_value / avg_equity if avg_equity else 0.0
        if "cost_amount" in trades_df:
            cost_drag = trades_df["cost_amount"].fillna(0).sum() / avg_equity * 100 if avg_equity else 0.0

    if not equity_df.empty and "benchmark_daily_return" in equity_df:
        strategy_returns = equity_df["daily_return"].fillna(0) / 100
        benchmark_returns = equity_df["benchmark_daily_return"].fillna(0) / 100
        if len(strategy_returns) > 2 and benchmark_returns.var() > 0:
            beta = strategy_returns.cov(benchmark_returns) / benchmark_returns.var()
            correlation = strategy_returns.corr(benchmark_returns)
            active_returns = strategy_returns - benchmark_returns
            tracking_error = active_returns.std(ddof=0)
            information_ratio = (active_returns.mean() / tracking_error) * math.sqrt(252) if tracking_error else 0.0

    return {
        "turnover": turnover,
        "cost_drag": cost_drag,
        "beta_vs_spy": 0.0 if pd.isna(beta) else beta,
        "correlation_vs_spy": 0.0 if pd.isna(correlation) else correlation,
        "information_ratio": 0.0 if pd.isna(information_ratio) else information_ratio,
    }


def candidate_filter_stats(trades_df, mask):
    filtered = trades_df.loc[mask].copy()
    if filtered.empty:
        return {"trades": 0, "sharpe": 0.0, "cagr": 0.0, "return": 0.0}
    returns = filtered["return_pct"].dropna().tolist()
    return {
        "trades": len(filtered),
        "sharpe": sharpe_like(returns),
        "cagr": cagr_like(filtered),
        "return": compounded_return(returns),
    }


def generate_recommendations(trades_df, min_trades=3):
    if trades_df.empty:
        return {
            "tickers_to_remove": [],
            "regimes_to_avoid": [],
            "score_minimum_recommended": None,
            "max_holding_ideal": None,
            "filters": [],
        }

    ticker_perf = summarize_trades(trades_df, "ticker")
    regime_perf = summarize_trades(trades_df, "market_regime", REGIME_ORDER)
    tickers_to_remove = ticker_perf[
        (ticker_perf["trades"] >= min_trades)
        & ((ticker_perf["expectancy"] < 0) | (ticker_perf["profit_factor"] < 1))
    ].sort_values(["expectancy", "total_pnl"])["ticker"].tolist()

    regimes_to_avoid = regime_perf[
        (regime_perf["trades"] >= min_trades)
        & ((regime_perf["expectancy"] < 0) | (regime_perf["profit_factor"] < 1))
    ]["market_regime"].tolist()

    base = candidate_filter_stats(trades_df, pd.Series(True, index=trades_df.index))
    score_candidates = []
    for threshold in [0.70, 0.75, 0.80, 0.85, 0.90]:
        stats = candidate_filter_stats(trades_df, trades_df["final_score"] >= threshold)
        if stats["trades"] >= min_trades:
            score_candidates.append((threshold, stats))
    best_score = max(score_candidates, key=lambda item: (item[1]["sharpe"], item[1]["cagr"]))[0] if score_candidates else None

    holding_candidates = []
    for max_days in [5, 10, 15, 20, 30, 45, 60]:
        if "holding_days" not in trades_df:
            continue
        stats = candidate_filter_stats(trades_df, trades_df["holding_days"] <= max_days)
        if stats["trades"] >= min_trades:
            holding_candidates.append((max_days, stats))
    best_holding = max(holding_candidates, key=lambda item: (item[1]["sharpe"], item[1]["cagr"]))[0] if holding_candidates else None

    filters = []
    if tickers_to_remove:
        stats = candidate_filter_stats(trades_df, ~trades_df["ticker"].isin(tickers_to_remove))
        if stats["sharpe"] > base["sharpe"] or stats["cagr"] > base["cagr"]:
            filters.append(f"Remove weak tickers: {', '.join(tickers_to_remove)}")
    if regimes_to_avoid:
        stats = candidate_filter_stats(trades_df, ~trades_df["market_regime"].isin(regimes_to_avoid))
        if stats["sharpe"] > base["sharpe"] or stats["cagr"] > base["cagr"]:
            filters.append(f"Avoid regimes: {', '.join(regimes_to_avoid)}")
    if best_score is not None:
        stats = candidate_filter_stats(trades_df, trades_df["final_score"] >= best_score)
        if stats["sharpe"] > base["sharpe"] or stats["cagr"] > base["cagr"]:
            filters.append(f"Use minimum score >= {best_score:.2f}")
    if best_holding is not None:
        stats = candidate_filter_stats(trades_df, trades_df["holding_days"] <= best_holding)
        if stats["sharpe"] > base["sharpe"] or stats["cagr"] > base["cagr"]:
            filters.append(f"Cap holding days at {best_holding}")

    return {
        "tickers_to_remove": tickers_to_remove,
        "regimes_to_avoid": regimes_to_avoid,
        "score_minimum_recommended": best_score,
        "max_holding_ideal": best_holding,
        "filters": filters,
    }


def build_diagnostics(trades_df, equity_df, rejected_df=None):
    trades_df = trades_df.copy()
    equity_df = equity_df.copy()
    rejected_df = rejected_df.copy() if rejected_df is not None else pd.DataFrame()
    bucketed = add_score_bucket(trades_df)

    return {
        "by_ticker": summarize_trades(trades_df, "ticker").sort_values("total_pnl") if not trades_df.empty else pd.DataFrame(),
        "by_regime": summarize_trades(trades_df, "market_regime", REGIME_ORDER),
        "by_year": performance_by_year(trades_df),
        "by_exit_reason": performance_by_exit_reason(trades_df, rejected_df),
        "by_rejection_reason": rejection_reason_summary(rejected_df),
        "by_score_bucket": summarize_trades(bucketed, "score_bucket", SCORE_LABELS),
        "exposure": exposure_diagnostics(equity_df),
        "efficiency": portfolio_efficiency_diagnostics(trades_df, equity_df),
        "recommendations": generate_recommendations(trades_df),
    }
