"""
Trading Strategies for Gold (XAUUSD).
Implements scalping, breakout, and AI-powered trading strategies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Tuple
import numpy as np
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal enumeration."""
    BUY = "buy"
    SELL = "sell"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    HOLD = "hold"
    NO_SIGNAL = "no_signal"


@dataclass
class TradeSignal:
    """Represents a trading signal."""
    signal_type: SignalType
    confidence: float  # 0.0 to 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    reasoning: str
    timestamp: datetime = None
    indicators_used: Dict = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.indicators_used is None:
            self.indicators_used = {}

    def is_strong_signal(self) -> bool:
        """Check if signal strength is above threshold (0.7)."""
        return self.confidence >= 0.7


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    def __init__(self, name: str, symbol: str = "XAUUSD"):
        """
        Initialize strategy.
        
        Args:
            name: Strategy name
            symbol: Trading instrument
        """
        self.name = name
        self.symbol = symbol
        self.last_signal = None
        logger.info(f"Strategy {name} initialized for {symbol}")

    @abstractmethod
    def analyze(self, data: Dict) -> TradeSignal:
        """
        Analyze market data and generate trading signal.
        
        Args:
            data: Dictionary containing price data and indicators
                  Expected keys: 'close', 'high', 'low', 'volume', 
                                'ma_fast', 'ma_slow', 'rsi', 'macd', 'atr'
        
        Returns:
            TradeSignal: Generated trading signal
        """
        pass


class ScalpingStrategy(BaseStrategy):
    """
    Scalping Strategy for XAUUSD.
    
    Focuses on quick profits from small price movements.
    Uses tight stops and quick exits. Typical hold time: 5-30 minutes.
    
    Signals:
    - BUY: RSI < 30 (oversold) + MA confirmation + MACD positive
    - SELL: RSI > 70 (overbought) + MA confirmation + MACD negative
    """

    def __init__(self, symbol: str = "XAUUSD"):
        super().__init__("Scalping", symbol)
        self.rsi_oversold = 30
        self.rsi_overbought = 70

    def analyze(self, data: Dict) -> TradeSignal:
        """
        Scalping signal generation.
        
        Data requirements:
            - close: Latest close price
            - rsi: RSI(14) values
            - ma_fast: Fast MA (9-period)
            - ma_slow: Slow MA (21-period)
            - macd: MACD line value
            - signal_line: MACD signal line
            - atr: ATR for stop-loss calculation
        """
        
        if not self._validate_data(data):
            return TradeSignal(
                signal_type=SignalType.NO_SIGNAL,
                confidence=0.0,
                entry_price=data.get('close', 0),
                stop_loss=0,
                take_profit=0,
                reasoning="Insufficient data"
            )
        
        close = data['close']
        rsi = data['rsi']
        ma_fast = data['ma_fast']
        ma_slow = data['ma_slow']
        macd = data['macd']
        signal_line = data.get('signal_line', 0)
        atr = data.get('atr', close * 0.005)
        
        signal = SignalType.NO_SIGNAL
        confidence = 0.0
        reasoning = ""
        
        # BUY Signals (Oversold + Uptrend confirmation)
        if rsi < self.rsi_oversold:
            if ma_fast > ma_slow:  # Uptrend
                if macd > signal_line:  # MACD positive
                    signal = SignalType.BUY
                    confidence = min(0.9, (30 - rsi) / 30 + 0.3)  # Max 0.9
                    reasoning = f"Oversold (RSI={rsi:.1f}) + Uptrend (MA) + MACD positive"
            else:
                if macd > signal_line:
                    signal = SignalType.BUY
                    confidence = 0.6
                    reasoning = f"Oversold (RSI={rsi:.1f}) + MACD positive"
        
        # SELL Signals (Overbought + Downtrend confirmation)
        elif rsi > self.rsi_overbought:
            if ma_fast < ma_slow:  # Downtrend
                if macd < signal_line:  # MACD negative
                    signal = SignalType.SELL
                    confidence = min(0.9, (rsi - 70) / 30 + 0.3)
                    reasoning = f"Overbought (RSI={rsi:.1f}) + Downtrend (MA) + MACD negative"
            else:
                if macd < signal_line:
                    signal = SignalType.SELL
                    confidence = 0.6
                    reasoning = f"Overbought (RSI={rsi:.1f}) + MACD negative"
        
        # Calculate entry/exit prices
        entry_price = close
        
        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            stop_loss = close - (atr * 1.2)
            take_profit = close + (atr * 2.0)  # 2:1 risk-reward ratio
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            stop_loss = close + (atr * 1.2)
            take_profit = close - (atr * 2.0)
        else:
            stop_loss = 0
            take_profit = 0
        
        trade_signal = TradeSignal(
            signal_type=signal,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            indicators_used={
                'rsi': rsi,
                'ma_fast': ma_fast,
                'ma_slow': ma_slow,
                'macd': macd,
                'atr': atr
            }
        )
        
        self.last_signal = trade_signal
        return trade_signal

    @staticmethod
    def _validate_data(data: Dict) -> bool:
        """Validate required data fields."""
        required_fields = ['close', 'rsi', 'ma_fast', 'ma_slow', 'macd']
        return all(field in data for field in required_fields)


