import pandas as pd
from .indicators import calculate_indicators

def classify_market_regime(watchlist_data):
    """
    Classify market regime based on SPY, QQQ and breadth.
    Outputs: RISK_ON, RISK_OFF, NEUTRAL, HIGH_VOLATILITY
    """
    spy = watchlist_data.get('SPY')
    qqq = watchlist_data.get('QQQ')
    
    if spy is None or qqq is None:
        return "NEUTRAL"
    
    spy_last = spy.iloc[-1]
    qqq_last = qqq.iloc[-1]
    
    # Breadth: % of watchlist above SMA 50
    above_50 = 0
    total = 0
    for ticker, df in watchlist_data.items():
        if df is not None and not df.empty:
            total += 1
            if df['Close'].iloc[-1] > df['SMA_50'].iloc[-1]:
                above_50 += 1
    
    breadth = above_50 / total if total > 0 else 0.5
    
    # Conditions
    spy_above_200 = spy_last['Close'] > spy_last['SMA_200']
    qqq_above_200 = qqq_last['Close'] > qqq_last['SMA_200']
    
    # Volatility check (using SPY)
    spy_vol = spy_last['Vol_20D']
    
    if spy_vol > 25: # Arbitrary high vol threshold
        return "HIGH_VOLATILITY"
    
    if spy_above_200 and qqq_above_200 and breadth > 0.6:
        return "RISK_ON"
    
    if not spy_above_200 or breadth < 0.3:
        return "RISK_OFF"
    
    return "NEUTRAL"
