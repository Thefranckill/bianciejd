# 🤖 Bitcoing Trading Bot — Migración a Binance

Bot de trading de criptomonedas asíncrono con WebSockets, dashboard Streamlit y gestión de riesgos completa.

---

## 🚀 Instalación rápida

```bash
# 1. Clona el repositorio
git clone https://github.com/Thefranckill/bitcoing.git
cd bitcoing

# 2. Crea un entorno virtual
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Instala dependencias
pip install -r requirements.txt

# 4. Configura tus credenciales (asistente interactivo)
python setup_credentials.py
```

---

## ⚙️ Configuración

### Opción A — Asistente CLI (recomendado)
```bash
python setup_credentials.py
```
Te pedirá paso a paso: claves de Binance, Google y parámetros del bot.

### Opción B — Manual
Copia `.env.example` a `.env` y rellena los valores:
```bash
cp .env.example .env
```

| Variable | Descripción |
|---|---|
| `BINANCE_API_KEY` | API Key de Binance |
| `BINANCE_SECRET_KEY` | Secret Key de Binance |
| `GOOGLE_API_CREDENTIALS` | Path al JSON de cuenta de servicio Google |
| `GOOGLE_SHEET_ID` | ID de la hoja de cálculo para logs |
| `TRADING_PAIR` | Par a tradear (ej. `BTCUSDT`) |
| `TRADE_AMOUNT_USDT` | Capital por operación en USDT |
| `STOP_LOSS_PCT` | % Stop Loss (ej. `0.015` = 1.5%) |
| `TAKE_PROFIT_PCT` | % Take Profit (ej. `0.030` = 3%) |
| `TRAILING_STOP_PCT` | % Trailing Stop (ej. `0.010` = 1%) |
| `DRY_RUN` | `true` = simulación sin dinero real |

---

## ▶️ Uso

### Iniciar el bot
```bash
python main.py
```

### Abrir el dashboard
```bash
streamlit run dashboard/app.py
```
Accede en tu navegador: `http://localhost:8501`

### Modo PÁNICO (cerrar todo desde CLI)
```bash
python main.py --panic
```

---

## 🏗️ Arquitectura

```
bitcoing/
├── main.py                  # Punto de entrada
├── setup_credentials.py     # Configurador interactivo
├── .env.example             # Plantilla de variables de entorno
├── .gitignore               # Excluye .env y credenciales
├── requirements.txt
│
├── core/
│   ├── config.py            # Carga variables de entorno
│   ├── exchange.py          # Cliente Binance (REST + WebSocket)
│   └── bot.py               # Lógica de trading asíncrona
│
├── dashboard/
│   └── app.py               # Dashboard Streamlit
│
├── utils/
│   └── logger.py            # Logger CSV + Google Sheets
│
└── logs/                    # Logs y CSV de trades (ignorados por git)
```

---

## 📡 Características técnicas

### 🔄 WebSockets en lugar de REST polling
El bot suscribe al stream de precio por WebSocket de Binance. Esto elimina la latencia del polling REST y permite reaccionar en milisegundos a cambios de precio.

### ⚡ Asincronía completa con `asyncio`
El loop de decisión, el stream WebSocket y las llamadas a la API corren en paralelo sin bloquearse entre sí.

### 🛡️ Gestión de riesgos
En cada tick de precio se evalúan tres condiciones:
- **Stop Loss**: sale si el precio cae más del % configurado
- **Take Profit**: sale si el precio sube más del % configurado  
- **Trailing Stop**: actualiza el máximo dinámicamente y sale si cae más del % desde ese máximo

### 🚦 Rate Limiting
Ventana deslizante de 1200 req/min con backoff exponencial en caso de recibir error `429` de Binance.

### 🔐 Seguridad
- Las credenciales viven **solo** en `.env` (excluido del repo por `.gitignore`)
- Nunca se logean las claves en consola ni archivos

---

## 📊 Dashboard

El dashboard muestra en tiempo real:

| Sección | Descripción |
|---|---|
| Métricas | Precio actual, balance USDT/BTC, modo del bot |
| Gráfico PnL | Curva de rendimiento acumulada con Plotly |
| Balances | Todos los activos con saldo > 0 |
| Historial | Últimas 50 operaciones con color BUY/SELL |
| Botón PÁNICO | Cierra todas las posiciones spot inmediatamente |

---

## 🔧 Personalizar la estrategia

El método `_signal()` en `core/bot.py` determina las señales de compra/venta. Por defecto usa cruce de EMA 9/26. Para cambiarla:

```python
def _signal(self) -> Optional[str]:
    # Tu lógica aquí
    # Retorna "BUY", "SELL" o None
    ...
```

---

## ⚠️ Aviso legal

Este software es solo para fines educativos. El trading de criptomonedas conlleva un riesgo significativo de pérdida. Prueba siempre con `DRY_RUN=true` antes de usar dinero real.
