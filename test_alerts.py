#!/usr/bin/env python3
"""
Test script for the alert generator system.
Runs independently of the main CLI to test alert functionality.
"""

import sys
from pathlib import Path
from datetime import date, datetime
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.config import load_config, setup_logging
from src.data.data_manager import DataManager
from src.alerts.alert_generator import InvestmentAlertGenerator


def test_alert_generation():
    """Test the alert generation system."""
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config("config")
        logger.info("Configuration loaded successfully")
        
        # Create alert generator
        alert_generator = InvestmentAlertGenerator(config)
        logger.info(f"Alert generator initialized with scoring method: {config.get('scoring_method', 'default')}")
        
        # Create data manager
        data_manager = DataManager()
        
        # Load data for all configured tickers
        tickers_config = config["tickers"]
        ticker_data = {}
        
        logger.info("Loading ticker data...")
        total_tickers = 0
        loaded_tickers = 0
        
        for market, ticker_types in tickers_config.items():
            ticker_data[market] = {}
            for ticker_type, ticker_list in ticker_types.items():
                for ticker in ticker_list:
                    total_tickers += 1
                    df = data_manager.load_price_data(ticker, market)
                    if df is not None and len(df) > 0:
                        ticker_data[market][ticker] = df
                        loaded_tickers += 1
                        logger.debug(f"Loaded {ticker} ({market}): {len(df)} data points")
                    else:
                        logger.warning(f"No data available for {ticker} ({market})")
        
        logger.info(f"Successfully loaded {loaded_tickers}/{total_tickers} tickers")
        
        if loaded_tickers == 0:
            logger.error("No ticker data available for alert generation")
            return False
        
        # Generate alerts for today
        alert_date = date.today()
        logger.info(f"Generating alerts for {alert_date}")
        
        alerts = alert_generator.generate_alerts(ticker_data, alert_date)
        
        if not alerts:
            logger.info("No alerts generated (scores below threshold or no valid opportunities)")
            return True
        
        # Display results
        print(f"\n🔔 Generated {len(alerts)} alerts for {alert_date}")
        print("=" * 60)
        
        for i, alert in enumerate(alerts, 1):
            print(f"\nAlert #{i}:")
            print(alert["message"])
            
            # Show component breakdown if available
            if alert.get("components"):
                print("\nScore Breakdown:")
                components = alert["components"]
                for key, value in components.items():
                    if key != "final_score":
                        formatted_key = key.replace("_", " ").title()
                        print(f"  {formatted_key}: {value:.3f}")
            
            print("-" * 40)
        
        # Test Slack formatting for first alert
        if alerts:
            print("\nSample Slack Message Format:")
            print("=" * 60)
            slack_msg = alerts[0]["slack_message"]
            print(f"Text: {slack_msg['text']}")
            for block in slack_msg['blocks']:
                if block['type'] == 'header':
                    print(f"Header: {block['text']['text']}")
                elif block['type'] == 'section' and 'fields' in block:
                    print("Fields:")
                    for field in block['fields']:
                        print(f"  {field['text']}")
        
        logger.info("Alert generation test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error testing alert generation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_alert_scheduling():
    """Test alert scheduling logic."""
    logger = logging.getLogger(__name__)
    
    try:
        config = load_config("config")
        alert_generator = InvestmentAlertGenerator(config)
        
        # Test schedule dates
        start_date = date(2024, 1, 1)
        end_date = date(2024, 12, 31)
        
        schedule_dates = alert_generator.get_alert_schedule_dates(start_date, end_date)
        
        print(f"\nAlert Schedule for {start_date} to {end_date}:")
        print("=" * 40)
        for alert_date in schedule_dates:
            should_generate = alert_generator.should_generate_alerts(alert_date)
            status = "✓" if should_generate else "✗"
            print(f"{status} {alert_date}")
        
        print(f"\nTotal scheduled alert dates: {len(schedule_dates)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing alert scheduling: {e}")
        return False


def main():
    """Main test function."""
    print("LT Investments Alert System Test")
    print("=" * 40)
    
    # Test alert generation
    print("\n1. Testing Alert Generation...")
    success1 = test_alert_generation()
    
    # Test alert scheduling
    print("\n2. Testing Alert Scheduling...")
    success2 = test_alert_scheduling()
    
    # Summary
    print(f"\nTest Results:")
    print(f"Alert Generation: {'✓ PASSED' if success1 else '✗ FAILED'}")
    print(f"Alert Scheduling: {'✓ PASSED' if success2 else '✗ FAILED'}")
    
    return 0 if (success1 and success2) else 1


if __name__ == "__main__":
    exit(main())