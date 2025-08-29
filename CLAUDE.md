# Claude Code Configuration for LT Investments

## Project Overview
Long-term investment alert system that identifies optimal buying opportunities by analyzing stock price patterns over 90-day periods. Written in Python, uses CSV storage, Alpha Vantage API, and focuses on outperforming dollar-cost averaging.

## Key Commands
- **Install dependencies**: `uv sync`
- **Run backtesting**: `uv run python main.py backtest`
- **Update data**: `uv run python main.py update-data --force`
- **Score opportunities**: `uv run python main.py score --top 10`
- **Calculate allocation**: `uv run python main.py allocate`
- **Run tests**: `uv run pytest tests/ -v`
- **Lint code**: `uv run ruff check src/ tests/`
- **Type check**: `uv run mypy src/`
- **Format code**: `uv run ruff format src/ tests/`

## Project Structure
```
src/
├── data/           # Data fetching and storage
├── models/         # Scoring and allocation models
├── backtesting/    # Historical testing framework
└── utils/          # Helper functions

config/             # YAML configuration files
data/              # CSV data storage
tests/             # Unit and integration tests
```

## Important Files
- `config/settings.yaml`: Main configuration (budget, model parameters)
- `config/tickers.yaml`: Stock/ETF tracking lists
- `TECHNICAL_SPECIFICATION.md`: Complete system design
- `src/models/scorer.py`: Core investment scoring algorithm
- `src/backtesting/engine.py`: Backtesting framework

## Development Notes
- Uses Alpha Vantage API (free tier: 5 calls/min, 500/day)
- Supports US and AU markets
- 90-day lookback period for all calculations
- CSV files organized by ticker and market
- Target: outperform dollar-cost averaging

## Testing Strategy
- Unit tests for scoring models
- Integration tests for API clients
- Backtesting validation against known datasets
- 80/20 train/test splits for parameter optimization

## Environment Variables
- `ALPHA_VANTAGE_API_KEY`: Required for data fetching
- `LT_INVESTMENTS_ENV`: 'development' or 'production'

## Common Debugging
- Check API rate limits if data fetching fails
- Verify ticker symbols match market format (e.g., CBA.AX for AU)
- Ensure CSV files have proper headers and data types
- Validate date formats in backtesting ranges