"""
Monitoring and Alerts System.
Provides real-time alerts via email, Telegram, Discord, and webhooks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
import logging
import json

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts."""
    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    SYSTEM_ERROR = "system_error"
    SIGNAL_GENERATED = "signal_generated"
    BOT_STATUS = "bot_status"


@dataclass
class Alert:
    """Represents a trading alert."""
    alert_type: AlertType
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """Convert alert to dictionary."""
        return {
            "type": self.alert_type.value,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert alert to JSON."""
        return json.dumps(self.to_dict())


class BaseAlertHandler(ABC):
    """Abstract base for alert handlers."""
    
    @abstractmethod
    def send_alert(self, alert: Alert) -> bool:
        """Send alert through this handler."""
        pass


class EmailAlertHandler(BaseAlertHandler):
    """Send alerts via email."""
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        from_email: str,
        from_password: str,
        to_emails: List[str]
    ):
        """
        Initialize email handler.
        
        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP port
            from_email: Sender email address
            from_password: Email password
            to_emails: List of recipient emails
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.from_email = from_email
        self.from_password = from_password
        self.to_emails = to_emails
        logger.info("Email Alert Handler initialized")

    def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Create message
            message = MIMEMultipart()
            message["From"] = self.from_email
            message["To"] = ", ".join(self.to_emails)
            message["Subject"] = f"[{alert.level.value.upper()}] {alert.title}"
            
            # Email body
            body = f"""
            Trading Bot Alert
            ==================
            
            Type: {alert.alert_type.value}
            Level: {alert.level.value}
            Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            
            {alert.message}
            
            Additional Info:
            {json.dumps(alert.metadata, indent=2)}
            """
            
            message.attach(MIMEText(body, "plain"))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.from_email, self.from_password)
                server.send_message(message)
            
            logger.info(f"Email alert sent to {self.to_emails}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False


class TelegramAlertHandler(BaseAlertHandler):
    """Send alerts via Telegram."""
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram handler.
        
        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat/channel ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        logger.info("Telegram Alert Handler initialized")

    def send_alert(self, alert: Alert) -> bool:
        """Send alert via Telegram."""
        try:
            import requests
            
            message = f"""
🚨 *{alert.title}*
Level: `{alert.level.value}`
Type: `{alert.alert_type.value}`
Time: `{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}`

{alert.message}
"""
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            params = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=params)
            
            if response.status_code == 200:
                logger.info(f"Telegram alert sent to {self.chat_id}")
                return True
            else:
                logger.error(f"Telegram alert failed: {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False


class DiscordAlertHandler(BaseAlertHandler):
    """Send alerts via Discord."""
    
    def __init__(self, webhook_url: str):
        """
        Initialize Discord handler.
        
        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url
        logger.info("Discord Alert Handler initialized")

    def send_alert(self, alert: Alert) -> bool:
        """Send alert via Discord webhook."""
        try:
            import requests
            
            # Color based on alert level
            colors = {
                AlertLevel.INFO: 3447003,      # Blue
                AlertLevel.WARNING: 15105570,   # Orange
                AlertLevel.CRITICAL: 15158332,  # Red
            }
            
            payload = {
                "embeds": [{
                    "title": alert.title,
                    "description": alert.message,
                    "color": colors.get(alert.level, 3447003),
                    "fields": [
                        {"name": "Type", "value": alert.alert_type.value, "inline": True},
                        {"name": "Level", "value": alert.level.value, "inline": True},
                        {"name": "Time", "value": alert.timestamp.isoformat(), "inline": False},
                    ]
                }]
            }
            
            response = requests.post(self.webhook_url, json=payload)
            
            if response.status_code == 204:
                logger.info("Discord alert sent")
                return True
            else:
                logger.error(f"Discord alert failed: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False


class WebhookAlertHandler(BaseAlertHandler):
    """Send alerts via HTTP webhook."""
    
    def __init__(self, webhook_url: str):
        """
        Initialize webhook handler.
        
        Args:
            webhook_url: HTTP webhook URL
        """
        self.webhook_url = webhook_url
        logger.info("Webhook Alert Handler initialized")

    def send_alert(self, alert: Alert) -> bool:
        """Send alert via HTTP POST."""
        try:
            import requests
            
            response = requests.post(
                self.webhook_url,
                json=alert.to_dict(),
                timeout=10
            )
            
            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook alert sent to {self.webhook_url}")
                return True
            else:
                logger.error(f"Webhook alert failed: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class AlertManager:
    """
    Central alert management system.
    Manages multiple alert handlers and alert routing.
    """
    
    def __init__(self):
        """Initialize alert manager."""
        self.handlers: List[BaseAlertHandler] = []
        self.alert_history: List[Alert] = []
        self.muted_until: Optional[datetime] = None
        logger.info("Alert Manager initialized")

    def add_handler(self, handler: BaseAlertHandler) -> None:
        """Register an alert handler."""
        self.handlers.append(handler)
        logger.info(f"Alert handler registered: {handler.__class__.__name__}")

    def remove_handler(self, handler: BaseAlertHandler) -> None:
        """Unregister an alert handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.info(f"Alert handler removed: {handler.__class__.__name__}")

    def send_alert(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Send an alert through all registered handlers.
        
        Args:
            alert_type: Type of alert
            title: Alert title
            message: Alert message
            level: Alert severity level
            metadata: Additional metadata
        
        Returns:
            bool: True if at least one handler succeeded
        """
        
        # Check if alerts are muted
        if self.muted_until and datetime.now() < self.muted_until:
            logger.info("Alerts are muted, skipping send")
            return False
        
        alert = Alert(
            alert_type=alert_type,
            level=level,
            title=title,
            message=message,
            metadata=metadata or {}
        )
        
        # Store in history
        self.alert_history.append(alert)
        
        # Send through all handlers
        results = []
        for handler in self.handlers:
            try:
                result = handler.send_alert(alert)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in handler {handler.__class__.__name__}: {e}")
        
        success = any(results) if results else True
        
        if success:
            logger.info(f"Alert sent: {alert_type.value} - {title}")
        else:
            logger.warning(f"Alert failed: {alert_type.value} - {title}")
        
        return success

    def mute_alerts(self, minutes: int) -> None:
        """
        Mute alerts for specified minutes.
        
        Args:
            minutes: Number of minutes to mute
        """
        from datetime import timedelta
        self.muted_until = datetime.now() + timedelta(minutes=minutes)
        logger.info(f"Alerts muted for {minutes} minutes")

    def unmute_alerts(self) -> None:
        """Unmute alerts."""
        self.muted_until = None
        logger.info("Alerts unmuted")

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get recent alert history."""
        return self.alert_history[-limit:]

    def clear_history(self) -> None:
        """Clear alert history."""
        self.alert_history.clear()
        logger.info("Alert history cleared")
