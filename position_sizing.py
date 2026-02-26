"""
position_sizing.py
------------------
Gestión dinámica de capital.
- Kelly Criterion simplificado
- Nunca arriesga más del max_risk_pct del capital total
- Reduce tamaño tras rachas perdedoras (anti-martingala)
"""
from loguru import logger
from config import Config


class PositionSizer:

    def __init__(self, max_risk_pct: float = 0.05, max_position_pct: float = 0.20):
        """
        max_risk_pct:     máximo % del capital a ARRIESGAR por trade (no a invertir)
        max_position_pct: máximo % del capital a INVERTIR por trade
        """
        self.max_risk_pct     = max_risk_pct
        self.max_position_pct = max_position_pct
        self._consecutive_losses = 0
        self._win_rate = 0.5       # estimado inicial
        self._avg_win  = 0.03      # 3% promedio de ganancia
        self._avg_loss = 0.015     # 1.5% promedio de pérdida
        self._trades_history: list[float] = []

    def update(self, pnl: float):
        """Llama esto después de cada operación cerrada."""
        self._trades_history.append(pnl)
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # Recalcula win rate con las últimas 20 operaciones
        recent = self._trades_history[-20:]
        if len(recent) >= 5:
            self._win_rate = len([p for p in recent if p > 0]) / len(recent)
            wins   = [p for p in recent if p > 0]
            losses = [abs(p) for p in recent if p < 0]
            if wins:   self._avg_win  = sum(wins)   / len(wins)
            if losses: self._avg_loss = sum(losses)  / len(losses)

    def calculate(self, total_capital: float, price: float) -> float:
        """
        Retorna el monto en USDT a invertir en la próxima operación.
        """
        if total_capital <= 0:
            return 0.0

        # Kelly Criterion: f = (p*b - q) / b
        # p = win_rate, q = 1-p, b = avg_win/avg_loss
        b = self._avg_win / self._avg_loss if self._avg_loss > 0 else 2.0
        q = 1 - self._win_rate
        kelly = (self._win_rate * b - q) / b
        kelly = max(0.0, min(kelly, 0.25))  # clamp entre 0% y 25%

        # Fracción de Kelly conservadora (25% del Kelly completo)
        fraction = kelly * 0.25

        # Reducir tamaño tras rachas perdedoras
        if self._consecutive_losses >= 3:
            fraction *= 0.5
            logger.warning(f"Racha de {self._consecutive_losses} pérdidas → tamaño reducido 50%")
        elif self._consecutive_losses >= 2:
            fraction *= 0.75

        # Calcular monto basado en riesgo máximo
        risk_amount   = total_capital * self.max_risk_pct
        stop_loss_pct = Config.STOP_LOSS_PCT
        # Si riesgo real es stop_loss_pct del monto invertido:
        # risk_amount = position_size * stop_loss_pct
        position_by_risk = risk_amount / stop_loss_pct if stop_loss_pct > 0 else total_capital * 0.1

        # También limitar por Kelly y por máximo permitido
        position_by_kelly = total_capital * max(fraction, 0.02)
        position_max      = total_capital * self.max_position_pct

        position = min(position_by_risk, position_by_kelly, position_max)
        position = max(position, 10.0)  # mínimo $10

        logger.info(
            f"Position sizing: ${position:.2f} USDT "
            f"(Kelly:{fraction:.1%} | WinRate:{self._win_rate:.0%} | "
            f"Pérdidas consecutivas:{self._consecutive_losses})"
        )
        return round(position, 2)
