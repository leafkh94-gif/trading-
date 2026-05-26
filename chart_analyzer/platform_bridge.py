"""
MetaTrader Platform Integration.
Provides bridges to MT4 and MT5 for signal transmission and account management.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, List
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class AccountInfo:
    """MetaTrader account information."""
    account_number: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit_loss: float


class BasePlatformBridge(ABC):
    """Abstract base for platform integrations."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to platform."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Close connection to platform."""
        pass
    
    @abstractmethod
    def send_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        comment: str = ""
    ) -> Dict:
        """Send trading order."""
        pass
    
    @abstractmethod
    def close_order(self, ticket: int, volume: float, price: float) -> Dict:
        """Close an existing order."""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Optional[AccountInfo]:
        """Retrieve account information."""
        pass


class MT4Bridge(BasePlatformBridge):
    """
    MetaTrader 4 Integration Bridge.
    
    Connects to MT4 via WebAPI (WebSocket or HTTP).
    Allows signal transmission and account monitoring.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        username: str = "",
        password: str = "",
        account_number: int = 0
    ):
        """
        Initialize MT4 bridge.
        
        Args:
            host: MT4 WebAPI server host
            port: MT4 WebAPI server port
            username: MetaTrader username
            password: MetaTrader password
            account_number: Trading account number
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.account_number = account_number
        self.is_connected = False
        self.socket = None
        logger.info(f"MT4 Bridge initialized: {host}:{port}")

    def connect(self) -> bool:
        """Connect to MT4 WebAPI."""
        try:
            # In production, use websockets library
            # import websockets
            # self.socket = websockets.connect(f"ws://{self.host}:{self.port}")
            
            logger.info(f"Connecting to MT4 at {self.host}:{self.port}")
            self.is_connected = True
            logger.info("MT4 connected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MT4: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from MT4."""
        try:
            if self.socket:
                self.socket.close()
            self.is_connected = False
            logger.info("MT4 disconnected")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from MT4: {e}")
            return False

    def send_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        comment: str = ""
    ) -> Dict:
        """
        Send trading order to MT4.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSD")
            order_type: "BUY" or "SELL"
            volume: Order volume in lots
            price: Entry price
            stop_loss: Stop-loss price
            take_profit: Take-profit price
            comment: Order comment
        
        Returns:
            Dict with order result (ticket, status, etc.)
        """
        
        if not self.is_connected:
            logger.error("MT4 not connected")
            return {"status": "error", "message": "Not connected to MT4"}
        
        try:
            order_data = {
                "action": "TRADE_ACTION_DEAL",
                "magic": 12345,  # Unique identifier for bot orders
                "symbol": symbol,
                "volume": volume,
                "type": "ORDER_TYPE_BUY" if order_type.upper() == "BUY" else "ORDER_TYPE_SELL",
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "comment": comment or f"Signal from Trading Bot"
            }
            
            # Send order via WebSocket/API
            # order_result = self.socket.send(json.dumps(order_data))
            
            logger.info(f"Order sent to MT4: {order_type} {volume} {symbol} @ {price}")
            
            return {
                "status": "success",
                "ticket": 123456,  # Mock ticket number
                "symbol": symbol,
                "volume": volume,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit
            }
        
        except Exception as e:
            logger.error(f"Error sending order to MT4: {e}")
            return {"status": "error", "message": str(e)}

    def close_order(self, ticket: int, volume: float, price: float) -> Dict:
        """Close an order on MT4."""
        if not self.is_connected:
            logger.error("MT4 not connected")
            return {"status": "error", "message": "Not connected to MT4"}
        
        try:
            close_data = {
                "action": "TRADE_ACTION_DEAL",
                "position": ticket,
                "volume": volume,
                "price": price,
                "comment": "Closed by Trading Bot"
            }
            
            logger.info(f"Closing order {ticket} at {price}")
            
            return {
                "status": "success",
                "ticket": ticket,
                "closed_price": price,
                "closed_volume": volume
            }
        
        except Exception as e:
            logger.error(f"Error closing order on MT4: {e}")
            return {"status": "error", "message": str(e)}

    def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information from MT4."""
        if not self.is_connected:
            logger.error("MT4 not connected")
            return None
        
        try:
            # Request account info from MT4
            account_data = {
                "action": "GET_ACCOUNT_INFO",
                "account": self.account_number
            }
            
            # Mock account data for demonstration
            return AccountInfo(
                account_number=self.account_number,
                balance=10000.0,
                equity=10500.0,
                margin=5000.0,
                free_margin=5500.0,
                margin_level=210.0,
                profit_loss=500.0
            )
        
        except Exception as e:
            logger.error(f"Error getting account info from MT4: {e}")
            return None


class MT5Bridge(BasePlatformBridge):
    """
    MetaTrader 5 Integration Bridge.
    
    Uses Python MT5 API for direct connection and order management.
    """
    
    def __init__(
        self,
        username: str = "",
        password: str = "",
        server: str = "default",
        account_number: int = 0
    ):
        """
        Initialize MT5 bridge.
        
        Args:
            username: MetaTrader login
            password: MetaTrader password
            server: MT5 server name
            account_number: Trading account number
        """
        self.username = username
        self.password = password
        self.server = server
        self.account_number = account_number
        self.is_connected = False
        
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
        except ImportError:
            logger.error("MetaTrader5 library not installed. Install with: pip install MetaTrader5")
            self.mt5 = None
        
        logger.info("MT5 Bridge initialized")

    def connect(self) -> bool:
        """Connect to MT5."""
        if not self.mt5:
            logger.error("MT5 library not available")
            return False
        
        try:
            if not self.mt5.initialize():
                logger.error("Failed to initialize MT5")
                return False
            
            logger.info("MT5 initialized successfully")
            self.is_connected = True
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to MT5: {e}")
            return False

    def disconnect(self) -> bool:
        """Disconnect from MT5."""
        if not self.mt5:
            return False
        
        try:
            self.mt5.shutdown()
            self.is_connected = False
            logger.info("MT5 disconnected")
            return True
        except Exception as e:
            logger.error(f"Error disconnecting from MT5: {e}")
            return False

    def send_order(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        comment: str = ""
    ) -> Dict:
        """
        Send trading order to MT5.
        """
        
        if not self.is_connected or not self.mt5:
            logger.error("MT5 not connected")
            return {"status": "error", "message": "Not connected to MT5"}
        
        try:
            # Map order type
            order_action = self.mt5.TRADE_ACTION_DEAL
            order_type_enum = self.mt5.ORDER_TYPE_BUY if order_type.upper() == "BUY" else self.mt5.ORDER_TYPE_SELL
            
            # Prepare request
            request = {
                "action": order_action,
                "symbol": symbol,
                "volume": volume,
                "type": order_type_enum,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 20,
                "magic": 12345,
                "comment": comment or "Trading Bot",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC
            }
            
            # Send order
            result = self.mt5.order_send(request)
            
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result}")
                return {"status": "error", "message": f"MT5 error: {result.retcode}"}
            
            logger.info(f"Order sent to MT5: {order_type} {volume} {symbol} @ {price}")
            
            return {
                "status": "success",
                "ticket": result.order,
                "symbol": symbol,
                "volume": volume,
                "price": price
            }
        
        except Exception as e:
            logger.error(f"Error sending order to MT5: {e}")
            return {"status": "error", "message": str(e)}

    def close_order(self, ticket: int, volume: float, price: float) -> Dict:
        """Close an order on MT5."""
        if not self.is_connected or not self.mt5:
            logger.error("MT5 not connected")
            return {"status": "error", "message": "Not connected to MT5"}
        
        try:
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": "XAUUSD",
                "volume": volume,
                "type": self.mt5.ORDER_TYPE_SELL,
                "price": price,
                "magic": 12345,
                "comment": "Closed by Trading Bot",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC
            }
            
            result = self.mt5.order_send(request)
            
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                logger.error(f"Close order failed: {result}")
                return {"status": "error", "message": str(result)}
            
            logger.info(f"Order {ticket} closed on MT5")
            
            return {
                "status": "success",
                "ticket": ticket,
                "closed_price": price
            }
        
        except Exception as e:
            logger.error(f"Error closing order on MT5: {e}")
            return {"status": "error", "message": str(e)}

    def get_account_info(self) -> Optional[AccountInfo]:
        """Get account information from MT5."""
        if not self.is_connected or not self.mt5:
            logger.error("MT5 not connected")
            return None
        
        try:
            account_info = self.mt5.account_info()
            
            if account_info is None:
                logger.error("Failed to get account info from MT5")
                return None
            
            return AccountInfo(
                account_number=account_info.login,
                balance=account_info.balance,
                equity=account_info.equity,
                margin=account_info.margin,
                free_margin=account_info.margin_free,
                margin_level=account_info.margin_level,
                profit_loss=account_info.profit
            )
        
        except Exception as e:
            logger.error(f"Error getting account info from MT5: {e}")
            return None


class PlatformFactory:
    """Factory for creating platform bridges."""
    
    @staticmethod
    def create_bridge(platform: str, **kwargs) -> Optional[BasePlatformBridge]:
        """
        Create platform bridge.
        
        Args:
            platform: "mt4" or "mt5"
            **kwargs: Platform-specific arguments
        
        Returns:
            Platform bridge instance
        """
        
        if platform.lower() == "mt4":
            return MT4Bridge(**kwargs)
        elif platform.lower() == "mt5":
            return MT5Bridge(**kwargs)
        else:
            logger.error(f"Unknown platform: {platform}")
            return None
