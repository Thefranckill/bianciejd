"""
gemini_signal.py
----------------
Usa Google Gemini para generar senales de trading.
Soporta multiples API Keys con rotacion automatica.
Si una key alcanza el limite (429), pasa a la siguiente automaticamente.
"""

import json
import time
import aiohttp
from loguru import logger
from config import Config

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL    = "gemini-2.0-flash"

SYSTEM_PROMPT = """Eres un experto en trading de criptomonedas.
Analiza los datos de mercado y responde SOLO con un JSON valido sin texto extra ni markdown:
{"signal": "BUY" | "SELL" | "HOLD", "confidence": 0.0-1.0, "reason": "explicacion breve en espanol"}
- BUY: momentum positivo, soporte, cruce alcista
- SELL: resistencia, sobrecompra, cruce bajista
- HOLD: situacion ambigua o sin senal clara
"""


def _load_api_keys() -> list[str]:
    """
    Carga todas las API keys del .env.
    Soporta formato:
        GEMINI_API_KEY=key1
        GEMINI_API_KEY_2=key2
        GEMINI_API_KEY_3=key3
        ... hasta GEMINI_API_KEY_10
    """
    keys = []
    # Key principal
    if Config.GEMINI_API_KEY:
        keys.append(Config.GEMINI_API_KEY)
    # Keys adicionales (2 al 10)
    import os
    for i in range(2, 11):
        k = os.getenv(f"GEMINI_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    return keys


class KeyRotator:
    """Gestiona la rotacion de API keys con cooldown por limite."""

    def __init__(self, keys: list[str]):
        self._keys = keys
        # Tiempo en que cada key estara bloqueada hasta (timestamp)
        self._blocked_until: dict[str, float] = {}
        self._current_idx = 0

    def get_available_key(self) -> str | None:
        now = time.time()
        # Recorre todas las keys buscando una disponible
        for _ in range(len(self._keys)):
            key = self._keys[self._current_idx % len(self._keys)]
            if now >= self._blocked_until.get(key, 0):
                return key
            self._current_idx += 1

        # Todas bloqueadas — encuentra la que se desbloquea antes
        next_available = min(self._blocked_until.values())
        wait = max(0, next_available - now)
        logger.warning(f"Todas las keys en cooldown. La proxima disponible en {wait:.0f}s")
        return None

    def mark_rate_limited(self, key: str, cooldown: float = 65.0):
        """Bloquea una key por cooldown segundos."""
        self._blocked_until[key] = time.time() + cooldown
        self._current_idx += 1
        logger.warning(f"Key ...{key[-6:]} en cooldown por {cooldown:.0f}s")

    def mark_invalid(self, key: str):
        """Bloquea una key permanentemente (key invalida)."""
        self._blocked_until[key] = time.time() + 86400  # 24h
        self._current_idx += 1
        logger.error(f"Key ...{key[-6:]} marcada como invalida")

    @property
    def total(self) -> int:
        return len(self._keys)

    @property
    def available(self) -> int:
        now = time.time()
        return sum(1 for k in self._keys if now >= self._blocked_until.get(k, 0))


class GeminiSignal:

    def __init__(self):
        keys = _load_api_keys()
        if not keys:
            raise ValueError("No hay GEMINI_API_KEY configurada. Ejecuta: python setup_credentials.py")
        self._rotator = KeyRotator(keys)
        self._session = None
        logger.info(f"Gemini iniciado con {self._rotator.total} API key(s)")

    async def _get_session(self):
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_prompt(self, market_data: dict) -> str:
        prices = market_data.get("prices", [])
        last   = prices[-1] if prices else 0
        p1h    = prices[-60]   if len(prices) >= 60   else (prices[0] if prices else 0)
        p24h   = prices[-1440] if len(prices) >= 1440 else (prices[0] if prices else 0)
        ch1h   = ((last - p1h)  / p1h  * 100) if p1h  else 0
        ch24h  = ((last - p24h) / p24h * 100) if p24h else 0

        def ema(data, period):
            if len(data) < period:
                return data[-1] if data else 0
            k, e = 2 / (period + 1), data[-period]
            for p in data[-period + 1:]:
                e = p * k + e * (1 - k)
            return e

        ema9  = ema(prices, 9)
        ema26 = ema(prices, 26)
        trend = "ALCISTA (EMA9 > EMA26)" if ema9 > ema26 else "BAJISTA (EMA9 < EMA26)"

        return f"""Datos para {market_data.get('symbol', 'BTCUSDT')}:
- Precio actual: ${last:,.2f}
- Cambio 1h: {ch1h:+.2f}%
- Cambio 24h: {ch24h:+.2f}%
- EMA 9: ${ema9:,.2f} | EMA 26: ${ema26:,.2f}
- Tendencia: {trend}
Cual es tu senal?"""

    async def get_signal(self, market_data: dict) -> dict:
        key = self._rotator.get_available_key()
        if not key:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "Todas las keys en cooldown"}

        url = f"{BASE_URL}/{MODEL}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + self._build_prompt(market_data)}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200},
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data   = await resp.json()
                    raw    = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    raw    = raw.replace("```json", "").replace("```", "").strip()
                    result = json.loads(raw)
                    logger.info(
                        f"Gemini [{self._rotator.available}/{self._rotator.total} keys] "
                        f"-> {result['signal']} ({result.get('confidence',0):.0%}) | {result.get('reason','')}"
                    )
                    return result

                elif resp.status == 429:
                    self._rotator.mark_rate_limited(key, cooldown=65.0)
                    # Reintenta con la siguiente key disponible
                    return await self.get_signal(market_data)

                elif resp.status in (401, 403):
                    self._rotator.mark_invalid(key)
                    return await self.get_signal(market_data)

                else:
                    text = await resp.text()
                    logger.warning(f"Gemini HTTP {resp.status}: {text[:150]}")
                    return {"signal": "HOLD", "confidence": 0.0, "reason": f"Error HTTP {resp.status}"}

        except Exception as e:
            logger.error(f"Error Gemini: {e}")
            return {"signal": "HOLD", "confidence": 0.0, "reason": str(e)}
