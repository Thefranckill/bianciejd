"""
backtesting.py
--------------
Prueba la estrategia con datos históricos de Binance.
Uso:  python backtesting.py

Descarga velas de los últimos N días y simula todas las
señales de compra/venta con Stop Loss, Take Profit y Trailing Stop.
Genera un reporte completo con métricas profesionales.
"""

import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
from binance import AsyncClient
from config import Config


# ── Parámetros del backtest ────────────────────────────────────────────
SYMBOL     = Config.TRADING_PAIR
DAYS_BACK  = 30          # cuántos días hacia atrás probar
INTERVAL   = "1h"        # velas de 1 hora
CAPITAL    = 1000.0      # capital inicial simulado en USDT
TRADE_PCT  = 0.05        # % del capital por operación


class Backtester:

    def __init__(self):
        self.sl  = Config.STOP_LOSS_PCT
        self.tp  = Config.TAKE_PROFIT_PCT
        self.tsl = Config.TRAILING_STOP_PCT

    # ── Descarga de datos ───────────────────────────────────────────────
    async def fetch_candles(self) -> pd.DataFrame:
        logger.info(f"Descargando {DAYS_BACK} días de velas {INTERVAL} para {SYMBOL}...")
        client = await AsyncClient.create(Config.BINANCE_API_KEY, Config.BINANCE_SECRET_KEY)
        try:
            start = str(int((datetime.now() - timedelta(days=DAYS_BACK)).timestamp() * 1000))
            klines = await client.get_historical_klines(SYMBOL, INTERVAL, start)
        finally:
            await client.close_connection()

        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","volume",
            "close_time","quote_vol","trades","taker_buy_base","taker_buy_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = pd.to_numeric(df[col])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = df.set_index("time")
        logger.info(f"✅ {len(df)} velas descargadas ({df.index[0].date()} → {df.index[-1].date()})")
        return df

    # ── Indicadores ─────────────────────────────────────────────────────
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        # EMAs
        df["ema9"]  = df["close"].ewm(span=9,  adjust=False).mean()
        df["ema26"] = df["close"].ewm(span=26, adjust=False).mean()
        df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        df["macd"]        = df["close"].ewm(span=12).mean() - df["close"].ewm(span=26).mean()
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_hist"]   = df["macd"] - df["macd_signal"]

        # Señal de entrada: EMA9 cruza EMA26 hacia arriba + RSI no sobrecomprado
        df["ema_cross_up"]   = (df["ema9"] > df["ema26"]) & (df["ema9"].shift(1) <= df["ema26"].shift(1))
        df["ema_cross_down"] = (df["ema9"] < df["ema26"]) & (df["ema9"].shift(1) >= df["ema26"].shift(1))
        df["signal_buy"]     = df["ema_cross_up"]  & (df["rsi"] < 70)
        df["signal_sell"]    = df["ema_cross_down"] & (df["rsi"] > 30)
        return df

    # ── Simulación ──────────────────────────────────────────────────────
    def run_simulation(self, df: pd.DataFrame) -> dict:
        capital    = CAPITAL
        position   = 0.0   # BTC en cartera
        entry_price = 0.0
        trailing_high = 0.0
        trades     = []
        equity_curve = [capital]
        in_position  = False

        for i in range(1, len(df)):
            row   = df.iloc[i]
            price = row["close"]

            if in_position:
                change = (price - entry_price) / entry_price

                # Take Profit
                if change >= self.tp:
                    pnl = position * price - position * entry_price
                    capital += position * price
                    trades.append({"type":"TAKE_PROFIT","entry":entry_price,"exit":price,
                                   "pnl":pnl,"bars":i,"date":df.index[i]})
                    in_position = False; position = 0.0
                    continue

                # Stop Loss
                if change <= -self.sl:
                    pnl = position * price - position * entry_price
                    capital += position * price
                    trades.append({"type":"STOP_LOSS","entry":entry_price,"exit":price,
                                   "pnl":pnl,"bars":i,"date":df.index[i]})
                    in_position = False; position = 0.0
                    continue

                # Trailing Stop
                if price > trailing_high:
                    trailing_high = price
                trail_drop = (trailing_high - price) / trailing_high
                if trail_drop >= self.tsl:
                    pnl = position * price - position * entry_price
                    capital += position * price
                    trades.append({"type":"TRAILING_STOP","entry":entry_price,"exit":price,
                                   "pnl":pnl,"bars":i,"date":df.index[i]})
                    in_position = False; position = 0.0
                    continue

                # Señal de venta
                if row["signal_sell"]:
                    pnl = position * price - position * entry_price
                    capital += position * price
                    trades.append({"type":"SIGNAL_SELL","entry":entry_price,"exit":price,
                                   "pnl":pnl,"bars":i,"date":df.index[i]})
                    in_position = False; position = 0.0

            else:
                # Señal de compra
                if row["signal_buy"] and capital > 10:
                    invest      = capital * TRADE_PCT
                    position    = invest / price
                    capital    -= invest
                    entry_price  = price
                    trailing_high = price
                    in_position  = True

            equity_curve.append(capital + position * price)

        # Cerrar posición abierta al final
        if in_position:
            price = df.iloc[-1]["close"]
            pnl   = position * price - position * entry_price
            capital += position * price
            trades.append({"type":"FORCED_CLOSE","entry":entry_price,"exit":price,
                           "pnl":pnl,"bars":len(df),"date":df.index[-1]})

        return {"trades": trades, "equity": equity_curve, "final_capital": capital}

    # ── Métricas ────────────────────────────────────────────────────────
    def compute_metrics(self, result: dict, df: pd.DataFrame) -> dict:
        trades = result["trades"]
        equity = result["equity"]

        if not trades:
            return {"error": "Sin operaciones en el período"}

        pnls     = [t["pnl"] for t in trades]
        wins     = [p for p in pnls if p > 0]
        losses   = [p for p in pnls if p < 0]

        total_return = (result["final_capital"] - CAPITAL) / CAPITAL * 100
        win_rate     = len(wins) / len(pnls) * 100
        avg_win      = np.mean(wins)   if wins   else 0
        avg_loss     = np.mean(losses) if losses else 0
        profit_factor = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")

        # Drawdown máximo
        eq = np.array(equity)
        peak = np.maximum.accumulate(eq)
        dd   = (eq - peak) / peak * 100
        max_drawdown = dd.min()

        # Sharpe Ratio (simplificado, sin tasa libre de riesgo)
        returns = np.diff(eq) / eq[:-1]
        sharpe  = (np.mean(returns) / np.std(returns) * np.sqrt(24*365)) if np.std(returns) > 0 else 0

        # Buy & Hold comparación
        bh_return = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0] * 100

        by_type = {}
        for t in trades:
            tp = t["type"]
            by_type[tp] = by_type.get(tp, 0) + 1

        return {
            "total_trades":   len(trades),
            "win_rate":       win_rate,
            "total_return":   total_return,
            "final_capital":  result["final_capital"],
            "avg_win":        avg_win,
            "avg_loss":       avg_loss,
            "profit_factor":  profit_factor,
            "max_drawdown":   max_drawdown,
            "sharpe_ratio":   sharpe,
            "buy_hold_return": bh_return,
            "alpha":          total_return - bh_return,
            "by_type":        by_type,
            "trades_detail":  trades,
            "equity_curve":   equity,
        }

    # ── Reporte en consola ──────────────────────────────────────────────
    def print_report(self, metrics: dict):
        if "error" in metrics:
            print(f"\n❌ {metrics['error']}")
            return

        sep = "═" * 50
        print(f"\n{sep}")
        print(f"  REPORTE DE BACKTESTING — {SYMBOL}")
        print(f"  Período: {DAYS_BACK} días | Capital: ${CAPITAL:,.0f}")
        print(sep)
        print(f"  Total operaciones:   {metrics['total_trades']}")
        print(f"  Win Rate:            {metrics['win_rate']:.1f}%")
        print(f"  Retorno total:       {metrics['total_return']:+.2f}%")
        print(f"  Capital final:       ${metrics['final_capital']:,.2f}")
        print(f"  Ganancia promedio:   ${metrics['avg_win']:+.4f}")
        print(f"  Pérdida promedio:    ${metrics['avg_loss']:+.4f}")
        print(f"  Profit Factor:       {metrics['profit_factor']:.2f}")
        print(f"  Drawdown máximo:     {metrics['max_drawdown']:.2f}%")
        print(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
        print(f"─── Comparación ─────────────────────────────────")
        print(f"  Estrategia:          {metrics['total_return']:+.2f}%")
        print(f"  Buy & Hold:          {metrics['buy_hold_return']:+.2f}%")
        alpha_sym = "✅" if metrics['alpha'] > 0 else "❌"
        print(f"  Alpha (ventaja):     {metrics['alpha']:+.2f}% {alpha_sym}")
        print(f"─── Salidas por tipo ─────────────────────────────")
        for tp, count in metrics["by_type"].items():
            print(f"  {tp:<20} {count}")
        print(sep)

        if metrics['total_return'] > metrics['buy_hold_return']:
            print("  ✅ La estrategia SUPERA al Buy & Hold")
        else:
            print("  ⚠️  La estrategia NO supera al Buy & Hold")
            print("     Considera ajustar los parámetros antes de operar en vivo.")
        print(sep + "\n")

    # ── Guardar resultados ──────────────────────────────────────────────
    def save_results(self, metrics: dict):
        import json
        from pathlib import Path
        out = Path("logs/backtest_results.json")
        out.parent.mkdir(exist_ok=True)
        # Convertir numpy types para JSON
        def convert(o):
            if isinstance(o, (np.integer,)): return int(o)
            if isinstance(o, (np.floating,)): return float(o)
            if isinstance(o, np.ndarray): return o.tolist()
            if isinstance(o, pd.Timestamp): return str(o)
            return str(o)
        safe = json.loads(json.dumps({k: v for k, v in metrics.items() if k != "trades_detail"}, default=convert))
        out.write_text(json.dumps(safe, indent=2))
        logger.info(f"Resultados guardados en {out}")

    async def run(self):
        df = await self.fetch_candles()
        df = self.add_indicators(df)
        result  = self.run_simulation(df)
        metrics = self.compute_metrics(result, df)
        self.print_report(metrics)
        self.save_results(metrics)
        return metrics


if __name__ == "__main__":
    asyncio.run(Backtester().run())