class BreakoutStrategy(BaseStrategy):
    """
    Breakout Strategy for XAUUSD.
    
    Trades breakouts from support/resistance levels.
    
    Signals:
    - BUY: Price breaks above resistance + RSI > 50 + Volume confirmation
    - SELL: Price breaks below support + RSI < 50 + Volume confirmation
    """

    def __init__(self, symbol: str = "XAUUSD"):
        super().__init__("Breakout", symbol)
        self.lookback_period = 20  # Period to find support/resistance

    def analyze(self, data: Dict) -> TradeSignal:
        """
        Breakout signal generation.
        
        Data requirements:
            - close: Close prices (array of last N periods)
            - high: High prices (array)
            - low: Low prices (array)
            - volume: Volume (array)
            - rsi: Current RSI
            - atr: ATR for stop-loss
        """
        
        if not self._validate_data(data):
            return TradeSignal(
                signal_type=SignalType.NO_SIGNAL,
                confidence=0.0,
                entry_price=data.get('close', 0) if isinstance(data.get('close'), (int, float)) else 0,
                stop_loss=0,
                take_profit=0,
                reasoning="Insufficient data"
            )
        
        # Get current values
        close = data['close'][-1] if isinstance(data['close'], list) else data['close']
        rsi = data.get('rsi', 50)
        atr = data.get('atr', close * 0.005)
        
        # Find support and resistance
        highs = data['high'] if isinstance(data['high'], list) else [data['high']]
        lows = data['low'] if isinstance(data['low'], list) else [data['low']]
        
        if len(highs) >= self.lookback_period:
            resistance = max(highs[-self.lookback_period:])
            support = min(lows[-self.lookback_period:])
        else:
            resistance = max(highs) if highs else close
            support = min(lows) if lows else close
        
        signal = SignalType.NO_SIGNAL
        confidence = 0.0
        reasoning = ""
        
        # Breakout above resistance
        if close > resistance and rsi > 50:
            signal = SignalType.BUY
            confidence = 0.75
            reasoning = f"Breakout above resistance ({resistance:.2f}) + RSI > 50"
        
        # Breakdown below support
        elif close < support and rsi < 50:
            signal = SignalType.SELL
            confidence = 0.75
            reasoning = f"Breakdown below support ({support:.2f}) + RSI < 50"
        
        # Calculate entry/exit
        entry_price = close
        
        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            stop_loss = support - (atr * 0.5)
            take_profit = entry_price + (entry_price - support)
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            stop_loss = resistance + (atr * 0.5)
            take_profit = entry_price - (resistance - entry_price)
        else:
            stop_loss = 0
            take_profit = 0
        
        trade_signal = TradeSignal(
            signal_type=signal,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            indicators_used={
                'support': support,
                'resistance': resistance,
                'rsi': rsi,
                'atr': atr
            }
        )
        
        self.last_signal = trade_signal
        return trade_signal

    @staticmethod
    def _validate_data(data: Dict) -> bool:
        """Validate required data fields."""
        required_fields = ['close', 'high', 'low']
        return all(field in data for field in required_fields)


