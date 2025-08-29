#!/usr/bin/env python3
"""
Long-Term Investment Alert System - Main CLI Script

This script provides the main entry point for running backtests,
updating data, and analyzing investment opportunities.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.config import load_config, setup_logging
from src.data.data_manager import DataManager
from src.data.api_client import create_api_client
from src.models.scorer import InvestmentScorer
from src.models.allocator import PortfolioAllocator
from src.backtesting.engine import BacktestEngine
from src.utils.helpers import create_performance_summary, generate_ticker_summary


def update_data_command(args, config):
    """Update price data for all configured tickers."""
    logger = logging.getLogger(__name__)
    
    try:
        # Create API client
        api_client = create_api_client("alpha_vantage")
        data_manager = DataManager(api_client=api_client)
        
        # Update data for all tickers
        tickers_config = config["tickers"]
        results = data_manager.bulk_update_data(tickers_config, force_refresh=args.force)
        
        # Report results
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        logger.info(f"Data update completed: {success_count}/{total_count} successful")
        
        if args.verbose:
            for ticker_market, success in results.items():
                status = "✓" if success else "✗"
                print(f"{status} {ticker_market}")
        
        return success_count == total_count
        
    except Exception as e:
        logger.error(f"Error updating data: {e}")
        return False


def score_tickers_command(args, config):
    """Score all tickers and display results."""
    logger = logging.getLogger(__name__)
    
    try:
        data_manager = DataManager()
        scorer = InvestmentScorer(config)
        
        # Load data for all tickers
        tickers_config = config["tickers"]
        ticker_data = {}
        
        for market, ticker_types in tickers_config.items():
            ticker_data[market] = {}
            for ticker_type, ticker_list in ticker_types.items():
                for ticker in ticker_list:
                    df = data_manager.load_price_data(ticker, market)
                    if df is not None:
                        ticker_data[market][ticker] = df
        
        # Score all tickers
        scores_df = scorer.score_multiple_tickers(ticker_data)
        
        if len(scores_df) == 0:
            logger.warning("No tickers could be scored")
            return False
        
        # Display results
        print(generate_ticker_summary(scores_df, args.top))
        
        # Optionally save results
        if args.save:
            filename = f"scores_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
            scores_df.to_csv(f"data/scores/{filename}", index=False)
            print(f"\nResults saved to data/scores/{filename}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error scoring tickers: {e}")
        return False


def allocate_command(args, config):
    """Calculate and display portfolio allocation."""
    logger = logging.getLogger(__name__)
    
    try:
        data_manager = DataManager()
        scorer = InvestmentScorer(config)
        allocator = PortfolioAllocator(config)
        
        # Load and score data
        tickers_config = config["tickers"]
        ticker_data = {}
        
        for market, ticker_types in tickers_config.items():
            ticker_data[market] = {}
            for ticker_type, ticker_list in ticker_types.items():
                for ticker in ticker_list:
                    df = data_manager.load_price_data(ticker, market)
                    if df is not None:
                        ticker_data[market][ticker] = df
        
        scores_df = scorer.score_multiple_tickers(ticker_data)
        
        # Calculate allocation
        comparison = allocator.compare_strategies(scores_df, ticker_data)
        
        # Display results
        print(allocator.generate_allocation_summary(comparison))
        
        return True
        
    except Exception as e:
        logger.error(f"Error calculating allocation: {e}")
        return False


def backtest_command(args, config):
    """Run historical backtest."""
    logger = logging.getLogger(__name__)
    
    try:
        # Create components
        api_client = create_api_client("alpha_vantage") if args.update_data else None
        data_manager = DataManager(api_client=api_client)
        
        # Update data if requested
        if args.update_data:
            logger.info("Updating data before backtest...")
            tickers_config = config["tickers"]
            data_manager.bulk_update_data(tickers_config, force_refresh=True)
        
        # Load data for backtest
        tickers_config = config["tickers"]
        ticker_data = {}
        
        for market, ticker_types in tickers_config.items():
            ticker_data[market] = {}
            for ticker_type, ticker_list in ticker_types.items():
                for ticker in ticker_list:
                    df = data_manager.load_price_data(ticker, market)
                    if df is not None and len(df) > 0:
                        ticker_data[market][ticker] = df
        
        if not any(ticker_data.values()):
            logger.error("No ticker data available for backtesting")
            return False
        
        # Run backtest
        backtest_engine = BacktestEngine(config, data_manager)
        
        logger.info("Starting backtest...")
        backtest_results = backtest_engine.run_monthly_backtest(ticker_data)
        
        if len(backtest_results) == 0:
            logger.error("Backtest produced no results")
            return False
        
        # Calculate performance metrics
        metrics = backtest_engine.calculate_performance_metrics(backtest_results, ticker_data)
        
        # Display results
        print(create_performance_summary(metrics))
        
        # Save results
        results_file = data_manager.save_backtest_results(backtest_results, args.name)
        if results_file:
            print(f"\nDetailed results saved to: {results_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error running backtest: {e}")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Long-Term Investment Alert System")
    
    # Global options
    parser.add_argument("--config-dir", default="config", help="Configuration directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Update data command
    update_parser = subparsers.add_parser("update-data", help="Update price data from API")
    update_parser.add_argument("--force", action="store_true", help="Force refresh of all data")
    
    # Score tickers command
    score_parser = subparsers.add_parser("score", help="Score all tickers")
    score_parser.add_argument("--top", type=int, default=10, help="Show top N tickers")
    score_parser.add_argument("--save", action="store_true", help="Save results to CSV")
    
    # Allocate command
    allocate_parser = subparsers.add_parser("allocate", help="Calculate portfolio allocation")
    
    # Backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run historical backtest")
    backtest_parser.add_argument("--update-data", action="store_true", help="Update data before backtesting")
    backtest_parser.add_argument("--name", help="Name for backtest results file")
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config(args.config_dir)
        logger.info("Configuration loaded successfully")
        
        # Route to appropriate command
        if args.command == "update-data":
            success = update_data_command(args, config)
        elif args.command == "score":
            success = score_tickers_command(args, config)
        elif args.command == "allocate":
            success = allocate_command(args, config)
        elif args.command == "backtest":
            success = backtest_command(args, config)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())