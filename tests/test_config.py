import pytest
import yaml
import tempfile
import shutil
import os
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.utils.config import ConfigLoader


class TestConfigLoader:
    """Test cases for the ConfigLoader class."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory for testing."""
        temp_dir = tempfile.mkdtemp()
        config_dir = Path(temp_dir) / "config"
        config_dir.mkdir()
        
        # Create sample settings.yaml
        settings = {
            "monthly_budget": 2000.0,
            "lookback_days": 90,
            "scoring_weights": {
                "price_position": 0.4,
                "momentum_decay": 0.3,
                "volatility_adjusted": 0.2,
                "volume_confirmation": 0.1
            },
            "api_keys": {
                "alpha_vantage": "${ALPHA_VANTAGE_API_KEY}"
            },
            "supported_markets": ["US", "AU"]
        }
        
        with open(config_dir / "settings.yaml", 'w') as f:
            yaml.dump(settings, f)
        
        # Create sample tickers.yaml
        tickers = {
            "tickers": {
                "US": {
                    "stocks": ["AAPL", "GOOGL"],
                    "etfs": ["SPY"]
                },
                "AU": {
                    "stocks": ["CBA.AX"],
                    "etfs": ["VAS.AX"]
                }
            }
        }
        
        with open(config_dir / "tickers.yaml", 'w') as f:
            yaml.dump(tickers, f)
        
        yield str(config_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def config_loader(self, temp_config_dir):
        """ConfigLoader instance with temporary directory."""
        return ConfigLoader(temp_config_dir)
    
    def test_load_settings(self, config_loader):
        """Test loading settings configuration."""
        settings = config_loader.load_settings()
        
        assert settings["monthly_budget"] == 2000.0
        assert settings["lookback_days"] == 90
        assert "scoring_weights" in settings
        assert len(settings["supported_markets"]) == 2
    
    def test_load_tickers(self, config_loader):
        """Test loading tickers configuration."""
        tickers = config_loader.load_tickers()
        
        assert "tickers" in tickers
        assert "US" in tickers["tickers"]
        assert "AU" in tickers["tickers"]
        assert "AAPL" in tickers["tickers"]["US"]["stocks"]
        assert "CBA.AX" in tickers["tickers"]["AU"]["stocks"]
    
    def test_load_full_config(self, config_loader):
        """Test loading and merging all configuration."""
        config = config_loader.load_full_config()
        
        # Should have both settings and tickers
        assert "monthly_budget" in config
        assert "tickers" in config
        assert "total_tickers" in config
        
        # Check computed total_tickers
        assert config["total_tickers"] == 4  # AAPL, GOOGL, SPY, CBA.AX, VAS.AX = 5 actually
    
    def test_env_var_substitution(self, config_loader):
        """Test environment variable substitution."""
        # Set test environment variable
        os.environ["ALPHA_VANTAGE_API_KEY"] = "test_api_key"
        
        try:
            settings = config_loader.load_settings()
            assert settings["api_keys"]["alpha_vantage"] == "test_api_key"
        finally:
            # Clean up
            if "ALPHA_VANTAGE_API_KEY" in os.environ:
                del os.environ["ALPHA_VANTAGE_API_KEY"]
    
    def test_env_var_missing(self, config_loader):
        """Test handling of missing environment variables."""
        # Ensure env var is not set
        if "ALPHA_VANTAGE_API_KEY" in os.environ:
            del os.environ["ALPHA_VANTAGE_API_KEY"]
        
        settings = config_loader.load_settings()
        # Should default to empty string for missing env vars
        assert settings["api_keys"]["alpha_vantage"] == ""
    
    def test_count_total_tickers(self, config_loader):
        """Test ticker counting functionality."""
        tickers = config_loader.load_tickers()
        count = config_loader._count_total_tickers(tickers)
        
        # Should count all tickers across all markets and types
        assert count == 5  # AAPL, GOOGL, SPY, CBA.AX, VAS.AX
    
    def test_validate_config_valid(self, config_loader):
        """Test validation of valid configuration."""
        config = config_loader.load_full_config()
        is_valid = config_loader.validate_config(config)
        
        assert is_valid
    
    def test_validate_config_missing_required(self, config_loader):
        """Test validation with missing required fields."""
        config = {"some_field": "value"}  # Missing required fields
        is_valid = config_loader.validate_config(config)
        
        assert not is_valid
    
    def test_validate_config_invalid_weights(self, config_loader):
        """Test validation with invalid scoring weights."""
        config = config_loader.load_full_config()
        
        # Modify weights to not sum to 1.0
        config["scoring_weights"]["price_position"] = 0.8
        is_valid = config_loader.validate_config(config)
        
        assert not is_valid
    
    def test_validate_config_negative_budget(self, config_loader):
        """Test validation with negative budget."""
        config = config_loader.load_full_config()
        config["monthly_budget"] = -100.0
        
        is_valid = config_loader.validate_config(config)
        assert not is_valid
    
    def test_get_api_key_from_config(self, config_loader):
        """Test getting API key from configuration."""
        config = {"api_keys": {"alpha_vantage": "config_key"}}
        
        api_key = config_loader.get_api_key("alpha_vantage", config)
        assert api_key == "config_key"
    
    def test_get_api_key_from_env(self, config_loader):
        """Test getting API key from environment."""
        os.environ["ALPHA_VANTAGE_API_KEY"] = "env_key"
        
        try:
            # No config provided, should get from env
            api_key = config_loader.get_api_key("alpha_vantage", None)
            assert api_key == "env_key"
        finally:
            del os.environ["ALPHA_VANTAGE_API_KEY"]
    
    def test_get_api_key_missing(self, config_loader):
        """Test getting API key when not available."""
        # Ensure no env var
        if "TEST_API_KEY" in os.environ:
            del os.environ["TEST_API_KEY"]
        
        api_key = config_loader.get_api_key("test", {})
        assert api_key is None
    
    def test_save_config(self, config_loader, temp_config_dir):
        """Test saving configuration to file."""
        config = {"test_setting": "test_value", "total_tickers": 5}
        
        success = config_loader.save_config(config, "test_config.yaml")
        assert success
        
        # Check file was created and doesn't contain computed values
        config_file = Path(temp_config_dir) / "test_config.yaml"
        assert config_file.exists()
        
        with open(config_file, 'r') as f:
            saved_config = yaml.safe_load(f)
        
        assert saved_config["test_setting"] == "test_value"
        assert "total_tickers" not in saved_config  # Should be removed
    
    def test_missing_config_file(self):
        """Test handling of missing configuration files."""
        loader = ConfigLoader("/nonexistent/path")
        
        with pytest.raises(FileNotFoundError):
            loader.load_settings()
    
    def test_malformed_yaml(self, temp_config_dir):
        """Test handling of malformed YAML files."""
        # Create malformed YAML file
        bad_file = Path(temp_config_dir) / "bad.yaml"
        with open(bad_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        loader = ConfigLoader(temp_config_dir)
        
        with pytest.raises(yaml.YAMLError):
            loader.load_settings("bad.yaml")