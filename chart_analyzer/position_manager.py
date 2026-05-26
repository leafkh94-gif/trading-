"""
Position Manager for tracking and managing open trades.
Handles entry, exit, and position lifecycle management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    """Trade status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradeType(Enum):
    """Trade type enumeration."""
    LONG = "long"
    SHORT = "short"


@dataclass
class Trade:
    """Represents a single trade."""
    
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = "XAUUSD"
    trade_type: TradeType = TradeType.LONG
    entry_price: float = 0.0
    entry_time: datetime = field(default_factory=datetime.now)
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    
    lot_size: float = 0.01
    stop_loss: float = 0.0
    take_profit: float = 0.0
    current_price: float = 0.0
    
    status: TradeStatus = TradeStatus.PENDING
    
    # Performance metrics
    pips: float = 0.0  # Pips from entry
    profit_loss: float = 0.0  # In dollars
    profit_loss_percent: float = 0.0  # Percentage
    
    # Metadata
    strategy: str = "unknown"
    reason: str = ""
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate trade data."""
        if self.entry_price <= 0:
            raise ValueError("Entry price must be positive")
        if self.lot_size <= 0:
            raise ValueError("Lot size must be positive")

    def update_current_price(self, price: float) -> None:
        """Update current market price and recalculate metrics."""
        self.current_price = price
        self._recalculate_metrics()

    def _recalculate_metrics(self) -> None:
        """Recalculate profit/loss metrics."""
        if self.status == TradeStatus.OPEN:
            if self.trade_type == TradeType.LONG:
                self.pips = self.current_price - self.entry_price
            else:
                self.pips = self.entry_price - self.current_price
            
            # Profit/loss calculation
            self.profit_loss = self.pips * self.lot_size * 100  # Gold pip value
            self.profit_loss_percent = (self.profit_loss / (self.entry_price * self.lot_size)) * 100

    def close(self, exit_price: float, reason: str = "") -> None:
        """Mark trade as closed."""
        self.exit_price = exit_price
        self.exit_time = datetime.now()
        self.status = TradeStatus.CLOSED
        self.reason = reason
        
        # Final calculation
        if self.trade_type == TradeType.LONG:
            self.pips = exit_price - self.entry_price
        else:
            self.pips = self.entry_price - exit_price
        
        self.profit_loss = self.pips * self.lot_size * 100
        self.profit_loss_percent = (self.profit_loss / (self.entry_price * self.lot_size)) * 100
        
        logger.info(
            f"Trade {self.trade_id} closed: {self.trade_type.value} "
            f"P&L: ${self.profit_loss:.2f} ({self.profit_loss_percent:.2f}%)"
        )

    def is_in_profit(self) -> bool:
        """Check if trade is currently in profit."""
        return self.profit_loss > 0

    def get_duration_minutes(self) -> float:
        """Get trade duration in minutes."""
        if self.exit_time:
            duration = self.exit_time - self.entry_time
        else:
            duration = datetime.now() - self.entry_time
        
        return duration.total_seconds() / 60


@dataclass
class PositionStats:
    """Statistics for a group of trades."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit_loss: float = 0.0
    average_profit_loss: float = 0.0
    win_rate: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    average_duration_minutes: float = 0.0


