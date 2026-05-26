"""
Trading Bot Platform - Comprehensive Demo

Demonstrates:
- AI-powered chart analysis for market data
- Multiple trading strategies (Scalping, Breakout, AI)
- Risk management and position sizing
- Generic market monitoring and alerts
- Performance tracking
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

from chart_analyzer import (
    TradingBot, BotConfig,
    RiskManager, RiskParameters,
    PositionManager,
    ScalpingStrategy, BreakoutStrategy, AIStrategy,
    AlertManager, AlertType, AlertLevel,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_sample_market_data(periods: int = 100) -> pd.DataFrame:
    """Generate realistic market price data for demonstration."""
    
    dates = pd.date_range('2024-01-01', periods=periods, freq='1H')
    
    # Start price around typical gold levels
    start_price = 2050.0
    
    # Generate realistic price movement
    returns = np.random.normal(0.0001, 0.005, periods)
    prices = start_price * np.exp(np.cumsum(returns))
    
    data = pd.DataFrame({
        'datetime': dates,
        'open': prices * (1 + np.random.uniform(-0.002, 0.002, periods)),
        'high': prices + np.abs(np.random.normal(0, 3, periods)),
        'low': prices - np.abs(np.random.normal(0, 3, periods)),
        'close': prices,
        'volume': np.random.uniform(1000000, 5000000, periods),
    })
    
    return data


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators for the data."""
    
    from talib import RSI, MACD, SMA, ATR
    
    close = data['close'].values
    high = data['high'].values
    low = data['low'].values
    
    # RSI (14-period)
    data['rsi'] = RSI(close, timeperiod=14)
    
    # MACD
    data['macd'], data['signal_line'], _ = MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    
    # Moving Averages
    data['ma_fast'] = SMA(close, timeperiod=9)
    data['ma_slow'] = SMA(close, timeperiod=21)
    
    # ATR (Average True Range)
    data['atr'] = ATR(high, low, close, timeperiod=14)
    
    # Fill NaN values
    data = data.fillna(method='bfill')
    
    return data


