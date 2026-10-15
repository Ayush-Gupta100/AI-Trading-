import logging
from typing import Dict, List, Optional

from config.settings import settings
from data.market_data import fetch_rsi_for_symbols, get_current_price

logger = logging.getLogger(__name__)


def screen_oversold(symbols: List[str] = None, threshold: int = None) -> List[Dict]:
    symbols = symbols or settings.TRADING_SYMBOLS
    threshold = threshold or settings.RSI_OVERSOLD

    rsi_data = fetch_rsi_for_symbols(symbols)
    oversold = []

    for symbol, rsi in rsi_data.items():
        if rsi < threshold:
            price = get_current_price(symbol)
            oversold.append({
                "symbol": symbol,
                "rsi": rsi,
                "current_price": price,
                "signal": "OVERSOLD"
            })
            logger.info(f"Oversold signal: {symbol} RSI={rsi}")

    return oversold


def screen_overbought(symbols: List[str] = None, threshold: int = None) -> List[Dict]:
    symbols = symbols or settings.TRADING_SYMBOLS
    threshold = threshold or settings.RSI_OVERBOUGHT

    rsi_data = fetch_rsi_for_symbols(symbols)
    overbought = []

    for symbol, rsi in rsi_data.items():
        if rsi > threshold:
            price = get_current_price(symbol)
            overbought.append({
                "symbol": symbol,
                "rsi": rsi,
                "current_price": price,
                "signal": "OVERBOUGHT"
            })
            logger.info(f"Overbought signal: {symbol} RSI={rsi}")

    return overbought


def screen_all(symbols: List[str] = None) -> Dict[str, List[Dict]]:
    return {
        "oversold": screen_oversold(symbols),
        "overbought": screen_overbought(symbols)
    }


def get_trade_candidates(wallet_positions: Dict) -> Dict[str, List[Dict]]:
    signals = screen_all()

    buy_candidates = []
    for item in signals["oversold"]:
        if item["symbol"] not in wallet_positions:
            buy_candidates.append(item)

    sell_candidates = []
    for item in signals["overbought"]:
        if item["symbol"] in wallet_positions:
            sell_candidates.append(item)

    return {
        "buy_candidates": buy_candidates,
        "sell_candidates": sell_candidates
    }