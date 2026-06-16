import sys
import argparse
from db.database import init_db, get_session, Run, Signal, SignalReview, PositionSimulated
from data.market_data import fetch_data, get_latest_price
from strategy.indicators import calculate_indicators
from strategy.regime import classify_market_regime
from strategy.signal_engine import generate_signal
from strategy.backtester import run_backtest
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
    parser.add_argument("command", choices=["run", "signals", "evaluate", "telegram-test", "backtest"])
    parser.add_argument("--start", help="Backtest start date, YYYY-MM-DD")
    parser.add_argument("--end", help="Backtest end date, YYYY-MM-DD")
    parser.add_argument("--max-holding-days", type=int, default=30, help="Maximum holding period for backtests")
    parser.add_argument("--initial-capital", type=float, default=10000.0, help="Initial backtest capital")
    parser.add_argument("--max-positions-total", type=int, default=5, help="Maximum concurrent backtest positions")
    parser.add_argument("--max-position-pct", type=float, default=0.20, help="Maximum capital fraction per position")
    parser.add_argument("--spread-slippage-pct", type=float, default=0.001, help="Per-side spread/slippage fraction")
    parser.add_argument("--currency-conversion-pct", type=float, default=0.0, help="Per-side currency conversion fraction")
    
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
    elif args.command == "backtest":
        if not args.start or not args.end:
            parser.error("backtest requires --start and --end")

        result = run_backtest(
            args.start,
            args.end,
            max_holding_days=args.max_holding_days,
            initial_capital=args.initial_capital,
            max_positions_total=args.max_positions_total,
            max_position_pct=args.max_position_pct,
            spread_slippage_pct=args.spread_slippage_pct,
            currency_conversion_pct=args.currency_conversion_pct,
        )
        metrics = result.metrics
        print(f"Backtest run #{result.run_id} saved.")
        print(f"Signals generated: {metrics['generated_signals']}")
        print(f"Trades closed: {metrics['total_trades']}")
        print(f"Rejected trades: {metrics['rejected_trades']}")
        print(f"Final equity: {metrics['final_equity']:.2f}")
        print(f"Strategy return: {metrics['total_return']:.2f}%")
        print(f"CAGR: {metrics['cagr']:.2f}%")
        print(f"Sharpe: {metrics['sharpe']:.2f}")
        print(f"Sortino: {metrics['sortino']:.2f}")
        print(f"Calmar: {metrics['calmar']:.2f}")
        print(f"Win rate: {metrics['win_rate']:.2f}%")
        print(f"Average return: {metrics['average_return']:.2f}%")
        print(f"Profit factor: {metrics['profit_factor']:.2f}")
        print(f"Max drawdown: {metrics['max_drawdown']:.2f}% ({metrics['max_drawdown_value']:.2f})")
        print(f"Return vs SPY: {metrics['total_return']:.2f}% vs {metrics['spy_return']:.2f}%")
        if metrics["bankrupt"]:
            print("ALERT: strategy bankrupt")
        if result.failed_tickers:
            print("Tickers skipped:")
            for ticker, reason in result.failed_tickers.items():
                print(f"- {ticker}: {reason}")

if __name__ == "__main__":
    main()