def demonstrate_bot_with_sample_data():
    """Demonstrate bot operation with sample historical data."""
    
    logger.info("=" * 70)
    logger.info("TRADING BOT PLATFORM - COMPREHENSIVE DEMONSTRATION")
    logger.info("=" * 70)
    
    # 1. Generate sample data
    logger.info("\n[1] Generating sample market data...")
    data = generate_sample_market_data(periods=100)
    
    try:
        from talib import RSI, MACD, SMA, ATR
        data = calculate_indicators(data)
        logger.info(f"✓ Generated {len(data)} periods of market data with indicators")
    except ImportError:
        logger.warning("talib not available, using manual indicators")
        # Manual indicator calculation would go here
        data['rsi'] = 50
        data['macd'] = 0
        data['signal_line'] = 0
        data['ma_fast'] = data['close']
        data['ma_slow'] = data['close']
        data['atr'] = data['close'] * 0.01
    
    # 2. Initialize Trading Bot
    logger.info("\n[2] Initializing Trading Bot...")
    
    bot_config = BotConfig(
        symbol="MARKET",
        account_equity=10000.0,
        strategy_name="scalping",
        max_trades_per_day=2,
        min_trade_confidence=0.65,
        enabled_strategies=["scalping", "breakout", "ai"]
    )
    
    risk_params = RiskParameters(
        max_risk_per_trade=1.5,
        max_daily_loss=5.0,
        max_open_positions=3,
        take_profit_ratio=2.5,
        volatility_multiplier=1.2
    )
    
    bot = TradingBot(bot_config, risk_params)
    bot.start()
    logger.info("✓ Trading bot started")
    
    # 3. Initialize Alert System
    logger.info("\n[3] Setting up Alert System...")
    alert_manager = AlertManager()
    # Note: In production, configure actual handlers:
    # alert_manager.add_handler(TelegramAlertHandler(token, chat_id))
    # alert_manager.add_handler(EmailAlertHandler(...))
    logger.info("✓ Alert manager initialized")
    
    # 4. Simulate Trading Session
    logger.info("\n[4] Simulating Trading Session...")
    logger.info(f"Trading Symbol: {bot_config.symbol}")
    logger.info(f"Initial Equity: ${bot_config.account_equity}")
    logger.info(f"Risk per Trade: {risk_params.max_risk_per_trade}%")
    logger.info(f"Max Daily Loss: {risk_params.max_daily_loss}%\n")
    
    trade_results = []
    
    # Process each candle
    for idx in range(20, len(data)):
        current_row = data.iloc[idx]
        current_price = current_row['close']
        
        # Prepare market data for analysis
        market_data = {
            'close': current_row['close'],
            'high': current_row['high'],
            'low': current_row['low'],
            'volume': current_row['volume'],
            'rsi': current_row.get('rsi', 50),
            'macd': current_row.get('macd', 0),
            'signal_line': current_row.get('signal_line', 0),
            'ma_fast': current_row.get('ma_fast', current_row['close']),
            'ma_slow': current_row.get('ma_slow', current_row['close']),
            'atr': current_row.get('atr', current_row['close'] * 0.01),
            'volatility': 1.0
        }
        
        # Analyze market with all strategies
        signals = bot.analyze_market(market_data)
        
        # Generate unified trading decision
        trade_signal = bot.generate_trading_decision(signals, market_data)
        
        # Execute trade if signal is strong enough
        if trade_signal and trade_signal.confidence >= bot_config.min_trade_confidence:
            executed = bot.validate_and_execute_trade(trade_signal, market_data)
            
            if executed:
                alert_manager.send_alert(
                    AlertType.SIGNAL_GENERATED,
                    f"Trade Signal: {trade_signal.signal_type.value.upper()}",
                    f"Confidence: {trade_signal.confidence:.2%}\n{trade_signal.reasoning}",
                    AlertLevel.INFO
                )
        
        # Update open trades with current price
        updates = bot.update_open_trades(current_price)
        
        # Record closed trades
        if updates["closed_trades"]:
            for trade in updates["closed_trades"]:
                trade_results.append(trade)
                
                if trade.profit_loss > 0:
                    alert_level = AlertLevel.INFO
                else:
                    alert_level = AlertLevel.WARNING
                
                alert_manager.send_alert(
                    AlertType.TRADE_CLOSED,
                    f"Trade Closed: {trade.trade_type.value.upper()} {trade.symbol}",
                    f"Profit/Loss: ${trade.profit_loss:.2f} ({trade.profit_loss_percent:.2f}%)\n"
                    f"Duration: {trade.get_duration_minutes():.0f} minutes",
                    alert_level
                )
    
    # 6. Performance Report
    logger.info("\n" + "=" * 70)
    logger.info("PERFORMANCE REPORT")
    logger.info("=" * 70)
    
    stats = bot.get_performance_stats()
    
    logger.info(f"\nTrade Statistics:")
    logger.info(f"  Total Trades: {stats.total_trades}")
    logger.info(f"  Winning Trades: {stats.winning_trades}")
    logger.info(f"  Losing Trades: {stats.losing_trades}")
    logger.info(f"  Win Rate: {stats.win_rate:.2f}%")
    logger.info(f"  Average P/L: ${stats.average_profit_loss:.2f}")
    logger.info(f"  Total P/L: ${stats.total_profit_loss:.2f}")
    logger.info(f"  Largest Win: ${stats.largest_win:.2f}")
    logger.info(f"  Largest Loss: ${stats.largest_loss:.2f}")
    logger.info(f"  Consecutive Wins: {stats.consecutive_wins}")
    logger.info(f"  Average Duration: {stats.average_duration_minutes:.1f} minutes")
    
    logger.info(f"\nBot Status:")
    status = bot.get_bot_status()
    for key, value in status.items():
        logger.info(f"  {key}: {value}")
    
    # 7. Strategy Comparison
    logger.info(f"\nStrategy Analysis:")
    for strategy_name, strategy in bot.strategies.items():
        if strategy.last_signal:
            logger.info(f"  {strategy_name.upper()}:")
            logger.info(f"    Last Signal: {strategy.last_signal.signal_type.value}")
            logger.info(f"    Confidence: {strategy.last_signal.confidence:.2%}")
    
    # 8. Alert Summary
    logger.info(f"\nAlert History ({len(alert_manager.alert_history)} total):")
    for alert in alert_manager.get_alert_history(limit=5):
        logger.info(f"  [{alert.level.value.upper()}] {alert.title}")
    
    logger.info("\n" + "=" * 70)
    logger.info("DEMONSTRATION COMPLETE")
    logger.info("=" * 70)
    
    bot.stop()


def demonstrate_risk_management():
    """Demonstrate risk management capabilities."""
    
    logger.info("\n" + "=" * 70)
    logger.info("RISK MANAGEMENT DEMONSTRATION")
    logger.info("=" * 70)
    
    risk_params = RiskParameters(
        max_risk_per_trade=1.5,
        max_daily_loss=5.0,
        max_open_positions=3,
        max_position_size=5.0
    )
    
    risk_mgr = RiskManager(risk_params)
    
    logger.info("\nRisk Parameters:")
    logger.info(f"  Max Risk per Trade: {risk_params.max_risk_per_trade}%")
    logger.info(f"  Max Daily Loss: {risk_params.max_daily_loss}%")
    logger.info(f"  Max Open Positions: {risk_params.max_open_positions}")
    
    # Test trade validation
    account_equity = 10000.0
    entry_price = 2050.0
    stop_loss_price = 2040.0
    
    validation = risk_mgr.validate_trade(
        account_equity=account_equity,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        current_market_price=entry_price
    )
    
    logger.info(f"\nTrade Validation Example:")
    logger.info(f"  Entry: ${entry_price}")
    logger.info(f"  Stop-Loss: ${stop_loss_price}")
    logger.info(f"  Valid: {validation.is_valid}")
    logger.info(f"  Suggested Lot Size: {validation.suggested_lot_size}")
    logger.info(f"  Suggested Take-Profit: ${validation.suggested_take_profit:.2f}")
    logger.info(f"  Reason: {validation.reason}")


if __name__ == "__main__":
    try:
        # Run main demonstration
        demonstrate_bot_with_sample_data()
        
        # Run risk management demonstration
        demonstrate_risk_management()
        
        logger.info("\n✓ All demonstrations completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("\nDemonstration interrupted by user")
    except Exception as e:
        logger.error(f"Error during demonstration: {e}", exc_info=True)


