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

def init_db():
    from sqlalchemy import create_engine
    engine = create_engine(config.DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine

def get_session():
    from sqlalchemy import create_engine
    engine = create_engine(config.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()
