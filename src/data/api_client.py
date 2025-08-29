from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import os


class APIClient(ABC):
    """Abstract base class for stock data API clients."""
    
    @abstractmethod
    def get_historical_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """Get historical price data for a ticker."""
        pass
    
    @abstractmethod
    def get_current_price(self, ticker: str) -> float:
        """Get current price for a ticker."""
        pass


class AlphaVantageClient(APIClient):
    """Alpha Vantage API client with rate limiting."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.last_call_time = 0
        self.min_call_interval = 12  # 5 calls/minute = 12 seconds between calls
    
    def _rate_limit(self) -> None:
        """Ensure we don't exceed API rate limits."""
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_call_interval:
            time.sleep(self.min_call_interval - elapsed)
        self.last_call_time = time.time()
    
    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make rate-limited API request."""
        self._rate_limit()
        params["apikey"] = self.api_key
        
        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if "Error Message" in data:
            raise ValueError(f"API Error: {data['Error Message']}")
        if "Note" in data:
            raise ValueError(f"API Rate Limit: {data['Note']}")
            
        return data
    
    def get_historical_data(self, ticker: str, period: str = "1y") -> pd.DataFrame:
        """Get historical daily data from Alpha Vantage."""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": ticker,
            "outputsize": "full"
        }
        
        data = self._make_request(params)
        
        if "Time Series (Daily)" not in data:
            raise ValueError(f"No data found for ticker {ticker}")
        
        time_series = data["Time Series (Daily)"]
        
        # Convert to DataFrame
        df_data = []
        for date_str, values in time_series.items():
            df_data.append({
                "date": datetime.strptime(date_str, "%Y-%m-%d").date(),
                "open": float(values["1. open"]),
                "high": float(values["2. high"]),
                "low": float(values["3. low"]),
                "close": float(values["4. close"]),
                "volume": int(values["6. volume"]),
                "adjusted_close": float(values["5. adjusted close"])
            })
        
        df = pd.DataFrame(df_data)
        df = df.sort_values("date")
        
        # Filter by period if needed
        if period == "1y":
            cutoff_date = datetime.now().date() - timedelta(days=365)
            df = df[df["date"] >= cutoff_date]
        
        return df.reset_index(drop=True)
    
    def get_current_price(self, ticker: str) -> float:
        """Get current price using global quote endpoint."""
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": ticker
        }
        
        data = self._make_request(params)
        
        if "Global Quote" not in data:
            raise ValueError(f"No current price data for ticker {ticker}")
        
        quote = data["Global Quote"]
        return float(quote["05. price"])


def create_api_client(api_type: str = "alpha_vantage", **kwargs) -> APIClient:
    """Factory function to create API clients."""
    if api_type == "alpha_vantage":
        api_key = kwargs.get("api_key") or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            raise ValueError("Alpha Vantage API key required")
        return AlphaVantageClient(api_key)
    else:
        raise ValueError(f"Unsupported API type: {api_type}")