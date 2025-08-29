# Long-Term Investment Alert System - Technical Specification

## Overview

A Python-based investment alert system that identifies optimal buying opportunities for stocks and ETFs by analyzing price patterns over a 90-day lookback period. The system aims to outperform dollar-cost averaging by concentrating purchases when securities are relatively undervalued.

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Config File   │    │   Data Source   │    │  CSV Storage    │
│   (YAML/JSON)   │    │   (Alpha Vantage│    │   (Historical)  │
└─────────────────┘    │    + Others)    │    └─────────────────┘
         │              └─────────────────┘              │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Core Engine                                 │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │ Data Manager  │  │ Score Model   │  │ Portfolio     │      │
│  │               │  │               │  │ Allocator     │      │
│  └───────────────┘  └───────────────┘  └───────────────┘      │
└─────────────────────────────────────────────────────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Backtesting     │    │ Alert Generator │    │ Reporting       │
│ Framework       │    │ (Future)        │    │ Dashboard       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Investment Algorithm

### Core Principle: Relative Value Scoring

The system identifies buying opportunities when stocks are trading at relatively low levels compared to their recent 90-day performance, allocating more budget to securities with higher "value" scores.

### Scoring Model Components:

1. **Price Position Score (40% weight)**
   - Current price percentile within 90-day range
   - Formula: `(max_90d - current) / (max_90d - min_90d)`

2. **Momentum Decay Score (30% weight)**
   - Measures how long the stock has been declining
   - Rewards sustained weakness (contrarian approach)

3. **Volatility-Adjusted Score (20% weight)**
   - Adjusts for stock's inherent volatility
   - Uses 90-day standard deviation normalization

4. **Volume Confirmation Score (10% weight)**
   - Confirms genuine selling pressure vs. low-volume drift
   - Higher volume during declines = higher score

### Final Allocation Formula:
```
allocation_percentage = (stock_score / total_all_scores) * monthly_budget
minimum_allocation = monthly_budget * 0.05  # 5% minimum per tracked stock
```

## Data Models & Storage

### CSV File Structure:

#### `data/prices/{TICKER}_{MARKET}.csv`
```csv
date,open,high,low,close,volume,adjusted_close
2024-01-01,150.25,152.30,149.50,151.75,1000000,151.75
```

#### `data/scores/{TICKER}_{MARKET}_scores.csv`
```csv
date,price_position,momentum_decay,volatility_adj,volume_conf,final_score,allocation_pct
2024-01-01,0.75,0.60,0.80,0.70,0.71,12.5
```

#### `data/backtests/backtest_{YYYY-MM-DD}_{HH-MM}.csv`
```csv
test_date,ticker,market,score,allocation,price,shares,total_invested,cumulative_value
2024-01-01,AAPL,US,0.75,500.00,150.25,3.33,500.00,500.83
```

### Directory Structure:
```
lt_investments/
├── config/
│   ├── settings.yaml
│   └── tickers.yaml
├── src/
│   ├── data/
│   │   ├── api_client.py
│   │   └── data_manager.py
│   ├── models/
│   │   ├── scorer.py
│   │   └── allocator.py
│   ├── backtesting/
│   │   ├── engine.py
│   │   └── metrics.py
│   └── utils/
│       └── helpers.py
├── data/
│   ├── prices/
│   ├── scores/
│   └── backtests/
└── tests/
```

## Configuration System

### `config/settings.yaml`
```yaml
# Investment Settings
monthly_budget: 2000.0
minimum_allocation_pct: 5.0
lookback_days: 90

# Model Parameters (tunable)
scoring_weights:
  price_position: 0.4
  momentum_decay: 0.3
  volatility_adjusted: 0.2
  volume_confirmation: 0.1

momentum_decay_factor: 0.95
volatility_window: 30

# Data Sources
primary_api: "alpha_vantage"
api_keys:
  alpha_vantage: "${ALPHA_VANTAGE_API_KEY}"

# Markets
supported_markets: ["US", "AU"]
market_configs:
  US:
    currency: "USD"
    timezone: "America/New_York"
  AU:
    currency: "AUD"
    timezone: "Australia/Sydney"

# Backtesting
backtest_start_date: "2023-01-01"
backtest_end_date: "2024-01-01"
```