class PositionManager:
    """
    Manages all open and closed positions.
    Tracks trade lifecycle and performance metrics.
    """

    def __init__(self):
        """Initialize position manager."""
        self.open_trades: Dict[str, Trade] = {}
        self.closed_trades: List[Trade] = []
        logger.info("Position Manager initialized")

    def open_trade(
        self,
        symbol: str,
        trade_type: TradeType,
        entry_price: float,
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        strategy: str,
        reason: str = ""
    ) -> Trade:
        """
        Open a new trade.
        
        Args:
            symbol: Trading instrument
            trade_type: LONG or SHORT
            entry_price: Entry price
            lot_size: Position size in lots
            stop_loss: Stop-loss price
            take_profit: Take-profit price
            strategy: Trading strategy name
            reason: Additional context for the trade
        
        Returns:
            Trade: Created trade object
        """
        
        trade = Trade(
            symbol=symbol,
            trade_type=trade_type,
            entry_price=entry_price,
            lot_size=lot_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_price=entry_price,
            strategy=strategy,
            reason=reason,
            status=TradeStatus.OPEN
        )
        
        self.open_trades[trade.trade_id] = trade
        logger.info(
            f"Trade opened: {trade.trade_id} | {trade_type.value} "
            f"{symbol} @ {entry_price} | Lot: {lot_size} | SL: {stop_loss} | TP: {take_profit}"
        )
        
        return trade

    def close_trade(self, trade_id: str, exit_price: float, reason: str = "") -> Optional[Trade]:
        """
        Close an open trade.
        
        Args:
            trade_id: Trade ID to close
            exit_price: Exit price
            reason: Reason for closing
        
        Returns:
            Trade: Closed trade object
        """
        
        if trade_id not in self.open_trades:
            logger.warning(f"Trade {trade_id} not found in open trades")
            return None
        
        trade = self.open_trades.pop(trade_id)
        trade.close(exit_price, reason)
        self.closed_trades.append(trade)
        
        return trade

    def update_price(self, trade_id: str, current_price: float) -> Optional[Trade]:
        """Update current price for an open trade."""
        if trade_id in self.open_trades:
            trade = self.open_trades[trade_id]
            trade.update_current_price(current_price)
            return trade
        return None

    def check_stop_loss(self, trade_id: str) -> bool:
        """Check if stop-loss has been hit."""
        if trade_id not in self.open_trades:
            return False
        
        trade = self.open_trades[trade_id]
        
        if trade.trade_type == TradeType.LONG:
            return trade.current_price <= trade.stop_loss
        else:
            return trade.current_price >= trade.stop_loss

    def check_take_profit(self, trade_id: str) -> bool:
        """Check if take-profit has been hit."""
        if trade_id not in self.open_trades:
            return False
        
        trade = self.open_trades[trade_id]
        
        if trade.trade_type == TradeType.LONG:
            return trade.current_price >= trade.take_profit
        else:
            return trade.current_price <= trade.take_profit

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID."""
        return self.open_trades.get(trade_id)

    def get_all_open_trades(self) -> List[Trade]:
        """Get all open trades."""
        return list(self.open_trades.values())

    def get_all_closed_trades(self) -> List[Trade]:
        """Get all closed trades."""
        return self.closed_trades

    def get_stats(self, trades: Optional[List[Trade]] = None) -> PositionStats:
        """
        Calculate statistics for a set of trades.
        
        Args:
            trades: List of trades to analyze (default: all closed trades)
        
        Returns:
            PositionStats: Statistics object
        """
        
        if trades is None:
            trades = self.closed_trades
        
        if not trades:
            return PositionStats()
        
        stats = PositionStats()
        stats.total_trades = len(trades)
        
        total_pnl = 0.0
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        durations = []
        
        for trade in trades:
            total_pnl += trade.profit_loss
            
            if trade.profit_loss > 0:
                stats.winning_trades += 1
                consecutive_wins += 1
                consecutive_losses = 0
                stats.largest_win = max(stats.largest_win, trade.profit_loss)
            else:
                stats.losing_trades += 1
                consecutive_losses += 1
                consecutive_wins = 0
                stats.largest_loss = min(stats.largest_loss, trade.profit_loss)
            
            max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            
            durations.append(trade.get_duration_minutes())
        
        # Calculate overall metrics
        stats.total_profit_loss = total_pnl
        stats.average_profit_loss = total_pnl / len(trades) if trades else 0
        stats.win_rate = (stats.winning_trades / len(trades)) * 100 if trades else 0
        stats.consecutive_wins = max_consecutive_wins
        stats.consecutive_losses = max_consecutive_losses
        stats.average_duration_minutes = sum(durations) / len(durations) if durations else 0
        
        return stats

    def get_open_position_count(self) -> int:
        """Get number of open positions."""
        return len(self.open_trades)

    def get_open_position_value(self, current_price: float) -> float:
        """Get total value of all open positions."""
        total_value = 0.0
        for trade in self.open_trades.values():
            total_value += trade.lot_size * current_price
        return total_value

    def clear_closed_trades(self) -> None:
        """Clear closed trades history."""
        self.closed_trades.clear()
        logger.info("Closed trades history cleared")
