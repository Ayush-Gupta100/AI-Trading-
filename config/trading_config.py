from config.settings import settings

TRADING_CONFIG = {
    "initial_capital": settings.INITIAL_CAPITAL,
    "symbols": settings.TRADING_SYMBOLS,
    "rsi_period": settings.RSI_PERIOD,
    "rsi_overbought": settings.RSI_OVERBOUGHT,
    "rsi_oversold": settings.RSI_OVERSOLD,
    "max_position_size": settings.MAX_POSITION_SIZE,
    "min_trade_quantity": 1,
    "trading_hours": {
        "market_open": "09:15",
        "mid_day": "12:30",
        "market_close": "15:15"
    },
    "risk_management": {
        "max_daily_loss_pct": 0.05,
        "max_drawdown_pct": 0.15,
        "stop_loss_pct": 0.08,
        "take_profit_pct": 0.15
    }
}