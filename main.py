"""
main.py
-------
Punto de entrada del bot.
Uso:
    python main.py          # Inicia el bot de trading
    python main.py --panic  # Cierra todas las posiciones y sale
"""

import asyncio
import sys
import os

# Asegura que la raiz del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from bot import TradingBot


async def main():
    bot = TradingBot()
    if "--panic" in sys.argv:
        logger.warning("Modo PANICO activado desde CLI.")
        await bot.panic()
        return
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario (Ctrl+C).")
