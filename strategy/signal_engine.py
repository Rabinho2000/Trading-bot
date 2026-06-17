import hashlib
from datetime import datetime
from .scoring import calculate_technical_score, calculate_final_score

def generate_signal(ticker, df, regime, as_of_date=None, strategy_name="SIGNAL_ENGINE", strategy_version="1.0"):
    if df is None or df.empty:
        return None
    
    if as_of_date is not None:
        scoped_df = df.loc[:as_of_date]
        if scoped_df.empty:
            return None
    else:
        scoped_df = df

    last_row = scoped_df.iloc[-1]
    if as_of_date is not None:
        date_str = last_row.name.strftime("%Y-%m-%d")
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    tech_score = calculate_technical_score(last_row)
    final_score, regime_score = calculate_final_score(tech_score, regime)
    
    # Decision logic
    action = "SKIP"
    reason = ""
    
    if regime == "RISK_OFF":
        action = "SKIP"
        reason = "Market regime is RISK_OFF. Preserving capital."
    elif final_score >= 0.75:
        action = "BUY"
        reason = "Strong technical setup and favorable regime."
    elif final_score >= 0.6:
        action = "WATCH"
        reason = "Promising setup, but needs more confirmation."
    elif last_row['Close'] < last_row['SMA_200']:
        action = "SKIP"
        reason = "Price below SMA 200. Trend is bearish."
    else:
        action = "SKIP"
        reason = "Weak technical setup or unfavorable conditions."

    # Entry and Targets (Simple logic for MVP)
    curr_price = last_row['Close']
    atr = last_row['ATR_14']
    
    entry_min = curr_price * 0.99
    entry_max = curr_price * 1.01
    invalidation = curr_price - (2 * atr)
    target_1 = curr_price + (2 * atr)
    target_2 = curr_price + (4 * atr)
    
    risk_rating = "LOW"
    if last_row['Vol_20D'] > 30:
        risk_rating = "HIGH"
    elif last_row['Vol_20D'] > 15:
        risk_rating = "MEDIUM"

    # Deterministic ID based on stable signal identity, not the score.
    signal_id = hashlib.md5(f"{strategy_name}_{strategy_version}_{date_str}_{ticker}_{action}".encode()).hexdigest()[:12]

    return {
        "signal_id": signal_id,
        "date": date_str,
        "ticker": ticker,
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "action": action,
        "entry_zone": {"min": round(entry_min, 2), "max": round(entry_max, 2)},
        "invalidation": round(invalidation, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "risk_rating": risk_rating,
        "time_horizon": "2-6 weeks",
        "technical_score": round(tech_score, 2),
        "regime_score": round(regime_score, 2),
        "final_score": round(final_score, 2),
        "reason": reason
    }
