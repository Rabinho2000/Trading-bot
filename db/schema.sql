-- Schema for t212-signal-lab

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    market_regime TEXT
);

CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    run_id INTEGER,
    date TEXT,
    ticker TEXT,
    action TEXT,
    entry_min REAL,
    entry_max REAL,
    invalidation REAL,
    target_1 REAL,
    target_2 REAL,
    risk_rating TEXT,
    technical_score REAL,
    regime_score REAL,
    final_score REAL,
    reason TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS signal_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT,
    summary TEXT,
    bullish_thesis TEXT,
    bearish_thesis TEXT,
    risks TEXT,
    confidence_score REAL,
    FOREIGN KEY(signal_id) REFERENCES signals(id)
);

CREATE TABLE IF NOT EXISTS price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    date TEXT,
    price REAL,
    indicators TEXT -- JSON
);

CREATE TABLE IF NOT EXISTS positions_simulated (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    entry_date TEXT,
    entry_price REAL,
    size REAL,
    status TEXT,
    exit_date TEXT,
    exit_price REAL,
    pnl REAL
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    start_date TEXT,
    end_date TEXT,
    watchlist TEXT,
    strategy_name TEXT,
    strategy_version TEXT,
    strategy_engine TEXT,
    benchmark_ticker TEXT,
    min_score REAL,
    allowed_risk_ratings TEXT,
    max_total_exposure REAL,
    use_adjusted_data INTEGER,
    rebalance_frequency TEXT,
    segment_name TEXT,
    overfit_risk INTEGER,
    initial_capital REAL,
    final_equity REAL,
    total_return REAL,
    cagr REAL,
    sharpe REAL,
    sortino REAL,
    calmar REAL,
    total_trades INTEGER,
    generated_signals INTEGER,
    rejected_trades INTEGER,
    win_rate REAL,
    average_win REAL,
    average_loss REAL,
    profit_factor REAL,
    expectancy REAL,
    average_return REAL,
    max_drawdown REAL,
    max_drawdown_value REAL,
    spy_return REAL,
    qqq_return REAL,
    spy_sma200_return REAL,
    benchmark_return REAL,
    alpha_vs_spy REAL,
    avg_holding_days REAL,
    max_concurrent_positions INTEGER,
    max_positions_total INTEGER,
    max_position_pct REAL,
    spread_slippage_pct REAL,
    currency_conversion_pct REAL,
    bankrupt INTEGER
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    signal_id TEXT,
    signal_date TEXT,
    ticker TEXT,
    market_regime TEXT,
    entry_date TEXT,
    entry_price REAL,
    exit_date TEXT,
    exit_price REAL,
    exit_reason TEXT,
    return_pct REAL,
    pnl REAL,
    technical_score REAL,
    regime_score REAL,
    final_score REAL,
    holding_days INTEGER,
    position_size REAL,
    entry_value REAL,
    exit_value REAL,
    risk_amount REAL,
    risk_pct REAL,
    cost_amount REAL,
    FOREIGN KEY(run_id) REFERENCES backtest_runs(id)
);

CREATE TABLE IF NOT EXISTS backtest_equity_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    date TEXT,
    cash REAL,
    positions_value REAL,
    equity REAL,
    drawdown_value REAL,
    drawdown_pct REAL,
    open_positions INTEGER,
    daily_return REAL,
    benchmark_daily_return REAL,
    spy_daily_return REAL,
    qqq_daily_return REAL,
    FOREIGN KEY(run_id) REFERENCES backtest_runs(id)
);

CREATE TABLE IF NOT EXISTS backtest_rejected_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    signal_id TEXT,
    signal_date TEXT,
    ticker TEXT,
    action TEXT,
    reason TEXT,
    final_score REAL,
    FOREIGN KEY(run_id) REFERENCES backtest_runs(id)
);
