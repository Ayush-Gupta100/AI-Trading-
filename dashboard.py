import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, List

from flask import Flask, jsonify, render_template_string

from wallet.ledger import ledger

logger = logging.getLogger(__name__)

app = Flask(__name__)

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Trading Agent Dashboard</title>
    <meta http-equiv="refresh" content="60">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        h1 { color: #333; }
        h2 { color: #666; font-size: 1.2em; margin-top: 0; }
        .metric { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #666; }
        .metric-value { font-weight: 600; color: #333; }
        .positive { color: #22c55e; }
        .negative { color: #ef4444; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #eee; }
        th { color: #666; font-weight: 600; }
        .timestamp { color: #999; font-size: 0.85em; }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }
        .status-running { background: #dcfce7; color: #166534; }
        .status-stopped { background: #fee2e2; color: #991b1b; }
        .log-entry { padding: 8px; font-family: monospace; font-size: 0.85em; border-bottom: 1px solid #eee; }
        .log-entry:last-child { border-bottom: none; }
        .log-info { color: #3b82f6; }
        .log-warning { color: #f59e0b; }
        .log-error { color: #ef4444; }
        .refresh-info { color: #999; font-size: 0.85em; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AI Trading Agent Dashboard</h1>
        <div class="card">
            <div class="metric">
                <span class="metric-label">System Status</span>
                <span class="metric-value">
                    <span class="status-badge status-{{ 'running' if status == 'running' else 'stopped' }}">{{ status }}</span>
                </span>
            </div>
            <div class="metric">
                <span class="metric-label">Last Updated</span>
                <span class="metric-value">{{ last_update }}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Next Trading Cycle</span>
                <span class="metric-value">{{ next_cycle }}</span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h2>💰 Portfolio Summary</h2>
                <div class="metric">
                    <span class="metric-label">Total Value</span>
                    <span class="metric-value {% if pnl >= 0 %}positive{% else %}negative{% endif %}">Rs {{ "%.2f"|format(total_value) }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Available Cash</span>
                    <span class="metric-value">Rs {{ "%.2f"|format(cash) }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Invested</span>
                    <span class="metric-value">Rs {{ "%.2f"|format(invested) }}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">P&L</span>
                    <span class="metric-value {% if pnl >= 0 %}positive{% else %}negative{% endif %}">Rs {{ "%.2f"|format(pnl) }} ({{ "%.2f"|format(pnl_pct) }}%)</span>
                </div>
            </div>

            <div class="card">
                <h2>📊 Positions</h2>
                {% if positions %}
                <table>
                    <thead>
                        <tr><th>Symbol</th><th>Qty</th><th>Avg Price</th><th>Current</th><th>Value</th><th>P&L</th></tr>
                    </thead>
                    <tbody>
                        {% for pos in positions %}
                        <tr>
                            <td>{{ pos.symbol }}</td>
                            <td>{{ pos.quantity }}</td>
                            <td>Rs {{ "%.2f"|format(pos.avg_price) }}</td>
                            <td>Rs {{ "%.2f"|format(pos.current_price) }}</td>
                            <td>Rs {{ "%.2f"|format(pos.value) }}</td>
                            <td class="{% if pos.pnl >= 0 %}positive{% else %}negative{% endif %}">
                                Rs {{ "%.2f"|format(pos.pnl) }} ({{ "%.2f"|format(pos.pnl_pct) }}%)
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p style="color: #999;">No open positions</p>
                {% endif %}
            </div>
        </div>

        <div class="card">
            <h2>📜 Recent Transactions</h2>
            {% if transactions %}
            <table>
                <thead>
                    <tr><th>Time</th><th>Action</th><th>Symbol</th><th>Qty</th><th>Price</th><th>Total</th><th>Reason</th></tr>
                </thead>
                <tbody>
                    {% for txn in transactions %}
                    <tr>
                        <td>{{ txn.timestamp }}</td>
                        <td><strong>{{ txn.action }}</strong></td>
                        <td>{{ txn.symbol }}</td>
                        <td>{{ txn.quantity }}</td>
                        <td>Rs {{ "%.2f"|format(txn.price) }}</td>
                        <td>Rs {{ "%.2f"|format(txn.total) }}</td>
                        <td>{{ txn.reasoning }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="color: #999;">No transactions yet</p>
            {% endif %}
        </div>

        <div class="card">
            <h2>📝 Recent Logs</h2>
            <div id="logs">
                {% for log in logs %}
                <div class="log-entry log-{{ log.level }}">
                    <span class="timestamp">{{ log.time }}</span>
                    <span>{{ log.message }}</span>
                </div>
                {% endfor %}
            </div>
        </div>

        <p class="refresh-info">Auto-refreshes every 60 seconds | Last update: {{ last_update }}</p>
    </div>
</body>
</html>
"""

_log_buffer: List[Dict[str, Any]] = []
_MAX_LOGS = 100


class LogCaptureHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            _log_buffer.append({
                "time": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname.lower(),
                "message": msg
            })
            if len(_log_buffer) > _MAX_LOGS:
                _log_buffer.pop(0)
        except Exception:
            pass


def get_portfolio_data() -> Dict[str, Any]:
    wallet = ledger.get_wallet()
    cash = float(wallet.get("cash", 0))
    positions = wallet.get("positions", {})
    total_value = float(wallet.get("total_value", cash))

    pos_list = []
    invested = 0
    for symbol, pos in positions.items():
        qty = float(pos.get("quantity", 0))
        avg = float(pos.get("avg_price", 0))
        value = qty * avg
        invested += value
        pos_list.append({
            "symbol": symbol,
            "quantity": qty,
            "avg_price": avg,
            "current_price": avg,
            "value": value,
            "pnl": 0,
            "pnl_pct": 0
        })

    pnl = total_value - 500
    pnl_pct = (pnl / 500) * 100 if 500 > 0 else 0

    transactions = ledger.get_transaction_history(20)
    txn_list = []
    for t in transactions:
        txn_list.append({
            "timestamp": t.get("timestamp", "").strftime("%Y-%m-%d %H:%M") if hasattr(t.get("timestamp", ""), "strftime") else str(t.get("timestamp", "")),
            "action": t.get("action", ""),
            "symbol": t.get("symbol", ""),
            "quantity": float(t.get("quantity", 0)),
            "price": float(t.get("price", 0)),
            "total": float(t.get("total", 0)),
            "reasoning": t.get("reasoning", "")
        })

    return {
        "cash": cash,
        "total_value": total_value,
        "invested": invested,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "positions": pos_list,
        "transactions": txn_list
    }


def get_system_status() -> Dict[str, Any]:
    return {
        "status": "running",
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "next_cycle": "Scheduled (09:15, 12:30, 15:15 IST)",
        "uptime_seconds": int(time.time() - _start_time)
    }


_start_time = time.time()


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/health/detailed")
def health_detailed():
    wallet = ledger.get_wallet()
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "wallet_initialized": wallet is not None,
        "cash": float(wallet.get("cash", 0)),
        "total_value": float(wallet.get("total_value", 0)),
        "positions_count": len(wallet.get("positions", {}))
    })


@app.route("/dashboard")
def dashboard():
    portfolio = get_portfolio_data()
    status = get_system_status()
    return render_template_string(DASHBOARD_TEMPLATE,
        status=status["status"],
        last_update=status["last_update"],
        next_cycle=status["next_cycle"],
        **portfolio,
        logs=_log_buffer[-50:]
    )


@app.route("/api/portfolio")
def api_portfolio():
    return jsonify(get_portfolio_data())


@app.route("/api/logs")
def api_logs():
    return jsonify({"logs": _log_buffer[-100:]})


def start_dashboard(host: str = "0.0.0.0", port: int = 8080):
    log_handler = LogCaptureHandler()
    log_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(log_handler)

    def run():
        logger.info(f"Dashboard starting on http://{host}:{port}")
        app.run(host=host, port=port, debug=False, use_reloader=False)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    start_dashboard()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass