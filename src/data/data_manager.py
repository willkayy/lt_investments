import pandas as pd
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

from .api_client import APIClient, create_api_client

logger = logging.getLogger(__name__)


class DataManager:
    """Manages CSV storage and retrieval of stock price data."""
    
    def __init__(self, data_dir: str = "data", api_client: Optional[APIClient] = None):
        self.data_dir = Path(data_dir)
        self.prices_dir = self.data_dir / "prices"
        self.scores_dir = self.data_dir / "scores"
        self.backtests_dir = self.data_dir / "backtests"
        
        # Create directories if they don't exist
        for dir_path in [self.prices_dir, self.scores_dir, self.backtests_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        self.api_client = api_client
    
    def _get_price_file_path(self, ticker: str, market: str) -> Path:
        """Get the file path for a ticker's price data."""
        return self.prices_dir / f"{ticker}_{market}.csv"
    
    def _get_scores_file_path(self, ticker: str, market: str) -> Path:
        """Get the file path for a ticker's scores data."""
        return self.scores_dir / f"{ticker}_{market}_scores.csv"
    
    def load_price_data(self, ticker: str, market: str) -> Optional[pd.DataFrame]:
        """Load price data from CSV file."""
        file_path = self._get_price_file_path(ticker, market)
        
        if not file_path.exists():
            logger.warning(f"No price data file found for {ticker} in {market}")
            return None
        
        try:
            df = pd.read_csv(file_path, parse_dates=["date"])
            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df.sort_values("date")
        except Exception as e:
            logger.error(f"Error loading price data for {ticker}: {e}")
            return None
    
    def save_price_data(self, ticker: str, market: str, df: pd.DataFrame) -> bool:
        """Save price data to CSV file."""
        file_path = self._get_price_file_path(ticker, market)
        
        try:
            # Ensure consistent column order and format
            required_columns = ["date", "open", "high", "low", "close", "volume", "adjusted_close"]
            df = df[required_columns].copy()
            df = df.sort_values("date")
            
            df.to_csv(file_path, index=False, date_format="%Y-%m-%d")
            logger.info(f"Saved price data for {ticker} ({len(df)} records)")
            return True
        except Exception as e:
            logger.error(f"Error saving price data for {ticker}: {e}")
            return False
    
    def update_price_data(self, ticker: str, market: str, force_refresh: bool = False) -> bool:
        """Update price data from API if needed."""
        if not self.api_client:
            logger.error("No API client configured")
            return False
        
        file_path = self._get_price_file_path(ticker, market)
        
        # Check if we need to update
        if not force_refresh and file_path.exists():
            # Check if data is recent (less than 1 day old)
            mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if (datetime.now() - mod_time).days < 1:
                logger.info(f"Price data for {ticker} is recent, skipping update")
                return True
        
        try:
            logger.info(f"Fetching price data for {ticker} from API...")
            df = self.api_client.get_historical_data(ticker, period="1y")
            
            if df is not None and len(df) > 0:
                return self.save_price_data(ticker, market, df)
            else:
                logger.warning(f"No data received for {ticker}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating price data for {ticker}: {e}")
            return False
    
    def get_latest_price_data(self, ticker: str, market: str, days: int = 90) -> Optional[pd.DataFrame]:
        """Get the most recent N days of price data."""
        df = self.load_price_data(ticker, market)
        
        if df is None or len(df) == 0:
            return None
        
        # Get the last N days
        return df.tail(days).copy()
    
    def save_scores_data(self, ticker: str, market: str, scores_df: pd.DataFrame) -> bool:
        """Save scoring data to CSV file."""
        file_path = self._get_scores_file_path(ticker, market)
        
        try:
            scores_df = scores_df.sort_values("date")
            scores_df.to_csv(file_path, index=False, date_format="%Y-%m-%d")
            logger.info(f"Saved scores data for {ticker}")
            return True
        except Exception as e:
            logger.error(f"Error saving scores data for {ticker}: {e}")
            return False
    
    def load_scores_data(self, ticker: str, market: str) -> Optional[pd.DataFrame]:
        """Load scores data from CSV file."""
        file_path = self._get_scores_file_path(ticker, market)
        
        if not file_path.exists():
            return None
        
        try:
            df = pd.read_csv(file_path, parse_dates=["date"])
            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df.sort_values("date")
        except Exception as e:
            logger.error(f"Error loading scores data for {ticker}: {e}")
            return None
    
    def save_backtest_results(self, results_df: pd.DataFrame, test_name: str = None) -> str:
        """Save backtest results and return the filename."""
        if test_name is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            test_name = f"backtest_{timestamp}"
        
        file_path = self.backtests_dir / f"{test_name}.csv"
        
        try:
            results_df.to_csv(file_path, index=False)
            logger.info(f"Saved backtest results to {file_path}")
            return str(file_path)
        except Exception as e:
            logger.error(f"Error saving backtest results: {e}")
            return ""
    
    def get_available_tickers(self) -> Dict[str, List[str]]:
        """Get list of available tickers by market."""
        tickers_by_market = {}
        
        for file_path in self.prices_dir.glob("*.csv"):
            if file_path.name.endswith("_scores.csv"):
                continue
                
            # Parse ticker_market.csv format
            name_parts = file_path.stem.split("_")
            if len(name_parts) >= 2:
                ticker = "_".join(name_parts[:-1])  # Handle tickers with underscores
                market = name_parts[-1]
                
                if market not in tickers_by_market:
                    tickers_by_market[market] = []
                tickers_by_market[market].append(ticker)
        
        return tickers_by_market
    
    def bulk_update_data(self, tickers_config: Dict[str, Dict[str, List[str]]], force_refresh: bool = False) -> Dict[str, bool]:
        """Update price data for multiple tickers."""
        results = {}
        
        for market, ticker_types in tickers_config.items():
            for ticker_type, ticker_list in ticker_types.items():
                for ticker in ticker_list:
                    logger.info(f"Updating {ticker} ({market})")
                    success = self.update_price_data(ticker, market, force_refresh)
                    results[f"{ticker}_{market}"] = success
        
        return results