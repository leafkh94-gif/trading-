# Trading Chart Analyzer

A Python-based trading chart analysis tool for analyzing market data and generating trading signals.

## Features

- Real-time chart analysis
- Technical indicator calculations
- Trading signal generation
- Data visualization

## Project Structure

```
trading-/
├── chart_analyzer/          # Main package
│   ├── __init__.py
│   ├── analyzer.py         # Core analysis logic
│   ├── indicators.py       # Technical indicators
│   ├── data_handler.py     # Data processing
│   └── visualizer.py       # Chart visualization
├── tests/                  # Unit tests
│   ├── __init__.py
│   └── test_analyzer.py
├── requirements.txt        # Project dependencies
├── main.py                # Entry point
└── README.md              # This file
```

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/leafkh94-gif/trading-.git
   cd trading-
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```python
from chart_analyzer import Analyzer

# Initialize analyzer
analyzer = Analyzer()

# Analyze chart data
signals = analyzer.analyze(data)
```

## Running Tests

Run unit tests with pytest:

```bash
pytest tests/
pytest tests/ -v  # Verbose output
pytest tests/ --cov=chart_analyzer  # With coverage report
```

## Requirements

See `requirements.txt` for all dependencies.

## License

MIT
