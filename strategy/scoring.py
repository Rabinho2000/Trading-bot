def calculate_technical_score(row):
    """
    Returns a score between 0 and 1.
    Criteria:
    - Price > SMA 200
    - SMA 20 > SMA 50
    - RSI between 45 and 70
    - Momentum 3M positive
    - Volume > Avg 20D
    """
    score = 0.0
    weights = {
        'trend_200': 0.3,
        'trend_cross': 0.2,
        'rsi': 0.15,
        'momentum': 0.2,
        'volume': 0.15
    }
    
    if row['Close'] > row['SMA_200']:
        score += weights['trend_200']
        
    if row['SMA_20'] > row['SMA_50']:
        score += weights['trend_cross']
        
    if 45 <= row['RSI_14'] <= 70:
        score += weights['rsi']
    elif 40 <= row['RSI_14'] <= 75:
        score += weights['rsi'] * 0.5
        
    if row['Perf_3M'] > 0:
        score += weights['momentum']
        
    if row['Volume'] > row['Volume_Avg_20']:
        score += weights['volume']
        
    return score

def calculate_final_score(tech_score, regime):
    regime_multiplier = {
        'RISK_ON': 1.2,
        'NEUTRAL': 1.0,
        'RISK_OFF': 0.5,
        'HIGH_VOLATILITY': 0.7
    }
    
    regime_score = regime_multiplier.get(regime, 1.0)
    final = tech_score * regime_score
    return min(final, 1.0), regime_score
