"""
Unit tests for the analyzer module.
"""

import pytest
import pandas as pd
import numpy as np
from chart_analyzer import Analyzer, DataHandler, TechnicalIndicators


class TestAnalyzer:
    """Test cases for the Analyzer class."""

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLCV data for testing."""
        dates = pd.date_range('2024-01-01', periods=100)
        return pd.DataFrame({
            'open': np.random.uniform(100, 110, 100),
            'high': np.random.uniform(110, 120, 100),
            'low': np.random.uniform(90, 100, 100),
            'close': np.random.uniform(100, 110, 100),
            'volume': np.random.uniform(1000000, 2000000, 100),
        }, index=dates)

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = Analyzer()
        assert analyzer is not None
        assert analyzer.indicators is not None
        assert analyzer.data_handler is not None

    def test_analyze_with_valid_data(self, sample_data):
        """Test analysis with valid data."""
        analyzer = Analyzer()
        results = analyzer.analyze(sample_data)

        assert results is not None
        assert 'data' in results
        assert 'indicators' in results
        assert 'signals' in results

    def test_analyze_with_empty_data(self):
        """Test analysis with empty data raises error."""
        analyzer = Analyzer()
        with pytest.raises(ValueError):
            analyzer.analyze(pd.DataFrame())


class TestDataHandler:
    """Test cases for the DataHandler class."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        return pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [105, 106, 107],
            'Low': [99, 100, 101],
            'Close': [104, 105, 106],
            'Volume': [1000000, 1100000, 1200000],
        })

    def test_clean_data(self, sample_data):
        """Test data cleaning."""
        handler = DataHandler()
        cleaned = handler.clean_data(sample_data)

        assert len(cleaned) == 3
        assert all(col in cleaned.columns for col in ['open', 'high', 'low', 'close', 'volume'])

    def test_normalize_data(self, sample_data):
        """Test data normalization."""
        handler = DataHandler()
        cleaned = handler.clean_data(sample_data)
        normalized = handler.normalize_data(cleaned)

        assert normalized['close'].min() >= 0
        assert normalized['close'].max() <= 1

    def test_split_data(self, sample_data):
        """Test data splitting."""
        handler = DataHandler()
        cleaned = handler.clean_data(sample_data)
        train, test = handler.split_data(cleaned, train_ratio=0.67)

        assert len(train) + len(test) == len(cleaned)


class TestTechnicalIndicators:
    """Test cases for the TechnicalIndicators class."""

    @pytest.fixture
    def price_series(self):
        """Create sample price series for testing."""
        return pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109])

    def test_simple_moving_average(self, price_series):
        """Test SMA calculation."""
        indicators = TechnicalIndicators()
        sma = indicators.simple_moving_average(price_series, 3)

        assert len(sma) == len(price_series)
        assert sma.isna().sum() == 2  # First 2 values should be NaN

    def test_exponential_moving_average(self, price_series):
        """Test EMA calculation."""
        indicators = TechnicalIndicators()
        ema = indicators.exponential_moving_average(price_series, 3)

        assert len(ema) == len(price_series)
        assert not ema.isna().any()

    def test_relative_strength_index(self, price_series):
        """Test RSI calculation."""
        indicators = TechnicalIndicators()
        rsi = indicators.relative_strength_index(price_series, 14)

        assert len(rsi) == len(price_series)
        assert (rsi >= 0).all() or rsi.isna().any()
        assert (rsi <= 100).all() or rsi.isna().any()

    def test_macd(self, price_series):
        """Test MACD calculation."""
        indicators = TechnicalIndicators()
        macd_result = indicators.macd(price_series)

        assert 'macd' in macd_result
        assert 'signal' in macd_result
        assert 'histogram' in macd_result
        assert len(macd_result['macd']) == len(price_series)

    def test_bollinger_bands(self, price_series):
        """Test Bollinger Bands calculation."""
        indicators = TechnicalIndicators()
        bb = indicators.bollinger_bands(price_series)

        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        assert len(bb['upper']) == len(price_series)