### `config/tickers.yaml`
```yaml
tickers:
  US:
    stocks:
      - AAPL
      - GOOGL
      - MSFT
      - TSLA
    etfs:
      - SPY
      - QQQ
      - VTI
  AU:
    stocks:
      - CBA.AX
      - BHP.AX
      - CSL.AX
    etfs:
      - VAS.AX
      - VGS.AX
```

## API Abstraction Layer

### `src/data/api_client.py`
```python
class APIClient(ABC):
    @abstractmethod
    def get_historical_data(self, ticker: str, period: str) -> pd.DataFrame:
        pass
    
    @abstractmethod
    def get_current_price(self, ticker: str) -> float:
        pass

class AlphaVantageClient(APIClient):
    # Implementation for Alpha Vantage
    
class YahooFinanceClient(APIClient):
    # Future implementation for Yahoo Finance
```

## Backtesting Framework

### Performance Metrics:
1. **Total Return**: Final portfolio value vs. initial investment
2. **Annualized Return**: Compound annual growth rate
3. **Sharpe Ratio**: Risk-adjusted return
4. **Maximum Drawdown**: Largest peak-to-trough decline
5. **Win Rate**: Percentage of profitable investments
6. **Dollar-Cost Averaging Comparison**: Direct comparison baseline
7. **Volatility**: Standard deviation of monthly returns
8. **Sortino Ratio**: Downside risk-adjusted return

### Backtesting Process:
1. Load historical data for all tickers (1+ years)
2. For each month in backtest period:
   - Calculate scores for all tracked securities
   - Determine allocation based on scores
   - Simulate purchases at month-end prices
   - Track cumulative portfolio value
3. Calculate performance metrics
4. Generate comparison vs. dollar-cost averaging

## Implementation Phases

### Phase 1: Core Data & Scoring (Week 1-2)
- [ ] Set up project structure
- [ ] Implement Alpha Vantage API client
- [ ] Create CSV data storage system
- [ ] Build basic scoring model
- [ ] Configuration management

### Phase 2: Backtesting Engine (Week 3-4)
- [ ] Historical data collection
- [ ] Backtesting framework
- [ ] Performance metrics calculation
- [ ] Basic reporting dashboard

### Phase 3: Optimization & Testing (Week 5-6)
- [ ] Parameter tuning interface
- [ ] 80/20 train/test split functionality
- [ ] Model validation
- [ ] Performance optimization

### Phase 4: Alert System (Future)
- [ ] Real-time data monitoring
- [ ] Alert delivery mechanisms
- [ ] Cloud deployment preparation

## Key Dependencies

```
pandas>=1.5.0
numpy>=1.24.0
requests>=2.28.0
pyyaml>=6.0
matplotlib>=3.6.0
seaborn>=0.12.0
alpha-vantage>=2.3.0
pytest>=7.0.0
```

## Risk Considerations

1. **API Rate Limits**: Alpha Vantage free tier has 5 calls/minute, 500 calls/day
2. **Data Quality**: Market holidays, stock splits, dividends need handling
3. **Currency Conversion**: AU/US market comparison requires FX rates
4. **Survivorship Bias**: Backtesting only on currently listed securities
5. **Transaction Costs**: Not modeled initially, but should be added

## Success Criteria

- System consistently outperforms dollar-cost averaging in backtests
- < 2% maximum difference in monthly allocation calculations
- Sub-5 second execution time for monthly scoring
- 99%+ data accuracy compared to reference sources
- Extensible architecture for future enhancements