import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Union

# Configuration
GAIN_THRESHOLDS = [0.02, 0.04, 0.06, 0.10]
STOP_LOSS_THRESHOLDS = [-0.02, -0.04, -0.08, -0.10, -0.20]
TIME_FORMAT = '%I:%M %p'

def _find_milestone_time(data: pd.DataFrame, target_price: float, comparison: str) -> str:
    """Find first timestamp when a price milestone is hit."""
    if comparison == "high":
        hit_rows = data[data['High'] >= target_price]
    elif comparison == "low":
        hit_rows = data[data['Low'] <= target_price]
    else:
        raise ValueError(f"Invalid comparison: {comparison}")
    
    if not hit_rows.empty:
        return hit_rows.index[0].strftime(TIME_FORMAT)
    return "Not Hit"

def get_stock_milestones(ticker_symbol: str) -> Union[Dict, str]:
    """
    Fetch stock price milestones (gains and stop losses) for the previous trading day.
    
    Args:
        ticker_symbol: Stock ticker symbol (e.g., 'AAPL')
    
    Returns:
        Dictionary with milestone timestamps or error message
    """
    try:
        # Fetch 2 days of 1-minute data to ensure we capture all of yesterday
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period="2d", interval="1m")
        
        if data.empty:
            return f"No data found for {ticker_symbol}"
        
        # Filter for the most recent trading day
        yesterday_data = data[data.index.date == data.index.date[-1]]
        
        if yesterday_data.empty:
            return f"No data found for {ticker_symbol}"
        
        # Extract key prices
        open_price = yesterday_data['Open'].iloc[0]
        close_price = yesterday_data['Close'].iloc[-1]
        
        results = {
            "Ticker": ticker_symbol,
            "Market Price (Close)": round(close_price, 2),
            "Open Price": round(open_price, 2)
        }
        
        # Find gain milestones
        for threshold in GAIN_THRESHOLDS:
            target_price = open_price * (1 + threshold)
            hit_time = _find_milestone_time(yesterday_data, target_price, "high")
            results[f"+{int(threshold*100)}% Gain Time"] = hit_time
        
        # Find stop loss milestones
        for threshold in STOP_LOSS_THRESHOLDS:
            target_price = open_price * (1 + threshold)
            hit_time = _find_milestone_time(yesterday_data, target_price, "low")
            results[f"{int(threshold*100)}% Stop Loss Time"] = hit_time
        
        return results
    
    except Exception as e:
        return f"Error fetching data for {ticker_symbol}: {str(e)}"

# Example Usage
tickers = ["VERO", "ASBP", "HUBC"]
for symbol in tickers:
    print(get_stock_milestones(symbol))