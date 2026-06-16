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
    total_trades INTEGER,
    win_rate REAL,
    average_win REAL,
    average_loss REAL,
    profit_factor REAL,
    expectancy REAL,
    average_return REAL,
    max_drawdown REAL,
    spy_return REAL
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
    FOREIGN KEY(run_id) REFERENCES backtest_runs(id)
);
