"""
Core Trading Bot Engine.
Orchestrates strategy analysis, risk management, and trade execution.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from chart_analyzer.risk_manager import RiskManager, RiskParameters
from chart_analyzer.position_manager import PositionManager, TradeType, PositionStats
from chart_analyzer.strategies import (
    BaseStrategy, ScalpingStrategy, BreakoutStrategy, 
    AIStrategy, TradeSignal, SignalType
)

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Trading bot configuration."""
    symbol: str = "XAUUSD"
    account_equity: float = 1000.0
    strategy_name: str = "scalping"  # "scalping", "breakout", "ai"
    max_trades_per_day: int = 2
    min_trade_confidence: float = 0.6
    enabled_strategies: List[str] = None
    
    def __post_init__(self):
        if self.enabled_strategies is None:
            self.enabled_strategies = ["scalping", "breakout", "ai"]


class TradingBot:
    """
    Main trading bot engine.
    
    Orchestrates:
    - Strategy analysis
    - Signal generation
    - Risk validation
    - Trade execution
    - Performance tracking
    """

    def __init__(self, config: BotConfig, risk_params: Optional[RiskParameters] = None):
        """
        Initialize trading bot.
        
        Args:
            config: Bot configuration
            risk_params: Risk management parameters (default: conservative)
        """
        self.config = config
        self.account_equity = config.account_equity
        self.is_running = False
        
        # Initialize risk management
        if risk_params is None:
            risk_params = RiskParameters(
                max_risk_per_trade=1.0,
                max_daily_loss=5.0,
                max_open_positions=3,
                take_profit_ratio=2.0
            )
        
        self.risk_manager = RiskManager(risk_params)
        self.position_manager = PositionManager()
        
        # Initialize strategies
        self.strategies: Dict[str, BaseStrategy] = {}
        self._initialize_strategies()
        
        # Trading state
        self.trades_today = 0
        self.last_analysis_time = None
        
        logger.info(
            f"Trading Bot initialized: {config.symbol}, "
            f"Equity: ${config.account_equity}, "
            f"Strategy: {config.strategy_name}"
        )

    def _initialize_strategies(self) -> None:
        """Initialize trading strategies."""
        if "scalping" in self.config.enabled_strategies:
            self.strategies["scalping"] = ScalpingStrategy(self.config.symbol)
        
        if "breakout" in self.config.enabled_strategies:
            self.strategies["breakout"] = BreakoutStrategy(self.config.symbol)
        
        if "ai" in self.config.enabled_strategies:
            self.strategies["ai"] = AIStrategy(self.config.symbol)
        
        logger.info(f"Strategies initialized: {list(self.strategies.keys())}")

    def start(self) -> None:
        """Start the trading bot."""
        self.is_running = True
        self.risk_manager.reset_daily_counters()
        logger.info("Trading bot started")

    def stop(self) -> None:
        """Stop the trading bot."""
        self.is_running = False
        logger.info("Trading bot stopped")

    def analyze_market(self, market_data: Dict) -> Dict[str, TradeSignal]:
        """
        Analyze market using all enabled strategies.
        
        Args:
            market_data: Market data dictionary with OHLCV and indicators
        
        Returns:
            Dictionary of signals by strategy name
        """
        
        if not self.is_running:
            logger.warning("Bot is not running")
            return {}
        
        signals = {}
        
        for strategy_name, strategy in self.strategies.items():
            try:
                signal = strategy.analyze(market_data)
                signals[strategy_name] = signal
                
                if signal.signal_type != SignalType.NO_SIGNAL:
                    logger.info(
                        f"{strategy_name.upper()}: {signal.signal_type.value} "
                        f"(Confidence: {signal.confidence:.2%}) - {signal.reasoning}"
                    )
            except Exception as e:
                logger.error(f"Error in {strategy_name} strategy: {e}")
                signals[strategy_name] = None
        
        self.last_analysis_time = datetime.now()
        return signals

    def generate_trading_decision(
        self,
        signals: Dict[str, TradeSignal],
        market_data: Dict
    ) -> Optional[TradeSignal]:
        """
        Generate unified trading decision from multiple signals.
        
        Uses weighted voting from all strategies.
        
        Args:
            signals: Dictionary of signals from all strategies
            market_data: Current market data
        
        Returns:
            TradeSignal: Consolidated trading signal or None
        """
        
        if not signals:
            return None
        
        # Filter valid signals
        valid_signals = [
            s for s in signals.values() 
            if s and s.signal_type != SignalType.NO_SIGNAL
        ]
        
        if not valid_signals:
            return None
        
        # Weight signals by confidence and strategy reliability
        buy_weight = 0.0
        sell_weight = 0.0
        high_confidence_buys = 0
        high_confidence_sells = 0
        
        for signal in valid_signals:
            confidence = signal.confidence
            
            if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                buy_weight += confidence
                if signal.confidence >= 0.7:
                    high_confidence_buys += 1
            elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
                sell_weight += confidence
                if signal.confidence >= 0.7:
                    high_confidence_sells += 1
        
        # Determine final signal
        if high_confidence_buys >= 2 and buy_weight > sell_weight:
            # Strong consensus to buy
            final_signal = TradeSignal(
                signal_type=SignalType.STRONG_BUY,
                confidence=min(0.95, buy_weight / len(valid_signals)),
                entry_price=valid_signals[0].entry_price,
                stop_loss=min(s.stop_loss for s in valid_signals if s.stop_loss > 0),
                take_profit=max(s.take_profit for s in valid_signals if s.take_profit > 0),
                reasoning=f"{high_confidence_buys} strategies signal strong buy"
            )
            return final_signal
        
        elif high_confidence_sells >= 2 and sell_weight > buy_weight:
            # Strong consensus to sell
            final_signal = TradeSignal(
                signal_type=SignalType.STRONG_SELL,
                confidence=min(0.95, sell_weight / len(valid_signals)),
                entry_price=valid_signals[0].entry_price,
                stop_loss=max(s.stop_loss for s in valid_signals if s.stop_loss > 0),
                take_profit=min(s.take_profit for s in valid_signals if s.take_profit > 0),
                reasoning=f"{high_confidence_sells} strategies signal strong sell"
            )
            return final_signal
        
        elif buy_weight > sell_weight and buy_weight > 0:
            # Weak buy signal
            final_signal = TradeSignal(
                signal_type=SignalType.BUY,
                confidence=buy_weight / len(valid_signals),
                entry_price=valid_signals[0].entry_price,
                stop_loss=min(s.stop_loss for s in valid_signals if s.stop_loss > 0),
                take_profit=max(s.take_profit for s in valid_signals if s.take_profit > 0),
                reasoning="Mixed signals favor buying"
            )
            return final_signal
        
        elif sell_weight > buy_weight and sell_weight > 0:
            # Weak sell signal
            final_signal = TradeSignal(
                signal_type=SignalType.SELL,
                confidence=sell_weight / len(valid_signals),
                entry_price=valid_signals[0].entry_price,
                stop_loss=max(s.stop_loss for s in valid_signals if s.stop_loss > 0),
                take_profit=min(s.take_profit for s in valid_signals if s.take_profit > 0),
                reasoning="Mixed signals favor selling"
            )
            return final_signal
        
        return None

    def validate_and_execute_trade(
        self,
        signal: TradeSignal,
        market_data: Dict
    ) -> bool:
        """
        Validate signal against risk parameters and execute trade.
        
        Args:
            signal: Trading signal
            market_data: Current market data
        
        Returns:
            bool: True if trade was executed, False otherwise
        """
        
        if signal.confidence < self.config.min_trade_confidence:
            logger.info(f"Signal rejected: Confidence {signal.confidence:.2%} < {self.config.min_trade_confidence:.2%}")
            return False
        
        if self.trades_today >= self.config.max_trades_per_day:
            logger.warning(f"Daily trade limit ({self.config.max_trades_per_day}) reached")
            return False
        
        # Update risk manager state
        self.risk_manager.update_open_positions(
            self.position_manager.get_open_position_count()
        )
        
        # Validate trade with risk manager
        volatility = market_data.get('volatility', 1.0)
        validation = self.risk_manager.validate_trade(
            account_equity=self.account_equity,
            entry_price=signal.entry_price,
            stop_loss_price=signal.stop_loss,
            current_market_price=signal.entry_price,
            volatility=volatility
        )
        
        if not validation.is_valid:
            logger.warning(f"Trade validation failed: {validation.reason}")
            return False
        
        # Determine trade type
        if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
            trade_type = TradeType.LONG
            strategy_name = "buy"
        elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
            trade_type = TradeType.SHORT
            strategy_name = "sell"
        else:
            return False
        
        # Execute trade
        trade = self.position_manager.open_trade(
            symbol=self.config.symbol,
            trade_type=trade_type,
            entry_price=signal.entry_price,
            lot_size=validation.suggested_lot_size or 0.01,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            strategy=self.config.strategy_name,
            reason=signal.reasoning
        )
        
        self.trades_today += 1
        logger.info(f"Trade executed: {trade.trade_id}")
        
        return True

    def update_open_trades(self, current_price: float) -> Dict:
        """
        Update all open trades with current market price.
        Check for stop-loss and take-profit hits.
        
        Args:
            current_price: Current market price
        
        Returns:
            Dictionary with closed trades and updates
        """
        
        closed_trades = []
        updates = {
            "closed_trades": closed_trades,
            "updated_trades": 0,
            "total_open": len(self.position_manager.get_all_open_trades())
        }
        
        for trade in self.position_manager.get_all_open_trades():
            self.position_manager.update_price(trade.trade_id, current_price)
            
            # Check stop-loss
            if self.position_manager.check_stop_loss(trade.trade_id):
                closed_trade = self.position_manager.close_trade(
                    trade.trade_id,
                    current_price,
                    reason="Stop-loss hit"
                )
                closed_trades.append(closed_trade)
                logger.warning(f"Trade {trade.trade_id} closed: Stop-loss hit")
            
            # Check take-profit
            elif self.position_manager.check_take_profit(trade.trade_id):
                closed_trade = self.position_manager.close_trade(
                    trade.trade_id,
                    current_price,
                    reason="Take-profit hit"
                )
                closed_trades.append(closed_trade)
                logger.info(f"Trade {trade.trade_id} closed: Take-profit hit")
        
        updates["updated_trades"] = self.position_manager.get_open_position_count()
        
        return updates

    def get_performance_stats(self) -> PositionStats:
        """Get current performance statistics."""
        return self.position_manager.get_stats()

    def reset_daily_state(self) -> None:
        """Reset daily counters and state."""
        self.trades_today = 0
        self.risk_manager.reset_daily_counters()
        logger.info("Daily state reset")

    def get_bot_status(self) -> Dict:
        """Get current bot status."""
        stats = self.get_performance_stats()
        
        return {
            "is_running": self.is_running,
            "symbol": self.config.symbol,
            "account_equity": self.account_equity,
            "strategy": self.config.strategy_name,
            "open_positions": self.position_manager.get_open_position_count(),
            "trades_today": self.trades_today,
            "total_trades": stats.total_trades,
            "win_rate": f"{stats.win_rate:.2f}%",
            "total_profit_loss": f"${stats.total_profit_loss:.2f}",
            "last_analysis": self.last_analysis_time
        }
