#!/usr/bin/env python3
"""
Alert System Backtest - Shows when alerts would have been triggered historically.
This helps validate the alert system and understand buy opportunity frequency.
"""

import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import logging
import pandas as pd
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.config import load_config, setup_logging
from src.data.data_manager import DataManager
from src.alerts.alert_generator import InvestmentAlertGenerator


def backtest_alerts(start_date: date, end_date: date, config: dict) -> pd.DataFrame:
    """
    Backtest the alert system over a historical period.
    
    Args:
        start_date: Start date for backtest
        end_date: End date for backtest
        config: System configuration
        
    Returns:
        DataFrame with historical alert data
    """
    logger = logging.getLogger(__name__)
    
    # Create alert generator
    alert_generator = InvestmentAlertGenerator(config)
    data_manager = DataManager()
    
    # Load all ticker data
    tickers_config = config["tickers"]
    ticker_data = {}
    
    logger.info("Loading historical ticker data...")
    loaded_tickers = 0
    
    for market, ticker_types in tickers_config.items():
        ticker_data[market] = {}
        for ticker_type, ticker_list in ticker_types.items():
            for ticker in ticker_list:
                df = data_manager.load_price_data(ticker, market)
                if df is not None and len(df) > 0:
                    ticker_data[market][ticker] = df
                    loaded_tickers += 1
    
    logger.info(f"Loaded {loaded_tickers} tickers for backtesting")
    
    # Get all alert dates in the period
    alert_dates = alert_generator.get_alert_schedule_dates(start_date, end_date)
    logger.info(f"Testing {len(alert_dates)} alert dates from {start_date} to {end_date}")
    
    all_alerts = []
    
    for alert_date in alert_dates:
        logger.info(f"Processing alert date: {alert_date}")
        
        # Filter ticker data up to this date
        date_filtered_data = {}
        for market, tickers in ticker_data.items():
            date_filtered_data[market] = {}
            for ticker, df in tickers.items():
                # Only use data up to the alert date
                filtered_df = df[pd.to_datetime(df['date']).dt.date <= alert_date]
                if len(filtered_df) >= 30:  # Need minimum data for scoring
                    date_filtered_data[market][ticker] = filtered_df
        
        # Generate alerts for this date
        alerts = alert_generator.generate_alerts(date_filtered_data, alert_date)
        
        # Add to results
        for alert in alerts:
            alert_record = {
                'alert_date': alert_date,
                'ticker': alert['ticker'],
                'market': alert['market'],
                'action': alert['action'],
                'price': alert['price'],
                'shares': alert['shares'],
                'amount': alert['amount'],
                'allocation_pct': alert['allocation_percentage'],
                'score': alert['score'],
                'oversold_score': alert['components'].get('oversold_score', 0),
                'quality_filter': alert['components'].get('quality_filter', 0),
                'volatility_bonus': alert['components'].get('volatility_bonus', 0)
            }
            all_alerts.append(alert_record)
    
    return pd.DataFrame(all_alerts)


def analyze_alert_performance(alerts_df: pd.DataFrame, ticker_data: dict) -> dict:
    """
    Analyze how well the alerts performed by looking at subsequent returns.
    """
    if len(alerts_df) == 0:
        return {}
    
    logger = logging.getLogger(__name__)
    performance_data = []
    
    for _, alert in alerts_df.iterrows():
        ticker = alert['ticker']
        market = alert['market']
        alert_date = pd.Timestamp(alert['alert_date']).date()
        alert_price = alert['price']
        
        # Get ticker data
        if market in ticker_data and ticker in ticker_data[market]:
            df = ticker_data[market][ticker]
            
            # Find the alert date in the data
            alert_data = df[pd.to_datetime(df['date']).dt.date <= alert_date].iloc[-1]
            
            # Calculate returns at different periods
            returns = {}
            for days in [7, 30, 90]:
                future_date = alert_date + timedelta(days=days)
                future_data = df[pd.to_datetime(df['date']).dt.date >= future_date]
                
                if len(future_data) > 0:
                    future_price = future_data.iloc[0]['adjusted_close']
                    returns[f'return_{days}d'] = (future_price - alert_price) / alert_price
                else:
                    returns[f'return_{days}d'] = None
            
            performance_data.append({
                'alert_date': alert['alert_date'],
                'ticker': ticker,
                'market': market,
                'score': alert['score'],
                'amount': alert['amount'],
                **returns
            })
    
    performance_df = pd.DataFrame(performance_data)
    
    if len(performance_df) == 0:
        return {}
    
    # Calculate summary statistics
    stats = {}
    for period in ['7d', '30d', '90d']:
        col = f'return_{period}'
        if col in performance_df.columns:
            returns = performance_df[col].dropna()
            if len(returns) > 0:
                stats[period] = {
                    'mean_return': returns.mean(),
                    'median_return': returns.median(),
                    'positive_rate': (returns > 0).mean(),
                    'max_return': returns.max(),
                    'min_return': returns.min(),
                    'count': len(returns)
                }
    
    return {
        'performance_df': performance_df,
        'summary_stats': stats
    }


