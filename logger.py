"""
logger.py - Registro de operaciones en CSV local
"""
import csv
import time
from pathlib import Path
from loguru import logger
from config import Config

LOG_DIR   = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
TRADE_CSV = LOG_DIR / "trades.csv"
HEADERS   = ["timestamp", "action", "symbol", "price", "qty", "pnl", "reason"]

logger.add(
    LOG_DIR / "bot_{time:YYYY-MM-DD}.log",
    rotation="00:00", retention="30 days",
    level=Config.LOG_LEVEL,
    format="{time:HH:mm:ss} | {level:<8} | {message}",
)

def _init_csv():
    if not TRADE_CSV.exists():
        with open(TRADE_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=HEADERS).writeheader()


class TradeLogger:
    def __init__(self):
        _init_csv()

    def log_trade(self, trade: dict):
        row = {h: trade.get(h, "") for h in HEADERS}
        row["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(trade.get("timestamp", time.time())))
        with open(TRADE_CSV, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=HEADERS).writerow(row)

    @staticmethod
    def load_trades() -> list:
        if not TRADE_CSV.exists():
            return []
        with open(TRADE_CSV, "r") as f:
            return list(csv.DictReader(f))
