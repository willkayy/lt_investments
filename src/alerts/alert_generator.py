import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, Any, List, Tuple
import logging

from ..models.reversion_scorer import MeanReversionScorer
from ..models.allocator import PortfolioAllocator

logger = logging.getLogger(__name__)


class InvestmentAlertGenerator:
    """Generates investment alerts based on scoring models."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.monthly_budget = config.get("monthly_budget", 2000.0)
        self.alert_threshold = config.get("alert_threshold", 0.3)  # Minimum score to trigger alert
        self.max_alerts = config.get("max_alerts_per_period", 8)
        
        # Initialize scoring and allocation models
        scoring_method = config.get("scoring_method", "reversion")
        if scoring_method == "reversion":
            self.scorer = MeanReversionScorer(config)
        else:
            from ..models.scorer import InvestmentScorer
            self.scorer = InvestmentScorer(config)
            
        self.allocator = PortfolioAllocator(config)
    
    def generate_alerts(self, ticker_data: Dict[str, Dict[str, pd.DataFrame]], 
                       alert_date: date) -> List[Dict[str, Any]]:
        """
        Generate investment alerts for a specific date.
        
        Args:
            ticker_data: Dict with structure {market: {ticker: dataframe}}
            alert_date: Date to generate alerts for
            
        Returns:
            List of alert dictionaries with buy recommendations
        """
        # Score all tickers
        scores_df = self.scorer.score_multiple_tickers(ticker_data)
        
        # Filter scores above threshold
        if len(scores_df) == 0 or "score" not in scores_df.columns:
            valid_alerts = pd.DataFrame()
        else:
            valid_alerts = scores_df[
                (scores_df["score"] >= self.alert_threshold) & 
                (scores_df["current_price"].notna())
            ].copy()
        
        if len(valid_alerts) == 0:
            logger.info(f"No alerts generated for {alert_date} - no scores above threshold {self.alert_threshold}")
            return []
        
        # Calculate allocations for valid alerts
        allocations_df = self.allocator.calculate_allocations(valid_alerts)
        
        # Generate alert messages
        alerts = []
        for _, row in allocations_df.iterrows():
            if row["actual_amount"] > 0:  # Only include tickers with actual allocation
                alert = self._create_alert_message(row, alert_date)
                alerts.append(alert)
        
        # Limit number of alerts
        alerts = alerts[:self.max_alerts]
        
        logger.info(f"Generated {len(alerts)} alerts for {alert_date}")
        return alerts
    
    def _create_alert_message(self, allocation_row: pd.Series, alert_date: date) -> Dict[str, Any]:
        """Create formatted alert message for a single investment opportunity."""
        ticker = allocation_row["ticker"]
        market = allocation_row["market"]
        score = allocation_row["score"]
        price = allocation_row["current_price"]
        amount = allocation_row["actual_amount"]
        shares = allocation_row["shares"]
        allocation_pct = allocation_row["allocation_pct"]
        
        # Get component scores if available
        components = allocation_row.get("components", {})
        
        # Create human-readable message
        market_suffix = f" ({market})" if market != "US" else ""
        
        alert_message = {
            "timestamp": datetime.combine(alert_date, datetime.min.time()),
            "alert_date": alert_date,
            "ticker": ticker,
            "market": market,
            "action": "BUY",
            "price": round(price, 2),
            "shares": round(shares, 2),
            "amount": round(amount, 2),
            "allocation_percentage": round(allocation_pct * 100, 1),
            "score": round(score, 3),
            "components": components,
            "message": self._format_alert_text(ticker, market_suffix, price, shares, amount, score),
            "slack_message": self._format_slack_message(ticker, market_suffix, price, shares, amount, score, components)
        }
        
        return alert_message
    
    def _format_alert_text(self, ticker: str, market_suffix: str, price: float, 
                          shares: float, amount: float, score: float) -> str:
        """Format alert as plain text message (SMS-style)."""
        return (
            f"🔔 BUY ALERT: {ticker}{market_suffix}\n"
            f"💰 ${price:.2f} × {shares:.2f} shares = ${amount:.2f}\n"
            f"📊 Score: {score:.3f}\n"
            f"⏰ {datetime.now().strftime('%H:%M %Z')}"
        )
    
    def _format_slack_message(self, ticker: str, market_suffix: str, price: float,
                             shares: float, amount: float, score: float,
                             components: Dict[str, float]) -> Dict[str, Any]:
        """Format alert as Slack message with rich formatting."""
        
        # Create component breakdown if available
        component_text = ""
        if components:
            component_text = "\n*Score Breakdown:*\n"
            for key, value in components.items():
                if key != "final_score":
                    formatted_key = key.replace("_", " ").title()
                    component_text += f"• {formatted_key}: {value:.3f}\n"
        
        slack_message = {
            "text": f"Investment Alert: {ticker}{market_suffix}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🔔 Buy Alert: {ticker}{market_suffix}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Price:*\n${price:.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Shares:*\n{shares:.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Amount:*\n${amount:.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Score:*\n{score:.3f}"
                        }
                    ]
                }
            ]
        }
        
        # Add component breakdown if available
        if component_text:
            slack_message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": component_text
                }
            })
        
        # Add timestamp
        slack_message["blocks"].append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏰ Alert generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}"
                }
            ]
        })
        
        return slack_message
    
    def should_generate_alerts(self, alert_date: date) -> bool:
        """
        Determine if alerts should be generated for a specific date.
        Default: Generate monthly alerts on the 8th of each month (matching backtest schedule).
        """
        return alert_date.day == 8
    
    def get_alert_schedule_dates(self, start_date: date, end_date: date) -> List[date]:
        """Get all dates when alerts should be generated in a date range."""
        from dateutil.relativedelta import relativedelta
        
        alert_dates = []
        current_date = start_date.replace(day=8)  # Start on 8th of month
        
        # Adjust if start date is after the 8th
        if start_date.day > 8:
            current_date = current_date + relativedelta(months=1)
        
        while current_date <= end_date:
            alert_dates.append(current_date)
            current_date = current_date + relativedelta(months=1)
        
        return alert_dates