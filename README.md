# Long-Term Investment Alert System

A Python-based system that identifies optimal stock buying opportunities by analyzing price patterns over 90-day periods, designed to outperform dollar-cost averaging.

## Quick Start

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your Alpha Vantage API key
   ```

3. **Configure investments**:
   - Edit `config/settings.yaml` for budget and model parameters
   - Edit `config/tickers.yaml` for stocks/ETFs to track

4. **Update data and run backtest**:
   ```bash
   uv run python main.py update-data --force
   uv run python main.py backtest
   ```

## Usage Commands

### Main System
- **Update price data**: `uv run python main.py update-data [--force]`
- **Score current opportunities**: `uv run python main.py score [--top N] [--save]`
- **Calculate allocation**: `uv run python main.py allocate`
- **Run backtest**: `uv run python main.py backtest [--update-data] [--name TESTNAME]`

### Alert System Testing
- **Test current alerts**: `uv run python test_alerts.py`
- **Backtest alert history**: `uv run python test_alert_backtest.py`

Or use the installed script:
- **Direct command**: `uv run lt-investments score --top 5`

## Alert System

The alert system identifies buying opportunities using mean reversion analysis:

- **Scoring**: Uses oversold conditions, quality filters, and volatility analysis
- **Scheduling**: Generates monthly alerts on the 8th of each month
- **Performance**: Historical backtesting shows 5.7% average 90-day returns with 73% success rate
- **Threshold**: Only triggers alerts for scores ≥0.3 to ensure quality opportunities
- **Output**: Formatted for both plain text and Slack integration

Test the alert system:
```bash
# Test current alert generation
uv run python test_alerts.py

# View historical alert performance
uv run python test_alert_backtest.py
```

## Architecture

See `TECHNICAL_SPECIFICATION.md` for complete system design.

## Key Features

- **Multi-market support** (US, AU)
- **CSV-based data storage**
- **Comprehensive backtesting** with performance metrics
- **Alert system** with mean reversion scoring and monthly scheduling
- **Configurable scoring models** (reversion, complex)
- **Portfolio allocation** with diversification optimization
- **API abstraction** for easy data source switching

## Development

- **Install dev dependencies**: `uv sync --extra dev`
- **Test**: `uv run pytest tests/ -v`
- **Lint**: `uv run ruff check src/ tests/`
- **Type check**: `uv run mypy src/`
- **Format**: `uv run ruff format src/ tests/`

## Project Status

✅ **MVP Complete** - Ready for backtesting and investment analysis