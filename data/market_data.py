import logging
import time
from typing import Dict, List, Optional

import yfinance as yf

from config.settings import settings

logger = logging.getLogger(__name__)


def fetch_price_history(symbol: str, period: str = "1mo", interval: str = "1d") -> Optional[List[float]]:
    for attempt in range(3):
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval=interval)
            if hist.empty:
                logger.warning(f"No data returned for {symbol}")
                return None
            return hist["Close"].tolist()
        except Exception as e:
            delay = 2 ** attempt
            logger.warning(f"Attempt {attempt + 1}/3 failed for {symbol}: {e}. Retrying in {delay}s...")
            if attempt < 2:
                time.sleep(delay)
    logger.error(f"All attempts failed for {symbol}")
    return None


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)


def fetch_rsi_for_symbols(symbols: List[str], period: int = None) -> Dict[str, float]:
    period = period or settings.RSI_PERIOD
    rsi_data = {}

    for symbol in symbols:
        prices = fetch_price_history(symbol)
        if prices:
            rsi = calculate_rsi(prices, period)
            if rsi is not None:
                rsi_data[symbol] = rsi
            else:
                logger.warning(f"Could not calculate RSI for {symbol}")
                rsi_data[symbol] = 50.0
        else:
            rsi_data[symbol] = 50.0

    return rsi_data


def get_current_price(symbol: str) -> float:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass

    return 100.0