import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string."""
    if currency == "USD":
        return f"${amount:,.2f}"
    elif currency == "AUD":
        return f"A${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def format_percentage(value: float, decimal_places: int = 1) -> str:
    """Format value as percentage string."""
    return f"{value:.{decimal_places}f}%"


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio for a returns series."""
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    
    excess_return = returns.mean() - risk_free_rate / 252  # Daily risk-free rate
    return excess_return / returns.std() * np.sqrt(252)  # Annualized


def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Calculate Sortino ratio (downside risk-adjusted return)."""
    if len(returns) == 0:
        return 0.0
    
    excess_return = returns.mean() - risk_free_rate / 252
    downside_returns = returns[returns < 0]
    
    if len(downside_returns) == 0:
        return float('inf') if excess_return > 0 else 0.0
    
    downside_std = downside_returns.std()
    if downside_std == 0:
        return float('inf') if excess_return > 0 else 0.0
    
    return excess_return / downside_std * np.sqrt(252)


def calculate_max_drawdown(portfolio_values: pd.Series) -> Dict[str, float]:
    """Calculate maximum drawdown and related metrics."""
    if len(portfolio_values) == 0:
        return {"max_drawdown": 0.0, "max_drawdown_pct": 0.0}
    
    # Calculate running maximum
    running_max = portfolio_values.expanding().max()
    
    # Calculate drawdown
    drawdown = portfolio_values - running_max
    drawdown_pct = (drawdown / running_max) * 100
    
    max_drawdown = drawdown.min()
    max_drawdown_pct = drawdown_pct.min()
    
    return {
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct
    }


def create_performance_summary(metrics: Dict[str, Any]) -> str:
    """Create a formatted performance summary string."""
    lines = []
    lines.append("=" * 60)
    lines.append("INVESTMENT PERFORMANCE SUMMARY")
    lines.append("=" * 60)
    
    # Basic metrics
    lines.append("\nInvestment Summary:")
    lines.append(f"  Total Invested: {format_currency(metrics.get('total_invested', 0))}")
    lines.append(f"  Final Portfolio Value: {format_currency(metrics.get('final_portfolio_value', 0))}")
    lines.append(f"  Total Return: {format_currency(metrics.get('total_return', 0))}")
    lines.append(f"  Total Return %: {format_percentage(metrics.get('total_return_pct', 0))}")
    lines.append(f"  Annualized Return %: {format_percentage(metrics.get('annualized_return_pct', 0))}")
    
    # Investment details
    lines.append(f"\nInvestment Details:")
    lines.append(f"  Investment Period: {metrics.get('investment_period_years', 0):.1f} years")
    lines.append(f"  Number of Investments: {metrics.get('number_of_investments', 0)}")
    lines.append(f"  Unique Tickers: {metrics.get('unique_tickers', 0)}")
    
    # Comparison with DCA
    if "dca_comparison" in metrics:
        dca = metrics["dca_comparison"]
        lines.append(f"\nDollar-Cost Averaging Comparison:")
        lines.append(f"  DCA Total Return: {format_currency(dca.get('total_return', 0))}")
        lines.append(f"  DCA Return %: {format_percentage(dca.get('return_pct', 0))}")
        lines.append(f"  Outperformance vs DCA: {format_currency(metrics.get('outperformance_vs_dca', 0))}")
    
    lines.append("=" * 60)
    
    return "\n".join(lines)


def validate_ticker_format(ticker: str, market: str) -> bool:
    """Validate ticker format for different markets."""
    if not ticker or not market:
        return False
    
    if market == "AU":
        # Australian tickers should end with .AX
        return ticker.endswith(".AX")
    elif market == "US":
        # US tickers shouldn't have a suffix
        return "." not in ticker
    
    # For unknown markets, just check it's not empty
    return len(ticker.strip()) > 0


def clean_ticker_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and validate ticker data."""
    if df is None or len(df) == 0:
        return df
    
    # Remove rows with missing critical data
    df_clean = df.dropna(subset=["close", "volume"])
    
    # Remove rows with zero or negative prices
    df_clean = df_clean[df_clean["close"] > 0]
    
    # Remove rows with zero volume (likely market holidays)
    df_clean = df_clean[df_clean["volume"] > 0]
    
    # Sort by date
    df_clean = df_clean.sort_values("date")
    
    # Remove duplicates
    df_clean = df_clean.drop_duplicates(subset=["date"])
    
    if len(df_clean) < len(df):
        logger.info(f"Cleaned ticker data: {len(df)} -> {len(df_clean)} rows")
    
    return df_clean.reset_index(drop=True)


def generate_ticker_summary(scores_df: pd.DataFrame, top_n: int = 10) -> str:
    """Generate a summary of ticker scores."""
    if len(scores_df) == 0:
        return "No ticker data available"
    
    lines = []
    lines.append(f"\nTop {min(top_n, len(scores_df))} Investment Opportunities:")
    lines.append("-" * 80)
    lines.append(f"{'Ticker':<15} {'Market':<8} {'Score':<8} {'Price':<10} {'Components'}")
    lines.append("-" * 80)
    
    for _, row in scores_df.head(top_n).iterrows():
        components = row.get("components", {})
        comp_str = f"P:{components.get('price_position', 0):.2f} M:{components.get('momentum_decay', 0):.2f} V:{components.get('volatility_adjusted', 0):.2f} Vol:{components.get('volume_confirmation', 0):.2f}"
        
        lines.append(f"{row['ticker']:<15} {row['market']:<8} {row['score']:<8.3f} {format_currency(row.get('current_price', 0)):<10} {comp_str}")
    
    return "\n".join(lines)


def export_to_csv(data: pd.DataFrame, filepath: str, include_timestamp: bool = True) -> bool:
    """Export DataFrame to CSV with optional timestamp."""
    try:
        if include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = filepath.replace(".csv", f"_{timestamp}.csv")
        
        data.to_csv(filepath, index=False)
        logger.info(f"Data exported to {filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}")
        return False


def load_from_csv(filepath: str, date_columns: Optional[List[str]] = None) -> Optional[pd.DataFrame]:
    """Load DataFrame from CSV with date parsing."""
    try:
        df = pd.read_csv(filepath)
        
        if date_columns:
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col]).dt.date
        
        logger.info(f"Loaded {len(df)} rows from {filepath}")
        return df
        
    except Exception as e:
        logger.error(f"Error loading from CSV: {e}")
        return None