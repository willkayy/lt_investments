import pytest
import pandas as pd
import tempfile
import shutil
from pathlib import Path
from datetime import date, datetime
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.data.data_manager import DataManager


class TestDataManager:
    """Test cases for the DataManager class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def data_manager(self, temp_dir):
        """DataManager instance with temporary directory."""
        return DataManager(data_dir=temp_dir)
    
    @pytest.fixture
    def sample_price_data(self):
        """Sample price data for testing."""
        return pd.DataFrame({
            "date": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)],
            "open": [100.0, 101.0, 102.0],
            "high": [105.0, 106.0, 107.0],
            "low": [95.0, 96.0, 97.0],
            "close": [102.0, 103.0, 104.0],
            "volume": [1000000, 1100000, 1200000],
            "adjusted_close": [102.0, 103.0, 104.0]
        })
    
    def test_initialization(self, temp_dir):
        """Test DataManager initialization creates directories."""
        dm = DataManager(data_dir=temp_dir)
        
        # Check directories are created
        assert dm.prices_dir.exists()
        assert dm.scores_dir.exists()
        assert dm.backtests_dir.exists()
        
        assert dm.data_dir == Path(temp_dir)
    
    def test_save_and_load_price_data(self, data_manager, sample_price_data):
        """Test saving and loading price data."""
        ticker = "AAPL"
        market = "US"
        
        # Save data
        success = data_manager.save_price_data(ticker, market, sample_price_data)
        assert success
        
        # Load data
        loaded_data = data_manager.load_price_data(ticker, market)
        
        assert loaded_data is not None
        assert len(loaded_data) == 3
        assert list(loaded_data.columns) == ["date", "open", "high", "low", "close", "volume", "adjusted_close"]
        
        # Check data values
        assert loaded_data.iloc[0]["close"] == 102.0
        assert loaded_data.iloc[-1]["close"] == 104.0
    
    def test_load_nonexistent_price_data(self, data_manager):
        """Test loading data for non-existent ticker."""
        result = data_manager.load_price_data("NONEXISTENT", "US")
        assert result is None
    
    def test_get_price_file_path(self, data_manager):
        """Test price file path generation."""
        path = data_manager._get_price_file_path("AAPL", "US")
        expected = data_manager.prices_dir / "AAPL_US.csv"
        assert path == expected
        
        # Test with Australian ticker
        path = data_manager._get_price_file_path("CBA.AX", "AU")
        expected = data_manager.prices_dir / "CBA.AX_AU.csv"
        assert path == expected
    
    def test_get_latest_price_data(self, data_manager, sample_price_data):
        """Test getting latest N days of data."""
        ticker = "AAPL"
        market = "US"
        
        # Add more data points
        extended_data = sample_price_data.copy()
        for i in range(4, 100):  # Add more days
            extended_data = pd.concat([extended_data, pd.DataFrame({
                "date": [date(2024, 1, i)],
                "open": [100.0 + i],
                "high": [105.0 + i],
                "low": [95.0 + i],
                "close": [102.0 + i],
                "volume": [1000000],
                "adjusted_close": [102.0 + i]
            })], ignore_index=True)
        
        data_manager.save_price_data(ticker, market, extended_data)
        
        # Get latest 10 days
        latest_data = data_manager.get_latest_price_data(ticker, market, days=10)
        
        assert latest_data is not None
        assert len(latest_data) == 10
        
        # Should be the most recent data
        assert latest_data.iloc[-1]["close"] == 102.0 + 99  # Last day
    
    def test_save_and_load_scores_data(self, data_manager):
        """Test saving and loading scores data."""
        ticker = "AAPL"
        market = "US"
        
        scores_data = pd.DataFrame({
            "date": [date(2024, 1, 1), date(2024, 1, 2)],
            "price_position": [0.8, 0.7],
            "momentum_decay": [0.6, 0.5],
            "volatility_adj": [0.9, 0.8],
            "volume_conf": [0.7, 0.6],
            "final_score": [0.75, 0.65],
            "allocation_pct": [12.5, 10.5]
        })
        
        # Save scores
        success = data_manager.save_scores_data(ticker, market, scores_data)
        assert success
        
        # Load scores
        loaded_scores = data_manager.load_scores_data(ticker, market)
        
        assert loaded_scores is not None
        assert len(loaded_scores) == 2
        assert loaded_scores.iloc[0]["final_score"] == 0.75
    
    def test_save_backtest_results(self, data_manager):
        """Test saving backtest results."""
        results_data = pd.DataFrame({
            "test_date": [date(2024, 1, 1), date(2024, 1, 2)],
            "ticker": ["AAPL", "GOOGL"],
            "market": ["US", "US"],
            "score": [0.8, 0.7],
            "allocation": [500.0, 400.0],
            "price": [150.0, 2800.0]
        })
        
        filename = data_manager.save_backtest_results(results_data, "test_backtest")
        
        assert filename != ""
        assert "test_backtest.csv" in filename
        
        # Check file exists
        filepath = Path(filename)
        assert filepath.exists()
    
    def test_get_available_tickers(self, data_manager, sample_price_data):
        """Test getting list of available tickers."""
        # Save data for multiple tickers
        data_manager.save_price_data("AAPL", "US", sample_price_data)
        data_manager.save_price_data("GOOGL", "US", sample_price_data)
        data_manager.save_price_data("CBA.AX", "AU", sample_price_data)
        
        available_tickers = data_manager.get_available_tickers()
        
        assert "US" in available_tickers
        assert "AU" in available_tickers
        
        assert "AAPL" in available_tickers["US"]
        assert "GOOGL" in available_tickers["US"]
        assert "CBA.AX" in available_tickers["AU"]
    
    def test_data_sorting(self, data_manager):
        """Test that data is properly sorted by date."""
        # Create unsorted data
        unsorted_data = pd.DataFrame({
            "date": [date(2024, 1, 3), date(2024, 1, 1), date(2024, 1, 2)],
            "open": [102.0, 100.0, 101.0],
            "high": [107.0, 105.0, 106.0],
            "low": [97.0, 95.0, 96.0],
            "close": [104.0, 102.0, 103.0],
            "volume": [1200000, 1000000, 1100000],
            "adjusted_close": [104.0, 102.0, 103.0]
        })
        
        data_manager.save_price_data("TEST", "US", unsorted_data)
        loaded_data = data_manager.load_price_data("TEST", "US")
        
        # Should be sorted by date
        dates = loaded_data["date"].tolist()
        assert dates == sorted(dates)
        
        # First row should be earliest date
        assert loaded_data.iloc[0]["date"] == date(2024, 1, 1)
        assert loaded_data.iloc[0]["close"] == 102.0
    
    def test_bulk_update_data_structure(self, data_manager):
        """Test bulk update data method structure (without actual API calls)."""
        tickers_config = {
            "US": {
                "stocks": ["AAPL", "GOOGL"],
                "etfs": ["SPY"]
            },
            "AU": {
                "stocks": ["CBA.AX"]
            }
        }
        
        # This will fail because no API client is set, but we can check the structure
        results = data_manager.bulk_update_data(tickers_config, force_refresh=False)
        
        # Should return results for all tickers
        expected_keys = ["AAPL_US", "GOOGL_US", "SPY_US", "CBA.AX_AU"]
        assert all(key in results for key in expected_keys)
        
        # All should be False since no API client
        assert all(not success for success in results.values())
    
    def test_invalid_data_handling(self, data_manager):
        """Test handling of invalid or corrupted data."""
        # Try to load from non-existent file
        result = data_manager.load_price_data("INVALID", "US")
        assert result is None
        
        # Try to save empty DataFrame
        empty_df = pd.DataFrame()
        success = data_manager.save_price_data("EMPTY", "US", empty_df)
        assert not success  # Should fail due to missing columns