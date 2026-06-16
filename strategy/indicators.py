import pandas as pd
import numpy as np

def calculate_sma(df, window):
    return df['Close'].rolling(window=window).mean()

def calculate_rsi(df, window=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, window=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=window).mean()

def calculate_performance(df, days):
    return (df['Close'] / df['Close'].shift(days) - 1) * 100

def calculate_indicators(df):
    df = df.copy()
    df['SMA_20'] = calculate_sma(df, 20)
    df['SMA_50'] = calculate_sma(df, 50)
    df['SMA_200'] = calculate_sma(df, 200)
    df['RSI_14'] = calculate_rsi(df, 14)
    df['ATR_14'] = calculate_atr(df, 14)
    df['Volume_Avg_20'] = df['Volume'].rolling(window=20).mean()
    
    # Approx 1M = 21 trading days, 3M = 63, 6M = 126
    df['Perf_1M'] = calculate_performance(df, 21)
    df['Perf_3M'] = calculate_performance(df, 63)
    df['Perf_6M'] = calculate_performance(df, 126)
    
    df['High_52W'] = df['High'].rolling(window=252).max()
    df['Dist_52W_High'] = (df['Close'] / df['High_52W'] - 1) * 100
    
    # Volatility (standard deviation of daily returns)
    df['Returns'] = df['Close'].pct_change()
    df['Vol_20D'] = df['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
    
    return df
