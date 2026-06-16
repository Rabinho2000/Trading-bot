from risk.risk_manager import validate_signal_risk

def test_risk_validation():
    signal = {
        'ticker': 'AAPL',
        'entry_zone': {'min': 190, 'max': 210},
        'invalidation': 180,
        'action': 'BUY',
        'risk_rating': 'LOW',
        'final_score': 0.8
    }
    
    valid, msg = validate_signal_risk(signal, portfolio_value=10000)
    
    assert valid is True
    assert 'suggested_shares' in signal
    assert signal['exposure'] <= 500  # 5% of 10000
    print("Risk manager test passed!")

if __name__ == "__main__":
    test_risk_validation()
