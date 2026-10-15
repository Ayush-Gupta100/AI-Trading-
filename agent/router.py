import json
import logging
import time
from typing import Dict, Any, Optional

import requests

from config.settings import settings
from wallet.ledger import ledger

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
You are a quantitative trading AI managing a portfolio of Indian stocks with Rs 500 initial capital.

CURRENT PORTFOLIO:
Cash: Rs {cash:.2f}
Positions: {positions}
Total Value: Rs {total_value:.2f}

MARKET DATA (RSI):
{market_data}

TRADING RULES:
- Maximum 10% of portfolio per position
- Only trade when RSI < 30 (oversold) for BUY or RSI > 70 (overbought) for SELL
- Minimum trade quantity: 1 share
- Reasoning must be concise

Respond ONLY with valid JSON in this exact format:
{{
  "action": "BUY|SELL|HOLD",
  "symbol": "SYMBOL.NS",
  "quantity": 1,
  "reasoning": "Brief reason based on RSI and portfolio constraints"
}}

If HOLD, set quantity to 0 and symbol to "".
"""

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_groq(prompt: str) -> Optional[Dict[str, Any]]:
    if not settings.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set, skipping Groq")
        return None

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }

    try:
        resp = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=settings.REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except requests.Timeout:
        logger.warning("Groq request timed out")
    except requests.RequestException as e:
        logger.warning(f"Groq request failed: {e}")
    except (KeyError, json.JSONDecodeError) as e:
        logger.warning(f"Groq response parsing failed: {e}")
    return None


def _call_openrouter(prompt: str) -> Optional[Dict[str, Any]]:
    if not settings.OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set, skipping OpenRouter")
        return None

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/ai-trading-agent",
        "X-Title": "AI Trading Agent"
    }
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=settings.REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except requests.Timeout:
        logger.warning("OpenRouter request timed out")
    except requests.RequestException as e:
        logger.warning(f"OpenRouter request failed: {e}")
    except (KeyError, json.JSONDecodeError) as e:
        logger.warning(f"OpenRouter response parsing failed: {e}")
    return None


def _validate_decision(decision: Dict[str, Any]) -> bool:
    required_keys = {"action", "symbol", "quantity", "reasoning"}
    if not all(k in decision for k in required_keys):
        return False

    if decision["action"] not in {"BUY", "SELL", "HOLD"}:
        return False

    if decision["action"] == "HOLD":
        return decision["quantity"] == 0 and decision["symbol"] == ""

    if not isinstance(decision["quantity"], (int, float)) or decision["quantity"] < 1:
        return False

    if not isinstance(decision["symbol"], str) or not decision["symbol"]:
        return False

    return True


def _fallback_decision(market_data: Dict[str, float], wallet: Dict[str, Any]) -> Dict[str, Any]:
    cash = float(wallet.get("cash", 0))
    positions = wallet.get("positions", {})

    for symbol, rsi in market_data.items():
        if rsi < settings.RSI_OVERSOLD and cash > 0:
            max_spend = cash * settings.MAX_POSITION_SIZE
            price_estimate = 100.0
            qty = max(1, int(max_spend / price_estimate))
            if qty > 0:
                return {
                    "action": "BUY",
                    "symbol": symbol,
                    "quantity": qty,
                    "reasoning": f"RSI {rsi:.1f} oversold, fallback rule-based buy"
                }

        if rsi > settings.RSI_OVERBOUGHT and symbol in positions:
            pos = positions[symbol]
            qty = min(int(pos.get("quantity", 0)), 1)
            if qty > 0:
                return {
                    "action": "SELL",
                    "symbol": symbol,
                    "quantity": qty,
                    "reasoning": f"RSI {rsi:.1f} overbought, fallback rule-based sell"
                }

    return {"action": "HOLD", "symbol": "", "quantity": 0, "reasoning": "No actionable signals"}


def route_decision(market_data: Dict[str, float]) -> Dict[str, Any]:
    wallet = ledger.get_wallet()
    cash = float(wallet.get("cash", 0))
    positions = wallet.get("positions", {})
    total_value = float(wallet.get("total_value", 0))

    pos_str = ", ".join(
        f"{sym}: {pos['quantity']} shares @ Rs {pos['avg_price']:.2f}"
        for sym, pos in positions.items()
    ) or "None"

    mkt_str = "\n".join(f"{sym}: RSI {rsi:.1f}" for sym, rsi in market_data.items())

    prompt = PROMPT_TEMPLATE.format(
        cash=cash,
        positions=pos_str,
        total_value=total_value,
        market_data=mkt_str
    )

    logger.info("Requesting decision from Groq...")
    decision = _call_groq(prompt)

    if decision is None:
        logger.info("Groq unavailable, falling back to OpenRouter...")
        decision = _call_openrouter(prompt)

    if decision is None:
        logger.warning("Both LLM providers failed, using rule-based fallback")
        decision = _fallback_decision(market_data, wallet)

    if not _validate_decision(decision):
        logger.warning(f"Invalid decision format: {decision}, using fallback")
        decision = _fallback_decision(market_data, wallet)

    logger.info(f"Final decision: {decision}")
    return decision