"""
telegram_alerts.py
------------------
Alertas por Telegram para eventos importantes del bot.
Configura en .env:
    TELEGRAM_BOT_TOKEN=123456:ABC-...
    TELEGRAM_CHAT_ID=tu_chat_id

Para obtener tu CHAT_ID:
    1. Crea un bot en @BotFather en Telegram
    2. Envíale un mensaje a tu bot
    3. Visita: https://api.telegram.org/bot<TOKEN>/getUpdates
"""

import aiohttp
import asyncio
from loguru import logger
from config import Config


class TelegramAlerter:

    def __init__(self):
        self._token   = getattr(Config, "TELEGRAM_BOT_TOKEN", "")
        self._chat_id = getattr(Config, "TELEGRAM_CHAT_ID", "")
        self._enabled = bool(self._token and self._chat_id)
        self._session = None
        if self._enabled:
            logger.info("📱 Telegram alertas activadas")
        else:
            logger.info("📱 Telegram no configurado (opcional)")

    async def _get_session(self):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def send(self, message: str):
        if not self._enabled:
            return
        url     = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {
            "chat_id":    self._chat_id,
            "text":       message,
            "parse_mode": "HTML",
        }
        try:
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    logger.warning(f"Telegram error {r.status}")
        except Exception as e:
            logger.warning(f"Telegram no disponible: {e}")

    # ── Mensajes predefinidos ──────────────────────────────────────────

    async def alert_buy(self, symbol: str, price: float, qty: float, amount: float, reason: str):
        await self.send(
            f"🟢 <b>COMPRA EJECUTADA</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Par: <code>{symbol}</code>\n"
            f"Precio: <code>${price:,.2f}</code>\n"
            f"Cantidad: <code>{qty:.5f}</code>\n"
            f"Invertido: <code>${amount:.2f} USDT</code>\n"
            f"Señal: <i>{reason}</i>"
        )

    async def alert_sell(self, symbol: str, price: float, qty: float, pnl: float, reason: str):
        emoji = "💰" if pnl >= 0 else "🔴"
        await self.send(
            f"{emoji} <b>VENTA EJECUTADA</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Par: <code>{symbol}</code>\n"
            f"Precio: <code>${price:,.2f}</code>\n"
            f"PnL: <code>${pnl:+.4f} USDT</code>\n"
            f"Motivo: <i>{reason}</i>"
        )

    async def alert_stop_loss(self, symbol: str, price: float, loss: float):
        await self.send(
            f"🛑 <b>STOP LOSS ACTIVADO</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Par: <code>{symbol}</code>\n"
            f"Precio: <code>${price:,.2f}</code>\n"
            f"Pérdida: <code>${loss:.4f} USDT</code>"
        )

    async def alert_take_profit(self, symbol: str, price: float, gain: float):
        await self.send(
            f"🎯 <b>TAKE PROFIT ALCANZADO</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Par: <code>{symbol}</code>\n"
            f"Precio: <code>${price:,.2f}</code>\n"
            f"Ganancia: <code>${gain:+.4f} USDT</code>"
        )

    async def alert_panic(self, positions_closed: int):
        await self.send(
            f"⛔ <b>PÁNICO ACTIVADO</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Se cerraron <b>{positions_closed}</b> posiciones.\n"
            f"<i>Todas las operaciones han sido liquidadas.</i>"
        )

    async def alert_bot_start(self, pair: str, dry_run: bool):
        mode = "🟡 DRY RUN (simulación)" if dry_run else "🔴 LIVE (dinero real)"
        await self.send(
            f"🤖 <b>BOT INICIADO</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Par: <code>{pair}</code>\n"
            f"Modo: {mode}\n"
            f"Motor: Google Gemini 2.0"
        )

    async def alert_error(self, error: str):
        await self.send(
            f"⚠️ <b>ERROR DEL BOT</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<code>{error[:300]}</code>"
        )

    async def alert_reconnect(self, attempt: int):
        await self.send(
            f"🔄 <b>RECONEXIÓN</b>\n"
            f"El bot se reconectó a Binance (intento #{attempt})"
        )

    async def alert_daily_summary(self, trades: int, pnl: float, win_rate: float, balance: float):
        emoji = "📈" if pnl >= 0 else "📉"
        await self.send(
            f"{emoji} <b>RESUMEN DIARIO</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Operaciones: <code>{trades}</code>\n"
            f"PnL del día: <code>${pnl:+.2f} USDT</code>\n"
            f"Win Rate: <code>{win_rate:.0%}</code>\n"
            f"Balance: <code>${balance:,.2f} USDT</code>"
        )
