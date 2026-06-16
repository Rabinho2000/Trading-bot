import config

def validate_signal_risk(signal, portfolio_value=10000):
    """
    Calculate position sizing and validate risk.
    """
    ticker = signal['ticker']
    curr_price = (signal['entry_zone']['min'] + signal['entry_zone']['max']) / 2
    invalidation = signal['invalidation']
    
    # Risk amount (1% of portfolio)
    risk_amount = portfolio_value * config.MAX_RISK_PER_TRADE
    
    # Risk per share
    risk_per_share = abs(curr_price - invalidation)
    
    if risk_per_share == 0:
        return False, "Invalidation level matches entry price."
    
    # Suggested shares
    suggested_shares = risk_amount / risk_per_share
    
    # Exposure limit (5% of portfolio)
    max_exposure = portfolio_value * config.MAX_EXPOSURE_PER_TICKER
    actual_exposure = suggested_shares * curr_price
    
    if actual_exposure > max_exposure:
        suggested_shares = max_exposure / curr_price
        actual_exposure = max_exposure
        
    signal['suggested_shares'] = round(suggested_shares, 2)
    signal['exposure'] = round(actual_exposure, 2)
    signal['exposure_pct'] = round((actual_exposure / portfolio_value) * 100, 2)
    
    # Final checks
    if signal['risk_rating'] == "HIGH" and signal['action'] == "BUY":
        signal['action'] = "WATCH"
        signal['reason'] += " (Downgraded to WATCH due to high risk rating)"
        
    return True, "Risk validated"
