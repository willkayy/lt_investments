import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.models.scorer import InvestmentScorer


class TestInvestmentScorer:
    """Test cases for the InvestmentScorer class."""
    
    @pytest.fixture
    def config(self):
        """Standard configuration for tests."""
        return {
            "lookback_days": 90,
            "scoring_weights": {
                "price_position": 0.4,
                "momentum_decay": 0.3,
                "volatility_adjusted": 0.2,
                "volume_confirmation": 0.1
            },
            "momentum_decay_factor": 0.95,
            "volatility_window": 30
        }
    
    @pytest.fixture
    def scorer(self, config):
        """InvestmentScorer instance for tests."""
        return InvestmentScorer(config)
    
    @pytest.fixture
    def sample_data(self):
        """Sample price data for testing."""
        dates = [date.today() - timedelta(days=i) for i in range(100, 0, -1)]
        
        # Create declining price pattern
        prices = []
        base_price = 100.0
        for i in range(100):
            # Simulate declining trend with some volatility
            decline_factor = 1 - (i * 0.001)  # Gradual decline
            volatility = np.random.normal(0, 0.02)  # 2% daily volatility
            price = base_price * decline_factor * (1 + volatility)
            prices.append(max(price, 1.0))  # Ensure positive prices
        
        return pd.DataFrame({
            "date": dates,
            "open": prices,
            "high": [p * 1.02 for p in prices],
            "low": [p * 0.98 for p in prices],
            "close": prices,
            "volume": [1000000 + np.random.randint(-200000, 200000) for _ in range(100)],
            "adjusted_close": prices
        })
    
    def test_scorer_initialization(self, config):
        """Test scorer initializes with correct configuration."""
        scorer = InvestmentScorer(config)
        
        assert scorer.lookback_days == 90
        assert scorer.weights["price_position"] == 0.4
        assert scorer.momentum_decay_factor == 0.95
        assert scorer.volatility_window == 30
    
    def test_price_position_score_declining_stock(self, scorer, sample_data):
        """Test price position score for a declining stock."""
        # Current price should be near bottom of range
        score = scorer.calculate_price_position_score(sample_data.tail(90))
        
        # Score should be high (closer to 1.0) for declining stock
        assert 0.3 <= score <= 1.0
    
    def test_price_position_score_flat_stock(self, scorer):
        """Test price position score for flat stock (no movement)."""
        # Create flat price data
        dates = [date.today() - timedelta(days=i) for i in range(90, 0, -1)]
        flat_data = pd.DataFrame({
            "date": dates,
            "open": [100.0] * 90,
            "high": [100.0] * 90,
            "low": [100.0] * 90,
            "close": [100.0] * 90,
            "volume": [1000000] * 90,
            "adjusted_close": [100.0] * 90
        })
        
        score = scorer.calculate_price_position_score(flat_data)
        
        # Should return neutral score for no movement
        assert score == 0.5
    
    def test_momentum_decay_score(self, scorer, sample_data):
        """Test momentum decay score calculation."""
        score = scorer.calculate_momentum_decay_score(sample_data.tail(90))
        
        # Should be between 0 and 1
        assert 0.0 <= score <= 1.0
    
    def test_volatility_adjusted_score(self, scorer, sample_data):
        """Test volatility adjusted score calculation."""
        score = scorer.calculate_volatility_adjusted_score(sample_data.tail(90))
        
        # Should be between 0 and 1
        assert 0.0 <= score <= 1.0
    
    def test_volume_confirmation_score(self, scorer, sample_data):
        """Test volume confirmation score calculation."""
        score = scorer.calculate_volume_confirmation_score(sample_data.tail(90))
        
        # Should be between 0 and 1
        assert 0.0 <= score <= 1.0
    
    def test_final_score_calculation(self, scorer, sample_data):
        """Test final weighted score calculation."""
        final_score, components = scorer.calculate_final_score(sample_data.tail(90))
        
        # Final score should be between 0 and 1
        assert 0.0 <= final_score <= 1.0
        
        # Components should be present
        expected_components = ["price_position", "momentum_decay", "volatility_adjusted", "volume_confirmation"]
        for component in expected_components:
            assert component in components
            assert 0.0 <= components[component] <= 1.0
        
        # Final score should equal weighted sum
        weighted_sum = sum(
            components[comp] * scorer.weights[comp] 
            for comp in expected_components
        )
        assert abs(final_score - weighted_sum) < 0.001
    
    def test_score_ticker_with_valid_data(self, scorer, sample_data):
        """Test scoring a single ticker with valid data."""
        result = scorer.score_ticker("AAPL", "US", sample_data)
        
        # Check result structure
        assert "ticker" in result
        assert "market" in result
        assert "score" in result
        assert "components" in result
        assert "current_price" in result
        
        assert result["ticker"] == "AAPL"
        assert result["market"] == "US"
        assert 0.0 <= result["score"] <= 1.0
        assert result["current_price"] > 0
    
    def test_score_ticker_with_empty_data(self, scorer):
        """Test scoring a ticker with no data."""
        empty_data = pd.DataFrame()
        result = scorer.score_ticker("INVALID", "US", empty_data)
        
        assert result["ticker"] == "INVALID"
        assert result["score"] == 0.0
        assert "error" in result
    
    def test_score_multiple_tickers(self, scorer, sample_data):
        """Test scoring multiple tickers."""
        # Create sample data for multiple tickers
        ticker_data = {
            "US": {
                "AAPL": sample_data.copy(),
                "GOOGL": sample_data.copy()
            },
            "AU": {
                "CBA.AX": sample_data.copy()
            }
        }
        
        results_df = scorer.score_multiple_tickers(ticker_data)
        
        # Should have 3 results
        assert len(results_df) == 3
        
        # Should be sorted by score (descending)
        scores = results_df["score"].tolist()
        assert scores == sorted(scores, reverse=True)
        
        # All scores should be valid
        for score in scores:
            assert 0.0 <= score <= 1.0
    
    def test_insufficient_data_handling(self, scorer):
        """Test handling of insufficient data."""
        # Create very small dataset
        small_data = pd.DataFrame({
            "date": [date.today()],
            "close": [100.0],
            "high": [102.0],
            "low": [98.0],
            "volume": [1000000]
        })
        
        # Most scores should return 0 or low values for insufficient data
        price_score = scorer.calculate_price_position_score(small_data)
        momentum_score = scorer.calculate_momentum_decay_score(small_data)
        
        # Price score might work with minimal data
        assert 0.0 <= price_score <= 1.0
        
        # Momentum score should be 0 for insufficient data
        assert momentum_score == 0.0
    
    def test_weights_sum_to_one(self, config):
        """Test that scoring weights sum to 1.0."""
        weights = config["scoring_weights"]
        total_weight = sum(weights.values())
        
        assert abs(total_weight - 1.0) < 0.001