def main():
    """Main backtest function."""
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = load_config("config")
        
        # Determine backtest period
        backtest_start = pd.Timestamp(config.get("backtest_start_date", "2024-01-01")).date()
        backtest_end = pd.Timestamp(config.get("backtest_end_date", "2025-08-01")).date()
        
        print(f"Alert System Backtest: {backtest_start} to {backtest_end}")
        print("=" * 60)
        
        # Run alert backtest
        print("\nRunning historical alert backtest...")
        alerts_df = backtest_alerts(backtest_start, backtest_end, config)
        
        if len(alerts_df) == 0:
            print("❌ No alerts would have been generated in the backtest period")
            print("This could mean:")
            print("  - Alert threshold is too high")
            print("  - No good opportunities in this period") 
            print("  - Insufficient historical data")
            return 1
        
        # Display alert summary
        print(f"\n📊 Alert Summary")
        print("-" * 40)
        print(f"Total Alerts Generated: {len(alerts_df)}")
        print(f"Alert Frequency: {len(alerts_df) / ((backtest_end - backtest_start).days / 30):.1f} per month")
        print(f"Total Investment: ${alerts_df['amount'].sum():,.2f}")
        print(f"Average Alert Score: {alerts_df['score'].mean():.3f}")
        
        # Show alerts by month
        alerts_df['alert_month'] = pd.to_datetime(alerts_df['alert_date']).dt.to_period('M')
        monthly_alerts = alerts_df.groupby('alert_month').size()
        
        print(f"\n📅 Monthly Alert Distribution")
        print("-" * 40)
        for month, count in monthly_alerts.items():
            month_amount = alerts_df[alerts_df['alert_month'] == month]['amount'].sum()
            print(f"{month}: {count} alerts, ${month_amount:,.2f}")
        
        # Show top tickers
        ticker_summary = alerts_df.groupby(['ticker', 'market']).agg({
            'score': 'mean',
            'amount': 'sum',
            'alert_date': 'count'
        }).rename(columns={'alert_date': 'alert_count'}).round(3)
        
        print(f"\n🏆 Top Alert Tickers")
        print("-" * 40)
        print(ticker_summary.sort_values('alert_count', ascending=False).head(10))
        
        # Analyze performance
        print(f"\n📈 Analyzing Alert Performance...")
        
        # Load ticker data for performance analysis
        data_manager = DataManager()
        ticker_data = {}
        tickers_config = config["tickers"]
        
        for market, ticker_types in tickers_config.items():
            ticker_data[market] = {}
            for ticker_type, ticker_list in ticker_types.items():
                for ticker in ticker_list:
                    df = data_manager.load_price_data(ticker, market)
                    if df is not None:
                        ticker_data[market][ticker] = df
        
        performance_results = analyze_alert_performance(alerts_df, ticker_data)
        
        if performance_results and 'summary_stats' in performance_results:
            print(f"\n🎯 Alert Performance Analysis")
            print("-" * 40)
            
            for period, stats in performance_results['summary_stats'].items():
                print(f"\n{period.upper()} Returns:")
                print(f"  Mean Return: {stats['mean_return']*100:+.1f}%")
                print(f"  Median Return: {stats['median_return']*100:+.1f}%")
                print(f"  Success Rate: {stats['positive_rate']*100:.1f}%")
                print(f"  Best/Worst: {stats['max_return']*100:+.1f}% / {stats['min_return']*100:+.1f}%")
                print(f"  Sample Size: {stats['count']} alerts")
        
        # Show recent alerts
        recent_alerts = alerts_df.tail(10)
        print(f"\n🕒 Most Recent Alerts")
        print("-" * 40)
        for _, alert in recent_alerts.iterrows():
            print(f"{alert['alert_date']}: {alert['ticker']} ({alert['market']}) - "
                  f"${alert['price']:.2f} × {alert['shares']:.1f} = ${alert['amount']:.2f} "
                  f"(Score: {alert['score']:.3f})")
        
        # Save results
        output_file = f"data/alerts/alert_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        alerts_df.to_csv(output_file, index=False)
        print(f"\n💾 Detailed results saved to: {output_file}")
        
        logger.info("Alert backtest completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error running alert backtest: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())