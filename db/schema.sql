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
