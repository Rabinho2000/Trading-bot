import pandas as pd
import numpy as np
from strategy.indicators import calculate_indicators

def test_indicators_calculation():
    # Create dummy data
    dates = pd.date_range(start="2020-01-01", periods=300)
    data = {
        'Open': np.random.randn(300).cumsum() + 100,
        'High': np.random.randn(300).cumsum() + 105,
        'Low': np.random.randn(300).cumsum() + 95,
        'Close': np.random.randn(300).cumsum() + 100,
        'Volume': np.random.randint(1000, 10000, size=300)
    }
    df = pd.DataFrame(data, index=dates)
    
    result = calculate_indicators(df)
    
    assert 'SMA_20' in result.columns
    assert 'SMA_200' in result.columns
    assert 'RSI_14' in result.columns
    assert 'ATR_14' in result.columns
    assert not result['SMA_200'].isnull().all()
    print("Indicators test passed!")

if __name__ == "__main__":
    test_indicators_calculation()
