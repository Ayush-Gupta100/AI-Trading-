import logging
import signal
import sys
import threading
import time
from typing import Dict, Any

import schedule

from config.settings import settings
from wallet.ledger import ledger
from agent.router import route_decision
from agent.executor import executor
from data.market_data import fetch_rsi_for_symbols
from dashboard import start_dashboard

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

SHUTDOWN = False


def signal_handler(signum, frame):
    global SHUTDOWN
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    SHUTDOWN = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def fetch_market_data() -> Dict[str, float]:
    return fetch_rsi_for_symbols(settings.TRADING_SYMBOLS)


def execute_trading_cycle():
    logger.info("=" * 50)
    logger.info("Starting trading cycle")

    market_data = fetch_market_data()
    if not market_data:
        logger.error("No market data available, skipping cycle")
        return

    decision = route_decision(market_data)

    wallet_before = ledger.get_wallet()
    logger.info(f"Portfolio before: Cash=Rs {wallet_before['cash']:.2f}, Total=Rs {wallet_before['total_value']:.2f}")

    success = executor.execute_decision(decision)

    wallet_after = ledger.get_wallet()
    logger.info(f"Portfolio after: Cash=Rs {wallet_after['cash']:.2f}, Total=Rs {wallet_after['total_value']:.2f}")

    if success:
        logger.info(f"Trade executed successfully: {decision['action']} {decision['quantity']} {decision['symbol']}")
    else:
        logger.error(f"Trade failed: {decision['action']} {decision['quantity']} {decision['symbol']}")

    logger.info("Trading cycle complete")
    logger.info("=" * 50)


def special_algo_loop():
    logger.info("Special algo background loop started")
    cycle = 0
    while not SHUTDOWN:
        cycle += 1
        logger.debug(f"Special algo heartbeat #{cycle}")
        time.sleep(60)
    logger.info("Special algo background loop stopped")


def run_scheduler():
    schedule.every().day.at("09:15").do(execute_trading_cycle)
    schedule.every().day.at("12:30").do(execute_trading_cycle)
    schedule.every().day.at("15:15").do(execute_trading_cycle)

    logger.info("Scheduler started. Trading cycles scheduled at 09:15, 12:30, 15:15 IST")

    while not SHUTDOWN:
        schedule.run_pending()
        time.sleep(1)

    logger.info("Scheduler stopped")


def main():
    logger.info("AI Trading Agent starting up...")
    logger.info(f"Initial capital: Rs {settings.INITIAL_CAPITAL}")
    logger.info(f"Trading symbols: {settings.TRADING_SYMBOLS}")

    ledger.initialize_wallet(settings.INITIAL_CAPITAL)

    wallet = ledger.get_wallet()
    logger.info(f"Wallet initialized: Cash=Rs {wallet['cash']:.2f}")

    algo_thread = threading.Thread(target=special_algo_loop, daemon=True)
    algo_thread.start()
    logger.info("Background special algo thread started")

    dashboard_thread = start_dashboard(host="0.0.0.0", port=8080)
    logger.info("Dashboard started on http://0.0.0.0:8080 (health: /health, dashboard: /dashboard)")

    try:
        run_scheduler()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.exception(f"Unexpected error in main loop: {e}")
    finally:
        logger.info("Shutting down...")
        ledger.close()
        logger.info("AI Trading Agent stopped")


if __name__ == "__main__":
    main()