import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple, Optional
import logging
from dateutil.relativedelta import relativedelta

from ..models.scorer import InvestmentScorer
from ..models.allocator import PortfolioAllocator
from ..data.data_manager import DataManager

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Backtesting engine to evaluate investment strategies."""
    
    def __init__(self, config: Dict[str, Any], data_manager: DataManager):
        self.config = config
        self.data_manager = data_manager
        self.scorer = InvestmentScorer(config)
        self.allocator = PortfolioAllocator(config)
        
        # Backtest parameters
        self.start_date = datetime.strptime(config["backtest_start_date"], "%Y-%m-%d").date()
        self.end_date = datetime.strptime(config["backtest_end_date"], "%Y-%m-%d").date()
        self.lookback_days = config.get("lookback_days", 90)
        
    def get_available_data_range(self, ticker_data: Dict[str, Dict[str, pd.DataFrame]]) -> Tuple[date, date]:
        """Determine the actual date range available for backtesting."""
        min_start = None
        max_end = None
        
        for market, tickers in ticker_data.items():
            for ticker, df in tickers.items():
                if df is not None and len(df) > 0:
                    ticker_start = df.iloc[self.lookback_days]["date"] if len(df) > self.lookback_days else df.iloc[-1]["date"]
                    ticker_end = df.iloc[-1]["date"]
                    
                    if min_start is None or ticker_start > min_start:
                        min_start = ticker_start
                    if max_end is None or ticker_end < max_end:
                        max_end = ticker_end
        
        return min_start, max_end
    
    def get_price_at_date(self, df: pd.DataFrame, target_date: date) -> Optional[float]:
        """Get the price closest to the target date."""
        if df is None or len(df) == 0:
            return None
            
        # Find the closest date
        df_dates = df[df["date"] <= target_date]
        if len(df_dates) == 0:
            return None
            
        return float(df_dates.iloc[-1]["close"])
    
    def get_data_up_to_date(self, df: pd.DataFrame, target_date: date, lookback_days: int) -> pd.DataFrame:
        """Get data up to target_date with lookback period."""
        if df is None or len(df) == 0:
            return df
            
        # Filter data up to target date
        filtered_df = df[df["date"] <= target_date].copy()
        
        # Return last N days
        return filtered_df.tail(lookback_days)
    
    def run_monthly_backtest(self, ticker_data: Dict[str, Dict[str, pd.DataFrame]]) -> pd.DataFrame:
        """
        Run backtest with monthly investment periods.
        
        Returns DataFrame with monthly investment decisions and performance.
        """
        # Determine actual date range
        available_start, available_end = self.get_available_data_range(ticker_data)
        
        backtest_start = max(self.start_date, available_start) if available_start else self.start_date
        backtest_end = min(self.end_date, available_end) if available_end else self.end_date
        
        logger.info(f"Running backtest from {backtest_start} to {backtest_end}")
        
        # Generate monthly dates
        current_date = backtest_start
        monthly_dates = []
        
        while current_date <= backtest_end:
            monthly_dates.append(current_date)
            current_date = current_date + relativedelta(months=1)
        
        if len(monthly_dates) == 0:
            logger.error("No valid monthly dates for backtesting")
            return pd.DataFrame()
        
        backtest_results = []
        portfolio_value = 0.0
        total_invested = 0.0
        holdings = {}  # {ticker_market: {"shares": X, "avg_price": Y}}
        
        for month_date in monthly_dates:
            logger.info(f"Processing month: {month_date}")
            
            # Get data up to this date for scoring
            monthly_ticker_data = {}
            scores_data = []
            
            for market, tickers in ticker_data.items():
                monthly_ticker_data[market] = {}
                
                for ticker, df in tickers.items():
                    # Get data up to current month
                    month_data = self.get_data_up_to_date(df, month_date, self.lookback_days)
                    
                    if month_data is not None and len(month_data) >= 10:  # Minimum data requirement
                        monthly_ticker_data[market][ticker] = month_data
                        
                        # Score this ticker
                        score_result = self.scorer.score_ticker(ticker, market, month_data)
                        scores_data.append(score_result)
            
            if not scores_data:
                logger.warning(f"No valid data for {month_date}")
                continue
            
            # Create scores DataFrame
            scores_df = pd.DataFrame(scores_data)
            
            # Calculate allocations
            allocations_df = self.allocator.calculate_allocations(scores_df)
            
            # Simulate purchases
            month_investments = []
            monthly_invested = 0.0
            
            for _, allocation in allocations_df.iterrows():
                ticker = allocation["ticker"]
                market = allocation["market"]
                shares_to_buy = allocation["shares"]
                price = allocation["current_price"]
                amount = allocation["actual_amount"]
                
                # Update holdings
                key = f"{ticker}_{market}"
                if key in holdings:
                    # Update average price
                    total_shares = holdings[key]["shares"] + shares_to_buy
                    total_cost = holdings[key]["shares"] * holdings[key]["avg_price"] + amount
                    holdings[key] = {
                        "shares": total_shares,
                        "avg_price": total_cost / total_shares if total_shares > 0 else price
                    }
                else:
                    holdings[key] = {"shares": shares_to_buy, "avg_price": price}
                
                month_investments.append({
                    "date": month_date,
                    "ticker": ticker,
                    "market": market,
                    "shares": shares_to_buy,
                    "price": price,
                    "amount": amount,
                    "score": allocation["score"]
                })
                
                monthly_invested += amount
            
            total_invested += monthly_invested
            
            # Calculate current portfolio value
            current_portfolio_value = 0.0
            for key, holding in holdings.items():
                ticker, market = key.split("_", 1)
                current_price = self.get_price_at_date(ticker_data[market][ticker], month_date)
                if current_price:
                    current_portfolio_value += holding["shares"] * current_price
            
            portfolio_value = current_portfolio_value
            
            # Store monthly summary
            backtest_results.extend(month_investments)
            
            logger.info(f"Month {month_date}: Invested ${monthly_invested:.2f}, Portfolio Value: ${portfolio_value:.2f}")
        
        # Convert to DataFrame
        if backtest_results:
            results_df = pd.DataFrame(backtest_results)
            
            # Add cumulative metrics
            results_df["cumulative_invested"] = results_df.groupby(results_df.index // len(allocations_df))["amount"].cumsum()
            
            return results_df
        else:
            return pd.DataFrame()
    
    def calculate_performance_metrics(self, backtest_results: pd.DataFrame, 
                                    ticker_data: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        if len(backtest_results) == 0:
            return {"error": "No backtest results to analyze"}
        
        # Calculate final portfolio value
        final_date = max(backtest_results["date"])
        total_invested = backtest_results["amount"].sum()
        
        # Recreate final holdings
        holdings = {}
        for _, row in backtest_results.iterrows():
            key = f"{row['ticker']}_{row['market']}"
            if key in holdings:
                holdings[key]["shares"] += row["shares"]
                # Update average price
                total_cost = holdings[key]["shares"] * holdings[key]["avg_price"] + row["amount"]
                holdings[key]["avg_price"] = total_cost / holdings[key]["shares"]
            else:
                holdings[key] = {"shares": row["shares"], "avg_price": row["price"]}
        
        # Calculate final portfolio value
        final_portfolio_value = 0.0
        for key, holding in holdings.items():
            ticker, market = key.split("_", 1)
            final_price = self.get_price_at_date(ticker_data[market][ticker], final_date)
            if final_price:
                final_portfolio_value += holding["shares"] * final_price
        
        # Calculate metrics
        total_return = final_portfolio_value - total_invested
        total_return_pct = (total_return / total_invested) * 100 if total_invested > 0 else 0
        
        # Calculate annualized return
        start_date = min(backtest_results["date"])
        years = (final_date - start_date).days / 365.25
        annualized_return = ((final_portfolio_value / total_invested) ** (1/years) - 1) * 100 if years > 0 and total_invested > 0 else 0
        
        # Calculate dollar-cost averaging comparison
        dca_result = self._simulate_dca_backtest(ticker_data, backtest_results["date"].unique())
        
        metrics = {
            "total_invested": total_invested,
            "final_portfolio_value": final_portfolio_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "annualized_return_pct": annualized_return,
            "investment_period_years": years,
            "number_of_investments": len(backtest_results),
            "unique_tickers": len(set(backtest_results["ticker"] + "_" + backtest_results["market"])),
            "dca_comparison": dca_result,
            "outperformance_vs_dca": total_return - dca_result.get("total_return", 0)
        }
        
        return metrics
    
    def _simulate_dca_backtest(self, ticker_data: Dict[str, Dict[str, pd.DataFrame]], 
                              investment_dates: List[date]) -> Dict[str, Any]:
        """Simulate dollar-cost averaging for comparison."""
        monthly_budget = self.config.get("monthly_budget", 2000.0)
        
        # Count total tickers
        total_tickers = sum(len(tickers) for tickers in ticker_data.values())
        amount_per_ticker = monthly_budget / total_tickers if total_tickers > 0 else 0
        
        dca_holdings = {}
        total_dca_invested = 0.0
        
        for investment_date in investment_dates:
            for market, tickers in ticker_data.items():
                for ticker, df in tickers.items():
                    price = self.get_price_at_date(df, investment_date)
                    if price and price > 0:
                        shares = amount_per_ticker / price
                        key = f"{ticker}_{market}"
                        
                        if key in dca_holdings:
                            dca_holdings[key]["shares"] += shares
                        else:
                            dca_holdings[key] = {"shares": shares}
                        
                        total_dca_invested += amount_per_ticker
        
        # Calculate final DCA portfolio value
        final_date = max(investment_dates)
        final_dca_value = 0.0
        
        for key, holding in dca_holdings.items():
            ticker, market = key.split("_", 1)
            final_price = self.get_price_at_date(ticker_data[market][ticker], final_date)
            if final_price:
                final_dca_value += holding["shares"] * final_price
        
        dca_return = final_dca_value - total_dca_invested
        
        return {
            "strategy": "dollar_cost_averaging",
            "total_invested": total_dca_invested,
            "final_value": final_dca_value,
            "total_return": dca_return,
            "return_pct": (dca_return / total_dca_invested) * 100 if total_dca_invested > 0 else 0
        }