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

- **Update price data**: `uv run python main.py update-data [--force]`
- **Score current opportunities**: `uv run python main.py score [--top N] [--save]`
- **Calculate allocation**: `uv run python main.py allocate`
- **Run backtest**: `uv run python main.py backtest [--update-data] [--name TESTNAME]`

Or use the installed script:
- **Direct command**: `uv run lt-investments score --top 5`

## Architecture

See `TECHNICAL_SPECIFICATION.md` for complete system design.

## Key Features

- **Multi-market support** (US, AU)
- **CSV-based data storage**
- **Comprehensive backtesting** with performance metrics
- **Configurable scoring model** with 4 components
- **API abstraction** for easy data source switching

## Development

- **Install dev dependencies**: `uv sync --extra dev`
- **Test**: `uv run pytest tests/ -v`
- **Lint**: `uv run ruff check src/ tests/`
- **Type check**: `uv run mypy src/`
- **Format**: `uv run ruff format src/ tests/`

## Project Status

✅ **MVP Complete** - Ready for backtesting and investment analysis