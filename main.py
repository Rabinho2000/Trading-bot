import sys
import argparse
from db.database import init_db, get_session, Run, Signal, SignalReview, PositionSimulated
from data.market_data import fetch_data, get_latest_price
from strategy.indicators import calculate_indicators
from strategy.regime import classify_market_regime
from strategy.signal_engine import generate_signal
from risk.risk_manager import validate_signal_risk
from ai.analyst import get_ai_analysis
from alerts.telegram import send_telegram_message, format_daily_summary
import config

def run_analysis():
    print("Starting Market Analysis...")
    engine = init_db()
    session = get_session()
    
    watchlist_data = {}
    for ticker in config.DEFAULT_WATCHLIST:
        print(f"Fetching data for {ticker}...")
        df = fetch_data(ticker)
        if df is not None:
            df = calculate_indicators(df)
            watchlist_data[ticker] = df
            
    regime = classify_market_regime(watchlist_data)
    print(f"Market Regime: {regime}")
    
    # Save Run
    new_run = Run(market_regime=regime)
    session.add(new_run)
    session.commit()
    
    signals_generated = []
    for ticker, df in watchlist_data.items():
        signal = generate_signal(ticker, df, regime)
        if signal:
            valid, risk_msg = validate_signal_risk(signal)
            if valid:
                signals_generated.append(signal)
                
                # AI Analysis
                print(f"Analyzing {ticker} with AI...")
                analysis = get_ai_analysis(signal)
                
                # Save Signal
                # Check if signal already exists in this run or globally to avoid IntegrityError
                existing_signal = session.query(Signal).filter(Signal.id == signal['signal_id']).first()
                if existing_signal:
                    print(f"Signal {signal['signal_id']} for {ticker} already exists. Skipping.")
                    continue

                def clean_float(val):
                    import math
                    if val is None or (isinstance(val, float) and math.isnan(val)):
                        return 0.0
                    return val

                db_signal = Signal(
                    id=signal['signal_id'],
                    run_id=new_run.id,
                    date=signal['date'],
                    ticker=signal['ticker'],
                    action=signal['action'],
                    entry_min=clean_float(signal['entry_zone']['min']),
                    entry_max=clean_float(signal['entry_zone']['max']),
                    invalidation=clean_float(signal['invalidation']),
                    target_1=clean_float(signal['target_1']),
                    target_2=clean_float(signal['target_2']),
                    risk_rating=signal['risk_rating'],
                    technical_score=clean_float(signal['technical_score']),
                    regime_score=clean_float(signal['regime_score']),
                    final_score=clean_float(signal['final_score']),
                    reason=signal['reason']
                )
                session.add(db_signal)
                
                # Auto-create simulated position for BUY signals (Hypothetical €100)
                if signal['action'] == "BUY":
                    entry_price = (signal['entry_zone']['min'] + signal['entry_zone']['max']) / 2
                    pos = PositionSimulated(
                        ticker=signal['ticker'],
                        entry_date=signal['date'],
                        entry_price=entry_price,
                        size=100.0 / entry_price, # Shares for €100
                        status="OPEN"
                    )
                    session.add(pos)
                
                db_review = SignalReview(
                    signal_id=signal['signal_id'],
                    summary=analysis['summary'],
                    bullish_thesis=analysis['bullish_thesis'],
                    bearish_thesis=analysis['bearish_thesis'],
                    risks=analysis['risks'],
                    confidence_score=analysis['confidence_score']
                )
                session.add(db_review)
                
    session.commit()
    print(f"Generated {len(signals_generated)} signals.")
    
    # Telegram Alert
    summary = format_daily_summary(regime, signals_generated)
    send_telegram_message(summary)
    
    session.close()

def evaluate_positions():
    print("Evaluating open positions...")
    session = get_session()
    open_positions = session.query(PositionSimulated).filter(PositionSimulated.status == "OPEN").all()
    
    if not open_positions:
        print("No open positions to evaluate.")
        session.close()
        return

    report_lines = ["*Performance de Sinais (Base 100€):*"]
    
    for pos in open_positions:
        current_price = get_latest_price(pos.ticker)
        if current_price:
            pnl_pct = (current_price / pos.entry_price - 1) * 100
            pnl_val = (pos.size * current_price) - 100.0
            
            status_emoji = "✅" if pnl_val >= 0 else "❌"
            report_lines.append(
                f"{status_emoji} *{pos.ticker}*: {pnl_pct:+.2f}% ({pnl_val:+.2f}€)"
            )
            
    message = "\n".join(report_lines)
    print(message)
    send_telegram_message(message)
    session.close()

def list_signals():
    session = get_session()
    signals = session.query(Signal).order_by(Signal.date.desc()).all()
    for s in signals:
        print(f"{s.date} | {s.ticker} | {s.action} | Score: {s.final_score}")
    session.close()

def main():
    parser = argparse.ArgumentParser(description="t212-signal-lab CLI")
    parser.add_argument("command", choices=["run", "signals", "evaluate", "telegram-test"])
    
    args = parser.parse_args()
    
    if args.command == "run":
        run_analysis()
    elif args.command == "signals":
        list_signals()
    elif args.command == "evaluate":
        evaluate_positions()
    elif args.command == "telegram-test":
        send_telegram_message("Test message from t212-signal-lab")
        print("Test message sent.")

if __name__ == "__main__":
    main()
