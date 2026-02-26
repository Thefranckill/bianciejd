"""
bot.py
------
Bot de trading asíncrono con:
- Señales de Google Gemini
- Position sizing dinámico (Kelly Criterion)
- Reconexión automática con recuperación de estado
- Alertas por Telegram
- Resumen diario automático
"""

import asyncio
import time
import json
from pathlib import Path
from loguru import logger

from exchange        import BinanceExchange
from gemini_signal   import GeminiSignal
from config          import Config
from logger          import TradeLogger
from position_sizing import PositionSizer
from telegram_alerts import TelegramAlerter

MIN_CONFIDENCE  = 0.65
GEMINI_INTERVAL = 60
STATE_FILE      = Path("logs/bot_state.json")
MAX_RECONNECT_ATTEMPTS = 10


class TradingBot:

    def __init__(self):
        self.exchange    = BinanceExchange()
        self.gemini      = GeminiSignal()
        self.trade_log   = TradeLogger()
        self.sizer       = PositionSizer()
        self.telegram    = TelegramAlerter()
        self.symbol      = Config.TRADING_PAIR

        # Estado de posición
        self.in_position  = False
        self.entry_price  = 0.0
        self.entry_qty    = 0.0
        self.entry_amount = 0.0  # USDT invertidos

        # Buffers
        self._prices  = []
        self._volumes = []
        self._running = False
        self._last_gemini_call  = 0.0
        self._last_daily_report = 0.0
        self._reconnect_attempts = 0

        # Restaurar estado si el bot se cayó con posición abierta
        self._load_state()

    # ── Estado persistente ─────────────────────────────────────────────
    def _save_state(self):
        STATE_FILE.parent.mkdir(exist_ok=True)
        state = {
            "in_position":  self.in_position,
            "entry_price":  self.entry_price,
            "entry_qty":    self.entry_qty,
            "entry_amount": self.entry_amount,
            "symbol":       self.symbol,
            "timestamp":    time.time(),
        }
        STATE_FILE.write_text(json.dumps(state, indent=2))

    def _load_state(self):
        if not STATE_FILE.exists():
            return
        try:
            state = json.loads(STATE_FILE.read_text())
            # Solo restaurar si el estado tiene menos de 24h
            if time.time() - state.get("timestamp", 0) < 86400:
                self.in_position  = state.get("in_position", False)
                self.entry_price  = state.get("entry_price", 0.0)
                self.entry_qty    = state.get("entry_qty", 0.0)
                self.entry_amount = state.get("entry_amount", 0.0)
                if self.in_position:
                    logger.warning(
                        f"🔄 Estado restaurado: posición abierta en {self.symbol} "
                        f"@ ${self.entry_price:.2f} ({self.entry_qty:.6f} unidades)"
                    )
        except Exception as e:
            logger.warning(f"No se pudo restaurar estado: {e}")

    def _clear_state(self):
        self.in_position  = False
        self.entry_price  = 0.0
        self.entry_qty    = 0.0
        self.entry_amount = 0.0
        self._save_state()

    # ── WebSocket callback ─────────────────────────────────────────────
    def _on_price(self, symbol: str, price: float):
        self._prices.append(price)
        if len(self._prices) > 1500:
            self._prices.pop(0)

        if self.in_position:
            action = self.exchange.check_risk(symbol, self.entry_price, price)
            if action:
                asyncio.create_task(self._exit_position(reason=action, price=price))

    # ── Operaciones ────────────────────────────────────────────────────
    async def _enter_position(self, price: float, reason: str = "GEMINI_BUY"):
        # Calcular tamaño dinámico
        balance = await self.exchange.get_balance("USDT")
        amount  = self.sizer.calculate(balance, price)

        if amount < 10:
            logger.warning(f"Capital insuficiente para operar (${balance:.2f} disponible)")
            return

        logger.info(f"📥 Entrando @ ${price:.2f} | Invertir: ${amount:.2f} ({reason})")
        order = await self.exchange.buy_market(self.symbol, amount)

        self.in_position  = True
        self.entry_price  = price
        self.entry_qty    = float(order.get("executedQty", amount / price))
        self.entry_amount = amount
        self._save_state()

        self.trade_log.log_trade({
            "action": "BUY", "symbol": self.symbol,
            "price": price, "qty": self.entry_qty,
            "reason": reason, "timestamp": time.time(),
        })
        await self.telegram.alert_buy(self.symbol, price, self.entry_qty, amount, reason)

    async def _exit_position(self, reason: str, price: float):
        if not self.in_position:
            return

        logger.info(f"📤 Saliendo ({reason}) @ ${price:.2f}")
        await self.exchange.sell_market(self.symbol, self.entry_qty)

        pnl = (price - self.entry_price) * self.entry_qty
        logger.info(f"💰 PnL: ${pnl:+.4f} | Motivo: {reason}")

        # Actualizar position sizer con resultado
        self.sizer.update(pnl)

        self.trade_log.log_trade({
            "action": "SELL", "symbol": self.symbol,
            "price": price, "qty": self.entry_qty,
            "pnl": pnl, "reason": reason,
            "timestamp": time.time(),
        })

        # Alertas específicas por tipo
        if reason == "STOP_LOSS":
            await self.telegram.alert_stop_loss(self.symbol, price, pnl)
        elif reason == "TAKE_PROFIT":
            await self.telegram.alert_take_profit(self.symbol, price, pnl)
        else:
            await self.telegram.alert_sell(self.symbol, price, self.entry_qty, pnl, reason)

        self._clear_state()

    # ── Resumen diario ─────────────────────────────────────────────────
    async def _check_daily_report(self):
        now = time.time()
        # Enviar reporte cada 24h
        if now - self._last_daily_report < 86400:
            return
        self._last_daily_report = now

        trades = self.trade_log.load_trades()
        today_trades = [t for t in trades
                        if t.get("timestamp", "").startswith(time.strftime("%Y-%m-%d"))]
        if not today_trades:
            return

        pnls     = [float(t.get("pnl") or 0) for t in today_trades]
        total    = sum(pnls)
        wins     = len([p for p in pnls if p > 0])
        win_rate = wins / len(pnls) if pnls else 0
        balance  = await self.exchange.get_balance("USDT")
        await self.telegram.alert_daily_summary(len(today_trades), total, win_rate, balance)

    # ── Loop principal ─────────────────────────────────────────────────
    async def _decision_loop(self):
        logger.info(f"🧠 Motor: Gemini | Intervalo: {GEMINI_INTERVAL}s | Confianza mín: {MIN_CONFIDENCE:.0%}")
        while self._running:
            now   = time.time()
            price = self.exchange.get_cached_price(self.symbol)

            if price and len(self._prices) >= 30:
                if now - self._last_gemini_call >= GEMINI_INTERVAL:
                    self._last_gemini_call = now
                    result     = await self.gemini.get_signal({
                        "symbol":  self.symbol,
                        "prices":  list(self._prices),
                        "volumes": list(self._volumes),
                    })
                    signal     = result.get("signal", "HOLD")
                    confidence = result.get("confidence", 0.0)

                    if confidence >= MIN_CONFIDENCE:
                        if signal == "BUY" and not self.in_position:
                            await self._enter_position(price, f"GEMINI({confidence:.0%})")
                        elif signal == "SELL" and self.in_position:
                            await self._exit_position(f"GEMINI({confidence:.0%})", price)

            await self._check_daily_report()
            await asyncio.sleep(1)

    # ── Reconexión automática ──────────────────────────────────────────
    async def _run_with_reconnect(self):
        while self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            try:
                async with self.exchange:
                    self._reconnect_attempts = 0  # reset en conexión exitosa
                    await self.exchange.start_price_stream(self.symbol, callback=self._on_price)
                    self._running = True
                    logger.info(f"🤖 Bot iniciado — {self.symbol} | DRY_RUN: {Config.DRY_RUN}")
                    await self.telegram.alert_bot_start(self.symbol, Config.DRY_RUN)
                    await self._decision_loop()

            except asyncio.CancelledError:
                logger.info("Bot detenido por el usuario.")
                break

            except Exception as e:
                self._reconnect_attempts += 1
                wait = min(30 * self._reconnect_attempts, 300)  # máximo 5 minutos
                logger.error(f"❌ Error inesperado: {e}")
                logger.warning(f"🔄 Reconectando en {wait}s (intento {self._reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
                await self.telegram.alert_error(str(e))
                await self.telegram.alert_reconnect(self._reconnect_attempts)
                self._running = False
                await asyncio.sleep(wait)

        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            logger.error("❌ Máximo de reconexiones alcanzado. Bot detenido.")
            await self.telegram.alert_error("Máximo de reconexiones alcanzado. Bot detenido.")

    async def run(self):
        try:
            await self._run_with_reconnect()
        finally:
            self._running = False
            await self.gemini.close()
            await self.telegram.close()

    async def panic(self):
        async with self.exchange:
            results = await self.exchange.close_all_positions()
        await self.telegram.alert_panic(len(results))
        self._clear_state()
        await self.telegram.close()
