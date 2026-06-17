from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

Base = declarative_base()

class Run(Base):
    __tablename__ = 'runs'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    market_regime = Column(String)
    signals = relationship("Signal", back_populates="run")

class Signal(Base):
    __tablename__ = 'signals'
    id = Column(String, primary_key=True)  # Deterministic ID
    run_id = Column(Integer, ForeignKey('runs.id'))
    date = Column(String)
    ticker = Column(String)
    action = Column(String)
    entry_min = Column(Float)
    entry_max = Column(Float)
    invalidation = Column(Float)
    target_1 = Column(Float)
    target_2 = Column(Float)
    risk_rating = Column(String)
    technical_score = Column(Float)
    regime_score = Column(Float)
    final_score = Column(Float)
    reason = Column(String)
    run = relationship("Run", back_populates="signals")
    review = relationship("SignalReview", uselist=False, back_populates="signal")

class SignalReview(Base):
    __tablename__ = 'signal_reviews'
    id = Column(Integer, primary_key=True)
    signal_id = Column(String, ForeignKey('signals.id'))
    summary = Column(String)
    bullish_thesis = Column(String)
    bearish_thesis = Column(String)
    risks = Column(String)
    confidence_score = Column(Float)
    signal = relationship("Signal", back_populates="review")

class PriceSnapshot(Base):
    __tablename__ = 'price_snapshots'
    id = Column(Integer, primary_key=True)
    ticker = Column(String)
    date = Column(String)
    price = Column(Float)
    indicators = Column(JSON)

class PositionSimulated(Base):
    __tablename__ = 'positions_simulated'
    id = Column(Integer, primary_key=True)
    ticker = Column(String)
    entry_date = Column(String)
    entry_price = Column(Float)
    size = Column(Float)
    status = Column(String)  # OPEN, CLOSED
    exit_date = Column(String, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)

class BacktestRun(Base):
    __tablename__ = 'backtest_runs'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    start_date = Column(String)
    end_date = Column(String)
    watchlist = Column(String)
    strategy_name = Column(String, default="SIGNAL_ENGINE")
    strategy_version = Column(String, default="1.0")
    strategy_engine = Column(String, default="SIGNAL_ENGINE")
    benchmark_ticker = Column(String, default="SPY")
    min_score = Column(Float, default=0.75)
    allowed_risk_ratings = Column(String, default="LOW,MEDIUM,HIGH")
    max_total_exposure = Column(Float, default=0.30)
    use_adjusted_data = Column(Boolean, default=False)
    rebalance_frequency = Column(String, default="weekly")
    segment_name = Column(String, default="full")
    overfit_risk = Column(Boolean, default=False)
    initial_capital = Column(Float, default=10000.0)
    final_equity = Column(Float, default=0.0)
    total_return = Column(Float, default=0.0)
    cagr = Column(Float, default=0.0)
    sharpe = Column(Float, default=0.0)
    sortino = Column(Float, default=0.0)
    calmar = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    generated_signals = Column(Integer, default=0)
    rejected_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    average_win = Column(Float, default=0.0)
    average_loss = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    expectancy = Column(Float, default=0.0)
    average_return = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    max_drawdown_value = Column(Float, default=0.0)
    spy_return = Column(Float, default=0.0)
    qqq_return = Column(Float, default=0.0)
    spy_sma200_return = Column(Float, default=0.0)
    benchmark_return = Column(Float, default=0.0)
    alpha_vs_spy = Column(Float, default=0.0)
    avg_holding_days = Column(Float, default=0.0)
    max_concurrent_positions = Column(Integer, default=0)
    max_positions_total = Column(Integer, default=5)
    max_position_pct = Column(Float, default=0.2)
    spread_slippage_pct = Column(Float, default=0.0)
    currency_conversion_pct = Column(Float, default=0.0)
    bankrupt = Column(Boolean, default=False)
    trades = relationship("BacktestTrade", back_populates="run")
    equity_points = relationship("BacktestEquityCurve", back_populates="run")
    rejected = relationship("BacktestRejectedTrade", back_populates="run")

class BacktestTrade(Base):
    __tablename__ = 'backtest_trades'
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('backtest_runs.id'))
    signal_id = Column(String)
    signal_date = Column(String)
    ticker = Column(String)
    market_regime = Column(String)
    entry_date = Column(String)
    entry_price = Column(Float)
    exit_date = Column(String)
    exit_price = Column(Float)
    exit_reason = Column(String)
    return_pct = Column(Float)
    pnl = Column(Float)
    technical_score = Column(Float)
    regime_score = Column(Float)
    final_score = Column(Float)
    holding_days = Column(Integer)
    position_size = Column(Float)
    entry_value = Column(Float)
    exit_value = Column(Float)
    risk_amount = Column(Float)
    risk_pct = Column(Float)
    cost_amount = Column(Float)
    run = relationship("BacktestRun", back_populates="trades")

