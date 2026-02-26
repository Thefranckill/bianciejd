"""
config.py - Carga variables de entorno desde .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


class Config:
    # Binance
    BINANCE_API_KEY:    str   = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY: str   = os.getenv("BINANCE_SECRET_KEY", "")

    # Gemini
    GEMINI_API_KEY:     str   = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_SHEET_ID:    str   = os.getenv("GOOGLE_SHEET_ID", "")

    # Telegram
    TELEGRAM_TOKEN:     str   = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID:   str   = os.getenv("TELEGRAM_CHAT_ID", "")

    # Trading
    TRADING_PAIR:       str   = os.getenv("TRADING_PAIR", "BTCUSDT")
    TRADE_AMOUNT:       float = float(os.getenv("TRADE_AMOUNT_USDT", "50"))
    STOP_LOSS_PCT:      float = float(os.getenv("STOP_LOSS_PCT", "0.015"))
    TAKE_PROFIT_PCT:    float = float(os.getenv("TAKE_PROFIT_PCT", "0.030"))
    TRAILING_STOP_PCT:  float = float(os.getenv("TRAILING_STOP_PCT", "0.010"))
    DRY_RUN:            bool  = os.getenv("DRY_RUN", "true").lower() == "true"
    LOG_LEVEL:          str   = os.getenv("LOG_LEVEL", "INFO")

    # Position Sizing
    POSITION_SIZE_PCT:  float = float(os.getenv("POSITION_SIZE_PCT", "0.05"))   # 5% del capital
    MAX_POSITIONS:      int   = int(os.getenv("MAX_POSITIONS", "1"))             # máx posiciones simultáneas
    MIN_TRADE_USDT:     float = float(os.getenv("MIN_TRADE_USDT", "10"))         # mínimo por operación
