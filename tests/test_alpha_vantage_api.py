import pytest
import os
from unittest.mock import patch, MagicMock
from src.data.api_client import AlphaVantageClient, create_api_client
import requests


class TestAlphaVantageAPI:
    """Test Alpha Vantage API connectivity and basic functionality."""
    
    def test_api_key_loading(self):
        """Test that API key is loaded from environment."""
        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "test_key"}):
            client = create_api_client("alpha_vantage")
            assert isinstance(client, AlphaVantageClient)
            assert client.api_key == "test_key"
    
    def test_api_key_missing_raises_error(self):
        """Test that missing API key raises appropriate error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Alpha Vantage API key required"):
                create_api_client("alpha_vantage")
    
    @patch('requests.get')
    def test_api_basic_connectivity(self, mock_get):
        """Test basic API request structure and response handling."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Global Quote": {
                "01. symbol": "AAPL",
                "05. price": "150.00"
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = AlphaVantageClient("test_key")
        price = client.get_current_price("AAPL")
        
        assert price == 150.0
        mock_get.assert_called_once()
        
        # Verify API call structure
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://www.alphavantage.co/query"
        params = call_args[1]["params"]
        assert params["function"] == "GLOBAL_QUOTE"
        assert params["symbol"] == "AAPL"
        assert params["apikey"] == "test_key"
    
    @patch('requests.get')
    def test_api_error_handling(self, mock_get):
        """Test API error response handling."""
        # Mock error response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Error Message": "Invalid API call"
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = AlphaVantageClient("test_key")
        
        with pytest.raises(ValueError, match="API Error: Invalid API call"):
            client.get_current_price("INVALID")
    
    @patch('requests.get')
    def test_api_rate_limit_handling(self, mock_get):
        """Test API rate limit response handling."""
        # Mock rate limit response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute"
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = AlphaVantageClient("test_key")
        
        with pytest.raises(ValueError, match="API Rate Limit"):
            client.get_current_price("AAPL")
    
    def test_real_api_connection(self):
        """
        Test real API connection if API key is available.
        This test will be skipped if no API key is set.
        """
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            pytest.skip("No ALPHA_VANTAGE_API_KEY found in environment")
        
        client = AlphaVantageClient(api_key)
        
        try:
            # Test with a well-known ticker
            price = client.get_current_price("AAPL")
            assert isinstance(price, float)
            assert price > 0
            print(f"✓ Successfully retrieved AAPL price: ${price}")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Network error connecting to Alpha Vantage API: {e}")
        except ValueError as e:
            if "API Rate Limit" in str(e):
                pytest.skip("API rate limit reached - test inconclusive")
            else:
                pytest.fail(f"API returned error: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error: {e}")
    
    def test_real_api_historical_data(self):
        """
        Test real API historical data if API key is available.
        This test will be skipped if no API key is set.
        """
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            pytest.skip("No ALPHA_VANTAGE_API_KEY found in environment")
        
        client = AlphaVantageClient(api_key)
        
        try:
            # Test with a well-known ticker
            df = client.get_historical_data("AAPL", "1y")
            assert not df.empty
            assert "date" in df.columns
            assert "close" in df.columns
            assert len(df) > 0
            print(f"✓ Successfully retrieved AAPL historical data: {len(df)} records")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Network error connecting to Alpha Vantage API: {e}")
        except ValueError as e:
            if "API Rate Limit" in str(e):
                pytest.skip("API rate limit reached - test inconclusive")
            else:
                pytest.fail(f"API returned error: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error: {e}")


if __name__ == "__main__":
    # Run basic connectivity test if called directly
    print("Testing Alpha Vantage API connection...")
    
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("❌ No ALPHA_VANTAGE_API_KEY found in environment variables")
        print("Please set your API key: export ALPHA_VANTAGE_API_KEY=your_key_here")
        exit(1)
    
    try:
        client = AlphaVantageClient(api_key)
        price = client.get_current_price("AAPL")
        print(f"✓ API connection successful! AAPL current price: ${price}")
        
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        exit(1)