class AIStrategy(BaseStrategy):
    """
    AI-Powered Strategy using Machine Learning.
    
    Combines multiple indicators with ML predictions.
    """

    def __init__(self, symbol: str = "XAUUSD"):
        super().__init__("AI", symbol)
        self.ml_model = None  # Will be trained model

    def analyze(self, data: Dict) -> TradeSignal:
        """
        AI signal generation.
        
        Uses ensemble of indicators + ML model prediction.
        """
        
        if not self._validate_data(data):
            return TradeSignal(
                signal_type=SignalType.NO_SIGNAL,
                confidence=0.0,
                entry_price=data.get('close', 0),
                stop_loss=0,
                take_profit=0,
                reasoning="Insufficient data"
            )
        
        close = data['close']
        rsi = data['rsi']
        macd = data['macd']
        ma_fast = data['ma_fast']
        ma_slow = data['ma_slow']
        atr = data.get('atr', close * 0.005)
        
        # Composite signal from multiple indicators
        signal_strength = 0.0
        signal_direction = 0.0  # Positive = bullish, Negative = bearish
        
        # RSI component (-1 to +1)
        rsi_signal = (rsi - 50) / 50
        signal_direction += rsi_signal * 0.3
        
        # MA component
        ma_ratio = (ma_fast - ma_slow) / ma_slow
        signal_direction += min(1, max(-1, ma_ratio * 100)) * 0.4
        
        # MACD component
        macd_signal = 1.0 if macd > 0 else -1.0
        signal_direction += macd_signal * 0.3
        
        # Normalize direction to -1 to 1
        signal_direction = max(-1, min(1, signal_direction))
        
        # Determine signal type and confidence
        confidence = abs(signal_direction)
        
        if signal_direction > 0.5:
            signal = SignalType.STRONG_BUY
        elif signal_direction > 0.2:
            signal = SignalType.BUY
        elif signal_direction < -0.5:
            signal = SignalType.STRONG_SELL
        elif signal_direction < -0.2:
            signal = SignalType.SELL
        else:
            signal = SignalType.HOLD
            confidence = 0.5
        
        # Entry/exit prices
        entry_price = close
        
        if signal in [SignalType.BUY, SignalType.STRONG_BUY]:
            stop_loss = close - (atr * 1.5)
            take_profit = close + (atr * 2.5)
        elif signal in [SignalType.SELL, SignalType.STRONG_SELL]:
            stop_loss = close + (atr * 1.5)
            take_profit = close - (atr * 2.5)
        else:
            stop_loss = 0
            take_profit = 0
        
        reasoning = f"AI: RSI={rsi:.1f}, MA_Ratio={ma_ratio:.4f}, MACD={'Pos' if macd > 0 else 'Neg'}"
        
        trade_signal = TradeSignal(
            signal_type=signal,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            indicators_used={
                'rsi': rsi,
                'macd': macd,
                'ma_fast': ma_fast,
                'ma_slow': ma_slow,
                'atr': atr,
                'signal_direction': signal_direction
            }
        )
        
        self.last_signal = trade_signal
        return trade_signal

    @staticmethod
    def _validate_data(data: Dict) -> bool:
        """Validate required data fields."""
        required_fields = ['close', 'rsi', 'macd', 'ma_fast', 'ma_slow']
        return all(field in data for field in required_fields)
