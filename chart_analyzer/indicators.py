"""
Technical Indicators for trading analysis.
Provides standard technical indicators used in chart analysis.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple


class TechnicalIndicators:
    """
    Collection of technical indicators for market analysis.
    """
    
    @staticmethod
    def simple_moving_average(data: List[float], period: int) -> pd.Series:
        """Compatibility wrapper for simple moving average."""
        return pd.Series(data).rolling(window=period).mean()

    @staticmethod
    def exponential_moving_average(data: List[float], period: int) -> pd.Series:
        """Compatibility wrapper for exponential moving average."""
        return pd.Series(data).ewm(span=period, adjust=False).mean()

    @staticmethod
    def relative_strength_index(data: List[float], period: int = 14) -> pd.Series:
        """Compatibility wrapper for RSI."""
        series = pd.Series(data, dtype=float)
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(window=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def moving_average(data: List[float], period: int, ma_type: str = 'sma') -> List[float]:
        """
        Calculate moving average.
        
        Args:
            data: Price data
            period: MA period
            ma_type: 'sma' (simple) or 'ema' (exponential)
        
        Returns:
            List of MA values
        """
        if len(data) < period:
            return [np.nan] * len(data)
        
        if ma_type.lower() == 'sma':
            return TechnicalIndicators._calculate_sma(data, period)
        elif ma_type.lower() == 'ema':
            return TechnicalIndicators._calculate_ema(data, period)
        else:
            return [np.nan] * len(data)
    
    @staticmethod
    def _calculate_sma(data: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average."""
        df = pd.Series(data)
        sma = df.rolling(window=period).mean()
        return sma.tolist()
    
    @staticmethod
    def _calculate_ema(data: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average."""
        df = pd.Series(data)
        ema = df.ewm(span=period, adjust=False).mean()
        return ema.tolist()
    
    @staticmethod
    def rsi(data: List[float], period: int = 14) -> List[float]:
        """
        Calculate Relative Strength Index.
        
        Args:
            data: Price data (typically close prices)
            period: RSI period (default 14)
        
        Returns:
            List of RSI values
        """
        if len(data) < period:
            return [np.nan] * len(data)
        
        df = pd.Series(data)
        delta = df.diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.tolist()
    
    @staticmethod
    def macd(data: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            data: Price data
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
        
        Returns:
            Tuple of (MACD line, Signal line, Histogram)
        """
        if len(data) < slow:
            return {
                'macd': [np.nan] * len(data),
                'signal': [np.nan] * len(data),
                'histogram': [np.nan] * len(data),
            }

        df = pd.Series(data)
        ema_fast = df.ewm(span=fast, adjust=False).mean()
        ema_slow = df.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            'macd': macd_line.tolist(),
            'signal': signal_line.tolist(),
            'histogram': histogram.tolist(),
        }
    
    @staticmethod
    def bollinger_bands(data: List[float], period: int = 20, num_std: float = 2.0) -> dict:
        """
        Calculate Bollinger Bands.
        
        Args:
            data: Price data
            period: MA period
            num_std: Number of standard deviations
        
        Returns:
            Tuple of (Upper band, Middle band, Lower band)
        """
        if len(data) < period:
            return {
                'upper': [np.nan] * len(data),
                'middle': [np.nan] * len(data),
                'lower': [np.nan] * len(data),
            }

        df = pd.Series(data)
        middle_band = df.rolling(window=period).mean()
        std_dev = df.rolling(window=period).std()

        upper_band = middle_band + (std_dev * num_std)
        lower_band = middle_band - (std_dev * num_std)

        return {
            'upper': upper_band.tolist(),
            'middle': middle_band.tolist(),
            'lower': lower_band.tolist(),
        }
    
    @staticmethod
    def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
        """
        Calculate Average True Range.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
        
        Returns:
            List of ATR values
        """
        if len(high) < period or len(low) < period or len(close) < period:
            return [np.nan] * len(high)
        
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.tolist()
    
    @staticmethod
    def stochastic(high: List[float], low: List[float], close: List[float], 
                  period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Tuple[List[float], List[float]]:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Lookback period
            smooth_k: K line smoothing period
            smooth_d: D line smoothing period
        
        Returns:
            Tuple of (K line, D line)
        """
        if len(high) < period:
            return [np.nan] * len(high), [np.nan] * len(high)
        
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        
        k_percent = 100 * (close - lowest_low) / (highest_high - lowest_low)
        k_line = k_percent.rolling(window=smooth_k).mean()
        d_line = k_line.rolling(window=smooth_d).mean()
        
        return k_line.tolist(), d_line.tolist()
    
    @staticmethod
    def support_resistance(data: List[float], period: int = 20) -> Tuple[float, float]:
        """
        Simple support and resistance levels.
        
        Args:
            data: Price data
            period: Lookback period
        
        Returns:
            Tuple of (Support level, Resistance level)
        """
        if len(data) < period:
            return min(data), max(data)
        
        recent_data = data[-period:]
        support = min(recent_data)
        resistance = max(recent_data)
        
        return support, resistance
    
    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all standard indicators for a dataframe.
        
        Args:
            df: DataFrame with 'open', 'high', 'low', 'close', 'volume' columns
        
        Returns:
            DataFrame with added indicator columns
        """
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Add indicators
        df['sma_20'] = TechnicalIndicators.moving_average(close, 20, 'sma')
        df['sma_50'] = TechnicalIndicators.moving_average(close, 50, 'sma')
        df['ema_12'] = TechnicalIndicators.moving_average(close, 12, 'ema')
        df['rsi'] = TechnicalIndicators.rsi(close, 14)
        
        macd_result = TechnicalIndicators.macd(close)
        df['macd'] = macd_result['macd']
        df['macd_signal'] = macd_result['signal']
        df['macd_hist'] = macd_result['histogram']

        bb_result = TechnicalIndicators.bollinger_bands(close)
        df['bb_upper'] = bb_result['upper']
        df['bb_middle'] = bb_result['middle']
        df['bb_lower'] = bb_result['lower']
        
        df['atr'] = TechnicalIndicators.atr(high, low, close)
        
        k, d = TechnicalIndicators.stochastic(high, low, close)
        df['stoch_k'] = k
        df['stoch_d'] = d
        
        return df
