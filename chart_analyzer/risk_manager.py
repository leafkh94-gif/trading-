"""
Risk Management Engine for the Trading Bot.
Handles position sizing, risk calculations, and trade validation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification."""
    LOW = 0.5
    MEDIUM = 1.0
    HIGH = 2.0
    AGGRESSIVE = 3.0


@dataclass
class RiskParameters:
    """Configuration for risk management."""
    max_risk_per_trade: float = 1.0  # % of account equity
    max_daily_loss: float = 5.0  # % of account equity
    max_open_positions: int = 3
    max_position_size: float = 5.0  # % of account equity
    stop_loss_percent: float = 2.0  # % from entry
    take_profit_ratio: float = 2.0  # Risk-reward ratio
    min_win_rate: float = 0.50  # Minimum acceptable win rate
    volatility_multiplier: float = 1.0  # Adjust sizing by volatility


@dataclass
class TradeValidation:
    """Result of trade validation."""
    is_valid: bool
    reason: str
    suggested_lot_size: Optional[float] = None
    suggested_stop_loss: Optional[float] = None
    suggested_take_profit: Optional[float] = None


class RiskManager:
    """
    Core risk management engine.
    Validates trades and calculates position sizing based on risk parameters.
    """

    def __init__(self, parameters: RiskParameters):
        """
        Initialize risk manager.
        
        Args:
            parameters: Risk configuration parameters
        """
        self.parameters = parameters
        self.daily_loss = 0.0
        self.open_positions = 0
        self.trades_today = 0
        logger.info("Risk Manager initialized")

    def set_daily_loss(self, loss: float) -> None:
        """Update accumulated daily loss."""
        self.daily_loss = loss
        logger.info(f"Daily loss updated: ${loss:.2f}")

    def update_open_positions(self, count: int) -> None:
        """Update count of open positions."""
        self.open_positions = count
        logger.info(f"Open positions: {count}")

    def validate_trade(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss_price: float,
        current_market_price: float,
        instrument: str = "XAUUSD",
        volatility: float = 1.0
    ) -> TradeValidation:
        """
        Validate if a trade should be executed based on risk parameters.
        
        Args:
            account_equity: Current account balance
            entry_price: Planned entry price
            stop_loss_price: Planned stop-loss price
            current_market_price: Current market price
            instrument: Trading instrument (default: XAUUSD)
            volatility: Current market volatility (0.5-2.0 multiplier)
        
        Returns:
            TradeValidation: Validation result with suggested parameters
        """
        
        # Check 1: Maximum open positions
        if self.open_positions >= self.parameters.max_open_positions:
            return TradeValidation(
                is_valid=False,
                reason=f"Maximum open positions ({self.parameters.max_open_positions}) reached"
            )
        
        # Check 2: Daily loss limit
        if self.daily_loss >= (account_equity * self.parameters.max_daily_loss / 100):
            return TradeValidation(
                is_valid=False,
                reason=f"Daily loss limit ({self.parameters.max_daily_loss}%) exceeded"
            )
        
        # Calculate risk for this trade
        risk_per_trade = self.calculate_risk_per_trade(
            account_equity, entry_price, stop_loss_price
        )
        
        # Check 3: Risk per trade limit
        max_risk = account_equity * self.parameters.max_risk_per_trade / 100
        if risk_per_trade > max_risk:
            return TradeValidation(
                is_valid=False,
                reason=f"Risk per trade (${risk_per_trade:.2f}) exceeds limit (${max_risk:.2f})"
            )
        
        # Calculate lot size
        lot_size = self.calculate_lot_size(
            account_equity, entry_price, stop_loss_price, volatility
        )
        
        # Check 4: Position size limit
        position_value = lot_size * entry_price
        max_position_value = account_equity * self.parameters.max_position_size / 100
        if position_value > max_position_value:
            return TradeValidation(
                is_valid=False,
                reason=f"Position size (${position_value:.2f}) exceeds limit"
            )
        
        # Calculate take-profit based on risk-reward ratio
        take_profit = self.calculate_take_profit(
            entry_price, stop_loss_price
        )
        
        logger.info(
            f"Trade validated: Lot={lot_size:.2f}, Risk=${risk_per_trade:.2f}, "
            f"TP=${take_profit:.2f}"
        )
        
        return TradeValidation(
            is_valid=True,
            reason="Trade validated successfully",
            suggested_lot_size=lot_size,
            suggested_stop_loss=stop_loss_price,
            suggested_take_profit=take_profit
        )

    def calculate_lot_size(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss_price: float,
        volatility: float = 1.0
    ) -> float:
        """
        Calculate optimal lot size based on risk management rules.
        
        Formula: Lot Size = (Risk Amount / Pips) * Volatility Adjustment
        """
        
        # Risk amount per trade (% of equity)
        risk_percent = self.parameters.max_risk_per_trade
        risk_amount = account_equity * risk_percent / 100
        
        # Pips/points from entry to stop-loss
        pips = abs(entry_price - stop_loss_price)
        
        if pips == 0:
            return 0.01  # Minimum lot size
        
        # Base lot size
        lot_size = risk_amount / pips
        
        # Apply volatility adjustment
        lot_size *= self.parameters.volatility_multiplier
        lot_size *= (1 / volatility)  # Lower size if volatility is high
        
        # Ensure position doesn't exceed max % of equity
        max_position_size = (account_equity * self.parameters.max_position_size / 100) / entry_price
        lot_size = min(lot_size, max_position_size)
        
        # Round to 0.01 lot increments
        lot_size = round(lot_size, 2)
        lot_size = max(lot_size, 0.01)  # Minimum lot size
        
        return lot_size

    def calculate_risk_per_trade(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """Calculate total risk in dollars for a trade."""
        
        lot_size = self.calculate_lot_size(account_equity, entry_price, stop_loss_price)
        pips = abs(entry_price - stop_loss_price)
        
        # For gold, pip value varies. Standard: 1 pip = $0.01 per lot
        risk_amount = lot_size * pips * 100
        
        return risk_amount

    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calculate take-profit price based on risk-reward ratio.
        
        Formula: TP = Entry + (Entry - SL) * Risk-Reward Ratio
        """
        
        risk = abs(entry_price - stop_loss_price)
        reward = risk * self.parameters.take_profit_ratio
        
        if entry_price > stop_loss_price:  # Long trade
            return entry_price + reward
        else:  # Short trade
            return entry_price - reward

    def calculate_dynamic_stop_loss(
        self,
        entry_price: float,
        current_atr: float,
        is_long: bool = True
    ) -> float:
        """
        Calculate dynamic stop-loss based on ATR (Average True Range).
        
        Args:
            entry_price: Trade entry price
            current_atr: Current ATR value
            is_long: True for long trades, False for short
        
        Returns:
            float: Suggested stop-loss price
        """
        
        # Use 1.5x ATR as stop-loss distance
        stop_distance = current_atr * 1.5
        
        if is_long:
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance

    def get_position_adjustment(
        self,
        current_price: float,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        current_profit_loss: float,
        account_equity: float
    ) -> Optional[Dict]:
        """
        Determine if position should be adjusted (partial close, trailing stop, etc).
        
        Returns:
            Dict with adjustment recommendations or None
        """
        
        # If in profit, consider trailing stop
        if current_profit_loss > 0:
            profit_percent = (current_profit_loss / account_equity) * 100
            
            # If profit > 1% of account, set trailing stop at 0.5% from current price
            if profit_percent > 1.0:
                return {
                    "action": "trailing_stop",
                    "new_stop_loss": current_price - (abs(entry_price - stop_loss_price) * 0.5),
                    "reason": f"Profit at {profit_percent:.2f}%"
                }
        
        # If approaching take-profit, consider partial close
        distance_to_tp = abs(take_profit_price - current_price)
        total_distance = abs(take_profit_price - entry_price)
        
        if total_distance > 0 and distance_to_tp / total_distance < 0.1:
            return {
                "action": "partial_close",
                "close_percent": 50,  # Close 50% of position
                "reason": "Near take-profit level"
            }
        
        return None

    def reset_daily_counters(self) -> None:
        """Reset daily loss and trade counters."""
        self.daily_loss = 0.0
        self.trades_today = 0
        logger.info("Daily counters reset")
