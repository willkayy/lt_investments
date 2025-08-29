import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


class MeanReversionScorer:
    """Mean reversion scoring model - buy when assets are oversold relative to their trend."""
    
    def __init__(self, config: Dict[str, Any]):
        self.lookback_days = config.get("lookback_days", 90)
        # Optimized mean reversion weights for better DCA outperformance
        self.weights = {
            "oversold_score": 0.7,     # Increased focus on oversold conditions
            "quality_filter": 0.2,     # Reduced quality filter weight
            "volatility_bonus": 0.1    # Reduced volatility bonus
        }
    
    def calculate_oversold_score(self, df: pd.DataFrame) -> float:
        """
        Calculate oversold score - higher when price is significantly below trend.
        """
        if len(df) < 30:
            return 0.0
        
        current_price = df.iloc[-1]["adjusted_close"]
        
        # Calculate multiple moving averages for trend reference
        ma_20 = df.tail(20)["adjusted_close"].mean()
        ma_50 = df.tail(min(50, len(df)))["adjusted_close"].mean()
        
        # Long-term trend line (best fit)
        if len(df) >= 60:
            prices = df.tail(60)["adjusted_close"]
            x = np.arange(len(prices))
            trend_slope, trend_intercept = np.polyfit(x, prices, 1)
            trend_price = trend_slope * (len(prices) - 1) + trend_intercept
        else:
            trend_price = ma_50
        
        # Score based on distance below moving averages
        score = 0.0
        
        # Distance below MA20 (short-term oversold)
        if current_price < ma_20:
            ma20_discount = (ma_20 - current_price) / ma_20
            score += min(ma20_discount * 3, 0.4)  # Cap at 40% of score
        
        # Distance below MA50 (medium-term oversold)
        if current_price < ma_50:
            ma50_discount = (ma_50 - current_price) / ma_50
            score += min(ma50_discount * 2, 0.3)  # Cap at 30% of score
        
        # Distance below trend line
        if current_price < trend_price:
            trend_discount = (trend_price - current_price) / trend_price
            score += min(trend_discount * 2, 0.3)  # Cap at 30% of score
        
        # Bonus for multiple timeframe oversold
        oversold_signals = 0
        if current_price < ma_20:
            oversold_signals += 1
        if current_price < ma_50:
            oversold_signals += 1
        if current_price < trend_price:
            oversold_signals += 1
        
        if oversold_signals >= 2:
            score *= 1.2
        
        return max(0.0, min(1.0, score))
    
    def calculate_quality_filter(self, df: pd.DataFrame) -> float:
        """
        Quality filter to avoid broken/falling knife stocks.
        """
        if len(df) < 30:
            return 0.0
        
        # Calculate recent returns
        returns = df["adjusted_close"].pct_change().fillna(0)
        
        # Long-term return (avoid secular decliners)
        if len(df) >= 60:
            long_term_return = (df.iloc[-1]["adjusted_close"] / df.iloc[-61]["adjusted_close"]) - 1
        else:
            long_term_return = (df.iloc[-1]["adjusted_close"] / df.iloc[0]["adjusted_close"]) - 1
        
        # Recent extreme moves (avoid panic selling)
        recent_min_return = returns.tail(5).min()
        recent_max_decline = (df.tail(10)["adjusted_close"].max() - df.iloc[-1]["adjusted_close"]) / df.tail(10)["adjusted_close"].max()
        
        score = 1.0  # Start with perfect quality
        
        # Penalize extreme recent declines (potential fundamental issues)
        if recent_max_decline > 0.25:  # >25% drop in 10 days
            score *= 0.2  # Heavy penalty
        elif recent_max_decline > 0.15:  # >15% drop in 10 days
            score *= 0.5  # Moderate penalty
        elif recent_max_decline > 0.10:  # >10% drop in 10 days
            score *= 0.7  # Light penalty
        
        # Penalize extreme single-day moves (news/fundamental issues)
        if recent_min_return < -0.15:  # >15% single day drop
            score *= 0.3
        elif recent_min_return < -0.10:  # >10% single day drop
            score *= 0.6
        
        # Penalize long-term secular decline
        if long_term_return < -0.30:  # >30% decline over period
            score *= 0.4
        elif long_term_return < -0.20:  # >20% decline over period
            score *= 0.7
        
        # Volume confirmation (ensure not just thin trading)
        recent_vol = df.tail(10)["volume"].mean()
        avg_vol = df["volume"].mean()
        if recent_vol < avg_vol * 0.5:  # Very low recent volume
            score *= 0.8
        
        return max(0.0, min(1.0, score))
    
    def calculate_volatility_bonus(self, df: pd.DataFrame) -> float:
        """
        Volatility bonus - higher volatility stocks have more mean reversion potential.
        """
        if len(df) < 20:
            return 0.0
        
        # Calculate volatility
        returns = df["adjusted_close"].pct_change().fillna(0)
        volatility = returns.tail(30).std() if len(df) >= 30 else returns.std()
        
        # Normalize volatility (higher vol = higher score)
        # But cap to avoid extreme risk
        vol_score = min(volatility * 15, 1.0)  # Scale and cap
        
        return vol_score
    
    def calculate_final_score(self, df: pd.DataFrame) -> Tuple[float, Dict[str, float]]:
        """
        Calculate final weighted score and return component breakdown.
        """
        if df is None or len(df) == 0:
            return 0.0, {}
        
        # Calculate individual components
        oversold_score = self.calculate_oversold_score(df)
        quality_filter = self.calculate_quality_filter(df)
        volatility_bonus = self.calculate_volatility_bonus(df)
        
        # Calculate weighted final score
        final_score = (
            oversold_score * self.weights["oversold_score"] +
            quality_filter * self.weights["quality_filter"] +
            volatility_bonus * self.weights["volatility_bonus"]
        )
        
        # Quality filter acts as a multiplicative filter
        final_score *= quality_filter
        
        components = {
            "oversold_score": oversold_score,
            "quality_filter": quality_filter,
            "volatility_bonus": volatility_bonus,
            "final_score": final_score
        }
        
        return final_score, components
    
    def score_ticker(self, ticker: str, market: str, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Score a single ticker and return detailed results.
        """
        if price_data is None or len(price_data) == 0:
            logger.warning(f"No price data available for {ticker}")
            return {
                "ticker": ticker,
                "market": market,
                "score": 0.0,
                "components": {},
                "current_price": None,
                "error": "No price data available"
            }
        
        # Use only the lookback period
        lookback_data = price_data.tail(self.lookback_days)
        
        final_score, components = self.calculate_final_score(lookback_data)
        
        return {
            "ticker": ticker,
            "market": market,
            "score": final_score,
            "components": components,
            "current_price": float(lookback_data.iloc[-1]["adjusted_close"]),
            "date": lookback_data.iloc[-1]["date"],
            "data_points": len(lookback_data)
        }
    
    def score_multiple_tickers(self, ticker_data: Dict[str, Dict[str, pd.DataFrame]]) -> pd.DataFrame:
        """
        Score multiple tickers and return sorted results.
        """
        results = []
        
        for market, tickers in ticker_data.items():
            for ticker, df in tickers.items():
                result = self.score_ticker(ticker, market, df)
                results.append(result)
        
        # Convert to DataFrame
        scores_df = pd.DataFrame(results)
        
        # Sort by score descending if we have results
        if len(scores_df) > 0 and "score" in scores_df.columns:
            scores_df = scores_df.sort_values("score", ascending=False)
        
        logger.info(f"Scored {len(results)} tickers")
        return scores_df