class BacktestEquityCurve(Base):
    __tablename__ = 'backtest_equity_curve'
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('backtest_runs.id'))
    date = Column(String)
    cash = Column(Float)
    positions_value = Column(Float)
    equity = Column(Float)
    drawdown_value = Column(Float)
    drawdown_pct = Column(Float)
    open_positions = Column(Integer)
    daily_return = Column(Float)
    benchmark_daily_return = Column(Float, default=0.0)
    spy_daily_return = Column(Float, default=0.0)
    qqq_daily_return = Column(Float, default=0.0)
    run = relationship("BacktestRun", back_populates="equity_points")

class BacktestRejectedTrade(Base):
    __tablename__ = 'backtest_rejected_trades'
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('backtest_runs.id'))
    signal_id = Column(String)
    signal_date = Column(String)
    ticker = Column(String)
    action = Column(String)
    reason = Column(String)
    final_score = Column(Float)
    run = relationship("BacktestRun", back_populates="rejected")

def _add_column_if_missing(engine, table_name, column_name, column_sql):
    with engine.begin() as conn:
        existing = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()]
        if column_name not in existing:
            conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

def _migrate_sqlite_schema(engine):
    if not config.DATABASE_URL.startswith("sqlite"):
        return

    run_columns = {
        "initial_capital": "REAL DEFAULT 10000.0",
        "final_equity": "REAL DEFAULT 0.0",
        "total_return": "REAL DEFAULT 0.0",
        "cagr": "REAL DEFAULT 0.0",
        "sharpe": "REAL DEFAULT 0.0",
        "sortino": "REAL DEFAULT 0.0",
        "calmar": "REAL DEFAULT 0.0",
        "generated_signals": "INTEGER DEFAULT 0",
        "rejected_trades": "INTEGER DEFAULT 0",
        "max_drawdown_value": "REAL DEFAULT 0.0",
        "benchmark_return": "REAL DEFAULT 0.0",
        "alpha_vs_spy": "REAL DEFAULT 0.0",
        "avg_holding_days": "REAL DEFAULT 0.0",
        "max_concurrent_positions": "INTEGER DEFAULT 0",
        "max_positions_total": "INTEGER DEFAULT 5",
        "max_position_pct": "REAL DEFAULT 0.2",
        "spread_slippage_pct": "REAL DEFAULT 0.0",
        "currency_conversion_pct": "REAL DEFAULT 0.0",
        "bankrupt": "BOOLEAN DEFAULT 0",
        "strategy_name": "TEXT DEFAULT 'SIGNAL_ENGINE'",
        "strategy_version": "TEXT DEFAULT '1.0'",
        "strategy_engine": "TEXT DEFAULT 'SIGNAL_ENGINE'",
        "benchmark_ticker": "TEXT DEFAULT 'SPY'",
        "min_score": "REAL DEFAULT 0.75",
        "allowed_risk_ratings": "TEXT DEFAULT 'LOW,MEDIUM,HIGH'",
        "max_total_exposure": "REAL DEFAULT 0.30",
        "use_adjusted_data": "BOOLEAN DEFAULT 0",
        "rebalance_frequency": "TEXT DEFAULT 'weekly'",
        "segment_name": "TEXT DEFAULT 'full'",
        "overfit_risk": "BOOLEAN DEFAULT 0",
        "qqq_return": "REAL DEFAULT 0.0",
        "spy_sma200_return": "REAL DEFAULT 0.0",
    }
    trade_columns = {
        "holding_days": "INTEGER",
        "position_size": "REAL",
        "entry_value": "REAL",
        "exit_value": "REAL",
        "risk_amount": "REAL",
        "risk_pct": "REAL",
        "cost_amount": "REAL",
    }
    equity_columns = {
        "benchmark_daily_return": "REAL DEFAULT 0.0",
        "spy_daily_return": "REAL DEFAULT 0.0",
        "qqq_daily_return": "REAL DEFAULT 0.0",
    }

    for column_name, column_sql in run_columns.items():
        _add_column_if_missing(engine, "backtest_runs", column_name, column_sql)
    for column_name, column_sql in trade_columns.items():
        _add_column_if_missing(engine, "backtest_trades", column_name, column_sql)
    for column_name, column_sql in equity_columns.items():
        _add_column_if_missing(engine, "backtest_equity_curve", column_name, column_sql)

def init_db():
    from sqlalchemy import create_engine
    engine = create_engine(config.DATABASE_URL)
    Base.metadata.create_all(engine)
    _migrate_sqlite_schema(engine)
    return engine

def get_session():
    from sqlalchemy import create_engine
    engine = create_engine(config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()
