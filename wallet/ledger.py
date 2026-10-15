import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from logtail import LogtailHandler

from config.settings import settings


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if settings.LOGMUX_TOKEN:
    try:
        handler = LogtailHandler(source_token=settings.LOGMUX_TOKEN)
        logger.addHandler(handler)
        logger.info("Logtail handler initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Logtail: {e}. Falling back to console logging.")
        logger.addHandler(logging.StreamHandler())
else:
    logger.addHandler(logging.StreamHandler())
    logger.info("LOGMUX_TOKEN not set. Using console logging fallback.")


class Ledger:
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self.wallet_collection = None
        self.transactions_collection = None
        self._connect()

    def _connect(self) -> None:
        if not settings.MONGO_URI:
            logger.error("MONGO_URI not configured. Ledger will operate in memory-only mode.")
            return

        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                self.client = MongoClient(
                    settings.MONGO_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=5000
                )
                self.client.admin.command('ping')
                self.db = self.client["trading_agent"]
                self.wallet_collection = self.db["wallet"]
                self.transactions_collection = self.db["transactions"]
                logger.info("MongoDB connection established successfully")
                return
            except ConnectionFailure as e:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"MongoDB connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {delay}s...")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(delay)
                else:
                    logger.error("All MongoDB connection attempts failed. Ledger operating in memory-only mode.")
                    self.client = None

    def initialize_wallet(self, initial_capital: float = None) -> Dict[str, Any]:
        capital = initial_capital if initial_capital is not None else settings.INITIAL_CAPITAL

        wallet_doc = {
            "cash": float(capital),
            "positions": {},
            "total_value": float(capital),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        if self.wallet_collection is not None:
            try:
                existing = self.wallet_collection.find_one({})
                if existing:
                    logger.info("Wallet already exists, skipping initialization")
                    return existing
                self.wallet_collection.insert_one(wallet_doc)
                logger.info(f"Wallet initialized with Rs {capital}")
            except OperationFailure as e:
                logger.error(f"Failed to initialize wallet in MongoDB: {e}")

        # Return with Decimal for internal use
        wallet_doc["cash"] = Decimal(str(capital))
        wallet_doc["total_value"] = Decimal(str(capital))
        return wallet_doc

    def get_wallet(self) -> Dict[str, Any]:
        if self.wallet_collection is not None:
            try:
                wallet = self.wallet_collection.find_one({})
                if wallet:
                    wallet["cash"] = Decimal(str(wallet["cash"]))
                    wallet["total_value"] = Decimal(str(wallet["total_value"]))
                    for sym, pos in wallet.get("positions", {}).items():
                        pos["quantity"] = Decimal(str(pos["quantity"]))
                        pos["avg_price"] = Decimal(str(pos["avg_price"]))
                    return wallet
            except OperationFailure as e:
                logger.error(f"Failed to fetch wallet from MongoDB: {e}")

        return self.initialize_wallet()

    def update_wallet(self, wallet: Dict[str, Any]) -> bool:
        if self.wallet_collection is None:
            return False

        wallet["updated_at"] = datetime.utcnow()
        wallet_to_save = wallet.copy()
        wallet_to_save["cash"] = float(wallet["cash"])
        wallet_to_save["total_value"] = float(wallet["total_value"])
        for sym, pos in wallet_to_save.get("positions", {}).items():
            pos["quantity"] = float(pos["quantity"])
            pos["avg_price"] = float(pos["avg_price"])

        try:
            self.wallet_collection.replace_one({}, wallet_to_save, upsert=True)
            return True
        except OperationFailure as e:
            logger.error(f"Failed to update wallet in MongoDB: {e}")
            return False

    def log_transaction(
        self,
        action: str,
        symbol: str,
        quantity: float,
        price: float,
        reasoning: str = "",
        success: bool = True
    ) -> bool:
        transaction = {
            "timestamp": datetime.utcnow(),
            "action": action.upper(),
            "symbol": symbol,
            "quantity": Decimal(str(quantity)),
            "price": Decimal(str(price)),
            "total": Decimal(str(quantity * price)),
            "reasoning": reasoning,
            "success": success
        }

        logger.info(
            f"Transaction: {action.upper()} {quantity} {symbol} @ Rs {price:.2f} | Reason: {reasoning}",
            extra={"transaction": transaction}
        )

        if self.transactions_collection is not None:
            try:
                txn_to_save = transaction.copy()
                txn_to_save["quantity"] = float(txn_to_save["quantity"])
                txn_to_save["price"] = float(txn_to_save["price"])
                txn_to_save["total"] = float(txn_to_save["total"])
                self.transactions_collection.insert_one(txn_to_save)
                return True
            except OperationFailure as e:
                logger.error(f"Failed to log transaction to MongoDB: {e}")

        return False

    def execute_buy(self, symbol: str, quantity: float, price: float, reasoning: str) -> bool:
        wallet = self.get_wallet()
        total_cost = Decimal(str(quantity * price))

        if wallet["cash"] < total_cost:
            logger.warning(f"Insufficient funds: Rs {wallet['cash']} available, Rs {total_cost} required")
            self.log_transaction("BUY", symbol, quantity, price, reasoning, success=False)
            return False

        wallet["cash"] -= total_cost

        if symbol in wallet["positions"]:
            pos = wallet["positions"][symbol]
            total_qty = pos["quantity"] + Decimal(str(quantity))
            pos["avg_price"] = ((pos["avg_price"] * pos["quantity"]) + total_cost) / total_qty
            pos["quantity"] = total_qty
        else:
            wallet["positions"][symbol] = {
                "quantity": Decimal(str(quantity)),
                "avg_price": Decimal(str(price))
            }

        wallet["total_value"] = wallet["cash"] + sum(
            pos["quantity"] * pos["avg_price"] for pos in wallet["positions"].values()
        )

        success = self.update_wallet(wallet)
        if success:
            self.log_transaction("BUY", symbol, quantity, price, reasoning, success=True)
        return success

    def execute_sell(self, symbol: str, quantity: float, price: float, reasoning: str) -> bool:
        wallet = self.get_wallet()

        if symbol not in wallet["positions"]:
            logger.warning(f"No position in {symbol} to sell")
            self.log_transaction("SELL", symbol, quantity, price, reasoning, success=False)
            return False

        pos = wallet["positions"][symbol]
        if pos["quantity"] < Decimal(str(quantity)):
            logger.warning(f"Insufficient quantity: {pos['quantity']} available, {quantity} requested")
            self.log_transaction("SELL", symbol, quantity, price, reasoning, success=False)
            return False

        total_proceeds = Decimal(str(quantity * price))
        wallet["cash"] += total_proceeds
        pos["quantity"] -= Decimal(str(quantity))

        if pos["quantity"] == 0:
            del wallet["positions"][symbol]

        wallet["total_value"] = wallet["cash"] + sum(
            p["quantity"] * p["avg_price"] for p in wallet["positions"].values()
        )

        success = self.update_wallet(wallet)
        if success:
            self.log_transaction("SELL", symbol, quantity, price, reasoning, success=True)
        return success

    def get_transaction_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        if self.transactions_collection is None:
            return []

        try:
            cursor = self.transactions_collection.find().sort("timestamp", -1).limit(limit)
            return list(cursor)
        except OperationFailure as e:
            logger.error(f"Failed to fetch transaction history: {e}")
            return []

    def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


ledger = Ledger()