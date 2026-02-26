"""
exchange.py
-----------
Cliente asincrono para Binance Spot Trading.
WebSocket para precio en tiempo real + REST para ordenes.
"""

import asyncio
import time
from typing import Optional, Callable, Dict
from decimal import Decimal, ROUND_DOWN

from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException, BinanceRequestException
from loguru import logger
from config import Config


class RateLimiter:
    def __init__(self, max_calls=1200, period=60.0):
        self._max, self._period, self._calls = max_calls, period, []

    async def wait(self):
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < self._period]
        if len(self._calls) >= self._max:
            sleep_for = self._period - (now - self._calls[0]) + 0.1
            logger.warning(f"Rate limit. Esperando {sleep_for:.1f}s")
            await asyncio.sleep(sleep_for)
        self._calls.append(time.monotonic())


class BinanceExchange:

    def __init__(self):
        self._client = None
        self._bsm    = None
        self._rl     = RateLimiter()
        self._price_cache: Dict[str, float] = {}
        self._ws_task = None
        self._trailing_high: Dict[str, float] = {}

    async def __aenter__(self):
        await self.connect(); return self

    async def __aexit__(self, *_):
        await self.disconnect()

    async def connect(self):
        logger.info("Conectando a Binance...")
        self._client = await AsyncClient.create(Config.BINANCE_API_KEY, Config.BINANCE_SECRET_KEY)
        self._bsm    = BinanceSocketManager(self._client)
        logger.info("Conexion Binance establecida.")

    async def disconnect(self):
        if self._ws_task:
            self._ws_task.cancel()
        if self._client:
            await self._client.close_connection()

    async def start_price_stream(self, symbol: str, callback: Optional[Callable] = None):
        async def _run():
            async with self._bsm.symbol_ticker_socket(symbol.lower()) as stream:
                logger.info(f"WebSocket activo para {symbol}")
                while True:
                    msg   = await stream.recv()
                    price = float(msg["c"])
                    self._price_cache[symbol] = price
                    if callback:
                        callback(symbol, price)
        self._ws_task = asyncio.create_task(_run())

    def get_cached_price(self, symbol: str) -> Optional[float]:
        return self._price_cache.get(symbol)

    async def get_price(self, symbol: str) -> float:
        if symbol in self._price_cache:
            return self._price_cache[symbol]
        await self._rl.wait()
        t = await self._client.get_symbol_ticker(symbol=symbol)
        return float(t["price"])

    async def get_balance(self, asset="USDT") -> float:
        await self._rl.wait()
        acc = await self._client.get_account()
        for b in acc["balances"]:
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0

    async def get_all_balances(self) -> Dict[str, float]:
        await self._rl.wait()
        acc = await self._client.get_account()
        return {b["asset"]: float(b["free"]) for b in acc["balances"] if float(b["free"]) > 0}

    async def _round_qty(self, symbol: str, qty: float) -> str:
        info = await self._client.get_symbol_info(symbol)
        step = next(f["stepSize"] for f in info["filters"] if f["filterType"] == "LOT_SIZE")
        return str(Decimal(str(qty)).quantize(Decimal(step), rounding=ROUND_DOWN))

    async def _place_order(self, **kwargs) -> dict:
        for attempt in range(3):
            try:
                await self._rl.wait()
                if Config.DRY_RUN:
                    logger.info(f"[DRY RUN] Orden simulada: {kwargs}")
                    return {"orderId": f"DRY_{int(time.time()*1000)}", "executedQty": kwargs.get("quantity", "0"), **kwargs}
                return await self._client.create_order(**kwargs)
            except BinanceAPIException as e:
                if e.code in (-1003, -1015):
                    await asyncio.sleep(1.0 * (2 ** attempt))
                else:
                    raise
        raise RuntimeError("No se pudo ejecutar la orden.")

    async def buy_market(self, symbol: str, usdt_amount: float) -> dict:
        price = await self.get_price(symbol)
        qty   = await self._round_qty(symbol, usdt_amount / price)
        logger.info(f"BUY {qty} {symbol} @ ~{price:.2f}")
        order = await self._place_order(symbol=symbol, side="BUY", type="MARKET", quantity=qty)
        self._trailing_high[symbol] = price
        return order

    async def sell_market(self, symbol: str, qty: float) -> dict:
        qty_str = await self._round_qty(symbol, qty)
        price   = await self.get_price(symbol)
        logger.info(f"SELL {qty_str} {symbol} @ ~{price:.2f}")
        return await self._place_order(symbol=symbol, side="SELL", type="MARKET", quantity=qty_str)

    async def close_all_positions(self) -> list:
        logger.warning("PANICO - Cerrando todas las posiciones...")
        balances = await self.get_all_balances()
        results  = []
        for asset, amount in balances.items():
            if asset == "USDT":
                continue
            try:
                info = await self._client.get_symbol_info(f"{asset}USDT")
                if info:
                    results.append(await self.sell_market(f"{asset}USDT", amount))
            except Exception as e:
                logger.error(f"Error cerrando {asset}: {e}")
        return results

    def check_risk(self, symbol: str, entry_price: float, current_price: float) -> Optional[str]:
        change = (current_price - entry_price) / entry_price
        if change >= Config.TAKE_PROFIT_PCT:
            logger.info(f"Take Profit: {change*100:.2f}%"); return "TAKE_PROFIT"
        if change <= -Config.STOP_LOSS_PCT:
            logger.warning(f"Stop Loss: {change*100:.2f}%"); return "STOP_LOSS"
        prev_high = self._trailing_high.get(symbol, entry_price)
        if current_price > prev_high:
            self._trailing_high[symbol] = current_price
        elif prev_high and (prev_high - current_price) / prev_high >= Config.TRAILING_STOP_PCT:
            logger.warning("Trailing Stop activado"); return "TRAILING_STOP"
        return None
