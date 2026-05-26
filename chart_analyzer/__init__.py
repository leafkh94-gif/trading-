"""
Trading Chart Analyzer Package

A comprehensive toolkit for analyzing trading charts, generating signals, and executing trades.
Includes AI-powered trading bot with risk management, position tracking, and multi-platform support.
"""

# Original components
from .analyzer import Analyzer
from .indicators import TechnicalIndicators
from .data_handler import DataHandler

# Core trading components
from .trading_bot import TradingBot, BotConfig
from .risk_manager import RiskManager, RiskParameters, RiskLevel
from .position_manager import PositionManager, Trade, TradeType, TradeStatus, PositionStats
from .strategies import (
    BaseStrategy, ScalpingStrategy, BreakoutStrategy, AIStrategy,
    TradeSignal, SignalType
)
from .platform_bridge import (
    BasePlatformBridge, MT4Bridge, MT5Bridge, PlatformFactory, AccountInfo
)
from .monitoring import (
    AlertManager, Alert, AlertType, AlertLevel,
    EmailAlertHandler, TelegramAlertHandler, DiscordAlertHandler, WebhookAlertHandler
)

__all__ = [
    # Original components
    'Analyzer', 'TechnicalIndicators', 'DataHandler',
    
    # Trading bot
    'TradingBot', 'BotConfig',
    
    # Risk management
    'RiskManager', 'RiskParameters', 'RiskLevel',
    
    # Position management
    'PositionManager', 'Trade', 'TradeType', 'TradeStatus', 'PositionStats',
    
    # Strategies
    'BaseStrategy', 'ScalpingStrategy', 'BreakoutStrategy', 'AIStrategy',
    'TradeSignal', 'SignalType',
    
    # Platform integration
    'BasePlatformBridge', 'MT4Bridge', 'MT5Bridge', 'PlatformFactory', 'AccountInfo',
    
    # Monitoring
    'AlertManager', 'Alert', 'AlertType', 'AlertLevel',
    'EmailAlertHandler', 'TelegramAlertHandler', 'DiscordAlertHandler', 'WebhookAlertHandler'
]


__version__ = "0.1.0"
__author__ = "Trading Team"

__all__ = [
    "Analyzer",
    "TechnicalIndicators",
    "DataHandler",
]
