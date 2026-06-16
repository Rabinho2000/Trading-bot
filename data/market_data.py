import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def fetch_data(ticker, period="2y"):
    """Fetch historical data from yfinance"""
    try:
        data = yf.download(ticker, period=period, progress=False)
        if data.empty:
            return None
        
        # Flatten MultiIndex columns if necessary
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        return data
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None

def get_latest_price(ticker):
    """Get the most recent close price"""
    df = fetch_data(ticker, period="5d")
    if df is not None and not df.empty:
        # Drop rows where Close is NaN
        closes = df['Close'].dropna()
        if not closes.empty:
            val = closes.iloc[-1]
            # Ensure it's a scalar (sometimes returns a Series with one element)
            if isinstance(val, pd.Series):
                return float(val.iloc[0])
            return float(val)
    return None
