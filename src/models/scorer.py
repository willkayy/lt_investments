import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)


class InvestmentScorer:
    """Core scoring model that identifies buying opportunities."""
    
    def __init__(self, config: Dict[str, Any]):
        self.lookback_days = config.get("lookback_days", 90)
        self.weights = config.get("scoring_weights", {
            "price_position": 0.4,
            "momentum_decay": 0.3,
            "volatility_adjusted": 0.2,
            "volume_confirmation": 0.1
        })
        self.momentum_decay_factor = config.get("momentum_decay_factor", 0.95)
        self.volatility_window = config.get("volatility_window", 30)
    
    def calculate_price_position_score(self, df: pd.DataFrame) -> float:
        """
        Calculate price position score (40% weight).
        Higher score = current price is lower in the 90-day range.
        """
        if len(df) < 2:
            return 0.0
        
        current_price = df.iloc[-1]["close"]
        high_90d = df["high"].max()
        low_90d = df["low"].min()
        
        if high_90d == low_90d:
            return 0.5  # No movement, neutral score
        
        # Score is higher when current price is closer to the low
        position_score = (high_90d - current_price) / (high_90d - low_90d)
        return max(0.0, min(1.0, position_score))
    
    def calculate_momentum_decay_score(self, df: pd.DataFrame) -> float:
        """
        Calculate momentum decay score (30% weight).
        Rewards sustained weakness (contrarian approach).
        """
        if len(df) < 5:
            return 0.0
        
        # Calculate daily returns
        df_temp = df.copy()
        df_temp["returns"] = df_temp["close"].pct_change()
        
        # Count consecutive negative/positive days
        recent_returns = df_temp["returns"].tail(20).fillna(0)  # Last 20 days
        
        # Calculate weighted decay score
        score = 0.0
        weight = 1.0
        
        for ret in reversed(recent_returns):
            if ret < 0:  # Negative return (price declining)
                score += weight * abs(ret)
            else:  # Positive return reduces score
                score -= weight * ret * 0.5
            weight *= self.momentum_decay_factor
        
        # Normalize to 0-1 range
        return max(0.0, min(1.0, score / 2.0))
    
    def calculate_volatility_adjusted_score(self, df: pd.DataFrame) -> float:
        """
        Calculate volatility-adjusted score (20% weight).
        Adjusts for stock's inherent volatility.
        """
        if len(df) < self.volatility_window:
            return 0.0
        
        # Calculate rolling volatility
        df_temp = df.copy()
        df_temp["returns"] = df_temp["close"].pct_change()
        
        volatility = df_temp["returns"].std()
        if volatility == 0:
            return 0.5
        
        # Calculate recent price movement relative to volatility
        recent_change = (df.iloc[-1]["close"] - df.iloc[-5]["close"]) / df.iloc[-5]["close"]
        
        # Score is higher when recent decline is significant relative to normal volatility
        vol_adjusted_decline = abs(min(0, recent_change)) / volatility
        
        # Normalize using sigmoid-like function
        score = 2 / (1 + np.exp(-vol_adjusted_decline)) - 1
        return max(0.0, min(1.0, score))
    
    def calculate_volume_confirmation_score(self, df: pd.DataFrame) -> float:
        """
        Calculate volume confirmation score (10% weight).
        Higher volume during declines confirms genuine selling pressure.
        """
        if len(df) < 10:
            return 0.0
        
        df_temp = df.copy()
        df_temp["returns"] = df_temp["close"].pct_change()
        df_temp["volume_ma"] = df_temp["volume"].rolling(window=20, min_periods=5).mean()
        
        # Get recent data
        recent_data = df_temp.tail(10)
        
        volume_score = 0.0
        for _, row in recent_data.iterrows():
            if pd.isna(row["returns"]) or pd.isna(row["volume_ma"]):
                continue
                
            volume_ratio = row["volume"] / row["volume_ma"] if row["volume_ma"] > 0 else 1.0
            
            # High volume on down days increases score
            if row["returns"] < 0:
                volume_score += volume_ratio * abs(row["returns"])
            # High volume on up days slightly decreases score
            elif row["returns"] > 0:
                volume_score -= volume_ratio * row["returns"] * 0.3
        
        # Normalize to 0-1 range
        return max(0.0, min(1.0, volume_score / 5.0))
    
    def calculate_final_score(self, df: pd.DataFrame) -> Tuple[float, Dict[str, float]]:
        """
        Calculate final weighted score and return component breakdown.
        """
        if df is None or len(df) == 0:
            return 0.0, {}
        
        # Calculate individual components
        price_position = self.calculate_price_position_score(df)
        momentum_decay = self.calculate_momentum_decay_score(df)
        volatility_adj = self.calculate_volatility_adjusted_score(df)
        volume_conf = self.calculate_volume_confirmation_score(df)
        
        # Calculate weighted final score
        final_score = (
            price_position * self.weights["price_position"] +
            momentum_decay * self.weights["momentum_decay"] +
            volatility_adj * self.weights["volatility_adjusted"] +
            volume_conf * self.weights["volume_confirmation"]
        )
        
        components = {
            "price_position": price_position,
            "momentum_decay": momentum_decay,
            "volatility_adjusted": volatility_adj,
            "volume_confirmation": volume_conf,
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
            "current_price": float(lookback_data.iloc[-1]["close"]),
            "date": lookback_data.iloc[-1]["date"],
            "data_points": len(lookback_data)
        }
    
    def score_multiple_tickers(self, ticker_data: Dict[str, Dict[str, pd.DataFrame]]) -> pd.DataFrame:
        """
        Score multiple tickers and return sorted results.
        
        Args:
            ticker_data: Dict with structure {market: {ticker: dataframe}}
        """
        results = []
        
        for market, tickers in ticker_data.items():
            for ticker, df in tickers.items():
                result = self.score_ticker(ticker, market, df)
                results.append(result)
        
        # Convert to DataFrame
        scores_df = pd.DataFrame(results)
        
        # Sort by score descending
        scores_df = scores_df.sort_values("score", ascending=False)
        
        logger.info(f"Scored {len(results)} tickers")
        return scores_df