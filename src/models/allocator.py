import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)


class PortfolioAllocator:
    """Allocates monthly budget based on stock scores."""
    
    def __init__(self, config: Dict[str, Any]):
        self.monthly_budget = config.get("monthly_budget", 2000.0)
        self.min_allocation_pct = config.get("minimum_allocation_pct", 5.0) / 100.0
        self.min_allocation_amount = self.monthly_budget * self.min_allocation_pct
    
    def calculate_allocations(self, scores_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate budget allocation for each ticker based on scores.
        
        Args:
            scores_df: DataFrame with columns ['ticker', 'market', 'score', 'current_price']
        
        Returns:
            DataFrame with allocation details
        """
        if len(scores_df) == 0:
            logger.warning("No scores provided for allocation")
            return pd.DataFrame()
        
        # Filter out tickers with errors or zero scores
        valid_scores = scores_df[
            (scores_df["score"] > 0) & 
            (scores_df["current_price"].notna()) &
            (~scores_df.get("error", "").notna())
        ].copy()
        
        if len(valid_scores) == 0:
            logger.warning("No valid scores for allocation")
            return pd.DataFrame()
        
        # Calculate total score
        total_score = valid_scores["score"].sum()
        
        if total_score == 0:
            logger.warning("Total score is zero, using equal allocation")
            allocation_pct = 1.0 / len(valid_scores)
            valid_scores["allocation_pct"] = allocation_pct
        else:
            # Calculate proportional allocation based on scores
            valid_scores["allocation_pct"] = valid_scores["score"] / total_score
        
        # Apply minimum allocation constraint
        n_tickers = len(valid_scores)
        max_budget_for_min = self.min_allocation_pct * n_tickers
        
        if max_budget_for_min > 1.0:
            # Too many tickers for minimum allocation - adjust minimum
            adjusted_min_pct = 0.8 / n_tickers  # Use 80% of budget for equal minimums
            logger.warning(f"Too many tickers ({n_tickers}), adjusting minimum to {adjusted_min_pct:.1%}")
        else:
            adjusted_min_pct = self.min_allocation_pct
        
        # Ensure minimum allocation
        valid_scores.loc[valid_scores["allocation_pct"] < adjusted_min_pct, "allocation_pct"] = adjusted_min_pct
        
        # Renormalize to ensure total doesn't exceed 100%
        total_allocation = valid_scores["allocation_pct"].sum()
        if total_allocation > 1.0:
            valid_scores["allocation_pct"] = valid_scores["allocation_pct"] / total_allocation
        
        # Calculate dollar amounts
        valid_scores["allocation_amount"] = valid_scores["allocation_pct"] * self.monthly_budget
        valid_scores["shares"] = valid_scores["allocation_amount"] / valid_scores["current_price"]
        valid_scores["shares"] = valid_scores["shares"].round(2)  # Round to 2 decimal places
        
        # Recalculate actual amount based on rounded shares
        valid_scores["actual_amount"] = valid_scores["shares"] * valid_scores["current_price"]
        
        logger.info(f"Allocated ${valid_scores['actual_amount'].sum():.2f} across {len(valid_scores)} tickers")
        
        return valid_scores.sort_values("allocation_amount", ascending=False)
    
    def simulate_dollar_cost_averaging(self, ticker_data: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, Any]:
        """
        Simulate dollar-cost averaging strategy for comparison.
        
        Args:
            ticker_data: Dict with structure {market: {ticker: dataframe}}
        """
        # Count total tickers
        total_tickers = sum(len(tickers) for tickers in ticker_data.values())
        
        if total_tickers == 0:
            return {"total_amount": 0, "per_ticker": 0, "strategy": "dollar_cost_averaging"}
        
        amount_per_ticker = self.monthly_budget / total_tickers
        
        allocations = []
        for market, tickers in ticker_data.items():
            for ticker, df in tickers.items():
                if df is not None and len(df) > 0:
                    current_price = float(df.iloc[-1]["close"])
                    shares = amount_per_ticker / current_price
                    
                    allocations.append({
                        "ticker": ticker,
                        "market": market,
                        "allocation_amount": amount_per_ticker,
                        "current_price": current_price,
                        "shares": round(shares, 2),
                        "actual_amount": shares * current_price
                    })
        
        total_invested = sum(alloc["actual_amount"] for alloc in allocations)
        
        return {
            "allocations": allocations,
            "total_amount": total_invested,
            "per_ticker": amount_per_ticker,
            "strategy": "dollar_cost_averaging",
            "num_tickers": len(allocations)
        }
    
    def compare_strategies(self, scores_df: pd.DataFrame, ticker_data: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, Any]:
        """
        Compare score-based allocation vs dollar-cost averaging.
        """
        # Score-based allocation
        score_allocation = self.calculate_allocations(scores_df)
        
        # Dollar-cost averaging
        dca_allocation = self.simulate_dollar_cost_averaging(ticker_data)
        
        # Calculate concentration metrics
        score_based_concentration = self._calculate_concentration(score_allocation)
        
        return {
            "score_based": {
                "allocations": score_allocation,
                "total_invested": score_allocation["actual_amount"].sum() if len(score_allocation) > 0 else 0,
                "concentration": score_based_concentration,
                "num_positions": len(score_allocation)
            },
            "dollar_cost_averaging": dca_allocation,
            "budget": self.monthly_budget
        }
    
    def _calculate_concentration(self, allocations_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate concentration metrics for allocation."""
        if len(allocations_df) == 0:
            return {"herfindahl_index": 0, "max_allocation": 0, "top_3_concentration": 0}
        
        allocation_pcts = allocations_df["allocation_pct"]
        
        # Herfindahl-Hirschman Index (sum of squared percentages)
        hhi = (allocation_pcts ** 2).sum()
        
        # Maximum single allocation
        max_allocation = allocation_pcts.max()
        
        # Top 3 concentration
        top_3_concentration = allocation_pcts.nlargest(3).sum()
        
        return {
            "herfindahl_index": hhi,
            "max_allocation": max_allocation,
            "top_3_concentration": top_3_concentration
        }
    
    def generate_allocation_summary(self, comparison_result: Dict[str, Any]) -> str:
        """Generate human-readable summary of allocation comparison."""
        score_data = comparison_result["score_based"]
        dca_data = comparison_result["dollar_cost_averaging"]
        
        summary = []
        summary.append(f"Monthly Budget: ${comparison_result['budget']:,.2f}")
        summary.append("")
        
        # Score-based allocation
        summary.append("Score-Based Allocation:")
        summary.append(f"  Total Invested: ${score_data['total_invested']:,.2f}")
        summary.append(f"  Number of Positions: {score_data['num_positions']}")
        
        if len(score_data["allocations"]) > 0:
            concentration = score_data["concentration"]
            summary.append(f"  Concentration (HHI): {concentration['herfindahl_index']:.3f}")
            summary.append(f"  Largest Position: {concentration['max_allocation']:.1%}")
            
            summary.append("\n  Top Allocations:")
            for _, row in score_data["allocations"].head(5).iterrows():
                summary.append(f"    {row['ticker']} ({row['market']}): ${row['actual_amount']:.2f} ({row['allocation_pct']:.1%}) - Score: {row['score']:.3f}")
        
        summary.append("")
        
        # Dollar-cost averaging
        summary.append("Dollar-Cost Averaging:")
        summary.append(f"  Total Invested: ${dca_data['total_amount']:,.2f}")
        summary.append(f"  Per Ticker: ${dca_data['per_ticker']:,.2f}")
        summary.append(f"  Number of Positions: {dca_data['num_tickers']}")
        
        return "\n".join(summary)