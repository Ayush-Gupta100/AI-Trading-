import logging
from typing import Dict, Any, Optional

from wallet.ledger import ledger
from data.market_data import get_current_price

logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(self):
        self.slippage_pct = 0.001

    def execute_market_buy(self, symbol: str, quantity: int, reasoning: str) -> bool:
        price = get_current_price(symbol)
        exec_price = price * (1 + self.slippage_pct)

        logger.info(f"Executing MARKET BUY: {quantity} {symbol} @ ~Rs {exec_price:.2f}")

        success = ledger.execute_buy(symbol, quantity, exec_price, reasoning)

        if success:
            logger.info(f"BUY filled: {quantity} {symbol} @ Rs {exec_price:.2f}")
        else:
            logger.error(f"BUY rejected: {quantity} {symbol}")

        return success

    def execute_market_sell(self, symbol: str, quantity: int, reasoning: str) -> bool:
        price = get_current_price(symbol)
        exec_price = price * (1 - self.slippage_pct)

        logger.info(f"Executing MARKET SELL: {quantity} {symbol} @ ~Rs {exec_price:.2f}")

        success = ledger.execute_sell(symbol, quantity, exec_price, reasoning)

        if success:
            logger.info(f"SELL filled: {quantity} {symbol} @ Rs {exec_price:.2f}")
        else:
            logger.error(f"SELL rejected: {quantity} {symbol}")

        return success

    def execute_decision(self, decision: Dict[str, Any]) -> bool:
        action = decision.get("action", "HOLD")
        symbol = decision.get("symbol", "")
        quantity = int(decision.get("quantity", 0))
        reasoning = decision.get("reasoning", "Automated trade")

        if action == "HOLD" or quantity <= 0:
            logger.info("No execution needed (HOLD or zero quantity)")
            return True

        if action == "BUY":
            return self.execute_market_buy(symbol, quantity, reasoning)
        elif action == "SELL":
            return self.execute_market_sell(symbol, quantity, reasoning)

        logger.warning(f"Unknown action: {action}")
        return False


executor = OrderExecutor()