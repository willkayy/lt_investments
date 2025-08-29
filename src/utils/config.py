import yaml
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Handles loading and merging of configuration files."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        load_dotenv()  # Load environment variables from .env file
    
    def load_settings(self, settings_file: str = "settings.yaml") -> Dict[str, Any]:
        """Load main settings configuration."""
        settings_path = self.config_dir / settings_file
        
        if not settings_path.exists():
            raise FileNotFoundError(f"Settings file not found: {settings_path}")
        
        try:
            with open(settings_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Substitute environment variables
            config = self._substitute_env_vars(config)
            
            logger.info(f"Loaded settings from {settings_path}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            raise
    
    def load_tickers(self, tickers_file: str = "tickers.yaml") -> Dict[str, Any]:
        """Load tickers configuration."""
        tickers_path = self.config_dir / tickers_file
        
        if not tickers_path.exists():
            raise FileNotFoundError(f"Tickers file not found: {tickers_path}")
        
        try:
            with open(tickers_path, 'r') as f:
                tickers_config = yaml.safe_load(f)
            
            logger.info(f"Loaded tickers from {tickers_path}")
            return tickers_config
            
        except Exception as e:
            logger.error(f"Error loading tickers: {e}")
            raise
    
    def load_full_config(self, settings_file: str = "settings.yaml", 
                        tickers_file: str = "tickers.yaml") -> Dict[str, Any]:
        """Load and merge all configuration files."""
        settings = self.load_settings(settings_file)
        tickers = self.load_tickers(tickers_file)
        
        # Merge configurations
        full_config = {**settings, **tickers}
        
        # Add some computed values
        full_config["total_tickers"] = self._count_total_tickers(tickers)
        
        return full_config
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """Recursively substitute environment variables in config."""
        if isinstance(config, dict):
            return {key: self._substitute_env_vars(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            # Extract environment variable name
            env_var = config[2:-1]
            value = os.getenv(env_var)
            if value is None:
                logger.warning(f"Environment variable {env_var} not found, using empty string")
                return ""
            return value
        else:
            return config
    
    def _count_total_tickers(self, tickers_config: Dict[str, Any]) -> int:
        """Count total number of tickers across all markets."""
        total = 0
        
        if "tickers" in tickers_config:
            for market, ticker_types in tickers_config["tickers"].items():
                if isinstance(ticker_types, dict):
                    for ticker_type, ticker_list in ticker_types.items():
                        if isinstance(ticker_list, list):
                            total += len(ticker_list)
        
        return total
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration completeness and correctness."""
        required_settings = [
            "monthly_budget",
            "lookback_days",
            "scoring_weights",
            "supported_markets"
        ]
        
        required_tickers = ["tickers"]
        
        # Check required settings
        for setting in required_settings:
            if setting not in config:
                logger.error(f"Missing required setting: {setting}")
                return False
        
        # Check required tickers section
        for section in required_tickers:
            if section not in config:
                logger.error(f"Missing required section: {section}")
                return False
        
        # Validate scoring weights sum to 1.0
        weights = config.get("scoring_weights", {})
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:  # Allow small floating point errors
            logger.error(f"Scoring weights sum to {weight_sum}, should sum to 1.0")
            return False
        
        # Validate budget is positive
        budget = config.get("monthly_budget", 0)
        if budget <= 0:
            logger.error(f"Monthly budget must be positive, got {budget}")
            return False
        
        # Check if we have any tickers
        total_tickers = config.get("total_tickers", 0)
        if total_tickers == 0:
            logger.warning("No tickers configured")
        
        logger.info("Configuration validation passed")
        return True
    
    def save_config(self, config: Dict[str, Any], filename: str) -> bool:
        """Save configuration to file."""
        filepath = self.config_dir / filename
        
        try:
            # Remove computed values before saving
            config_to_save = config.copy()
            if "total_tickers" in config_to_save:
                del config_to_save["total_tickers"]
            
            with open(filepath, 'w') as f:
                yaml.dump(config_to_save, f, default_flow_style=False, indent=2)
            
            logger.info(f"Configuration saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get_api_key(self, api_name: str, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get API key from config or environment."""
        # Try config first
        if config and "api_keys" in config and api_name in config["api_keys"]:
            return config["api_keys"][api_name]
        
        # Try environment variables
        env_var_name = f"{api_name.upper()}_API_KEY"
        return os.getenv(env_var_name)


def setup_logging(log_level: str = "INFO") -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def load_config(config_dir: str = "config") -> Dict[str, Any]:
    """Convenience function to load full configuration."""
    loader = ConfigLoader(config_dir)
    config = loader.load_full_config()
    
    if not loader.validate_config(config):
        raise ValueError("Configuration validation failed")
    
    return config