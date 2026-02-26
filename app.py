"""
app.py - Dashboard Crypto Admin Style
Ejecutar: python -m streamlit run app.py
"""

import sys, asyncio, time, json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).parent))
from exchange import BinanceExchange
from config   import Config
from logger   import TradeLogger

st.set_page_config(
    page_title="Crypto Admin — Trading Bot",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [data-testid="stAppViewContainer"] {
    background: #0B0E1A !important;
    font-family: 'Syne', sans-serif;
    color: #E4E8F7;
}

[data-testid="stSidebar"] {
    background: #0D1120 !important;
    border-right: 1px solid rgba(255,255,255,0.06);
    padding-top: 0 !important;
}
[data-testid="stSidebar"] > div { padding: 0 !important; }

/* Hide streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
.block-container { padding: 1.5rem 2rem !important; max-width: 100% !important; }

/* ── CARDS ── */
.card {
    background: linear-gradient(145deg, #131729, #0f1322);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    position: relative;
    overflow: hidden;
    transition: border-color .25s;
}
.card:hover { border-color: rgba(99,179,237,0.25); }
.card::before {
    content:'';
    position:absolute; top:0; left:0; right:0; height:2px;
    background: linear-gradient(90deg, transparent, rgba(99,179,237,0.4), transparent);
}

/* ── METRIC CARDS ── */
.metric-card {
    background: linear-gradient(145deg, #131729, #0f1322);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
}
.metric-icon {
    width: 42px; height: 42px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem; margin-bottom: .8rem;
}
.metric-label { font-size: .72rem; color: #8892b0; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .3rem; }
.metric-value { font-size: 1.5rem; font-weight: 800; color: #E4E8F7; font-family: 'DM Mono', monospace; }
.metric-change { font-size: .78rem; margin-top: .3rem; font-family: 'DM Mono', monospace; }
.up   { color: #48bb78; }
.down { color: #fc8181; }
.neu  { color: #8892b0; }

/* ── SIDEBAR NAV ── */
.nav-logo {
    padding: 1.4rem 1.4rem 1rem;
    font-size: 1.1rem; font-weight: 800;
    display: flex; align-items: center; gap: .6rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: .5rem;
}
.nav-logo span.dot { color: #F6AD55; }
.nav-section { padding: .4rem 1.4rem .2rem; font-size: .65rem; color: #4a5578; text-transform: uppercase; letter-spacing: .1em; }
.nav-item {
    display: flex; align-items: center; gap: .7rem;
    padding: .55rem 1.4rem; font-size: .85rem; color: #8892b0;
    cursor: pointer; transition: all .2s; border-left: 2px solid transparent;
    text-decoration: none;
}
.nav-item:hover, .nav-item.active {
    color: #E4E8F7; background: rgba(99,179,237,0.07);
    border-left-color: #63B3ED;
}
.nav-badge {
    margin-left: auto; background: #F6AD55; color: #0B0E1A;
    font-size: .6rem; font-weight: 700; padding: .15rem .45rem;
    border-radius: 20px;
}

/* ── TABLE ── */
.tx-table { width: 100%; border-collapse: collapse; font-family: 'DM Mono', monospace; font-size: .82rem; }
.tx-table thead th {
    color: #8892b0; font-size: .68rem; text-transform: uppercase;
    letter-spacing: .08em; padding: .6rem .8rem; text-align: left;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    font-family: 'Syne', sans-serif;
}
.tx-table tbody td { padding: .75rem .8rem; border-bottom: 1px solid rgba(255,255,255,0.04); }
.tx-table tbody tr:hover td { background: rgba(99,179,237,0.04); }
.badge {
    display: inline-block; padding: .2rem .65rem; border-radius: 20px;
    font-size: .7rem; font-weight: 600; font-family: 'Syne', sans-serif;
}
.badge-buy  { background: rgba(72,187,120,0.15); color: #48bb78; border: 1px solid rgba(72,187,120,0.3); }
.badge-sell { background: rgba(252,129,129,0.15); color: #fc8181; border: 1px solid rgba(252,129,129,0.3); }
.badge-hold { background: rgba(246,173,85,0.15);  color: #F6AD55; border: 1px solid rgba(246,173,85,0.3); }

/* ── PANIC BUTTON ── */
.panic-wrap { padding: 1rem 1.4rem; }
.panic-btn {
    width: 100%; padding: .75rem; border-radius: 12px;
    background: linear-gradient(135deg, #c53030, #e53e3e);
    color: white; font-family: 'Syne', sans-serif;
    font-weight: 700; font-size: .85rem; border: none;
    cursor: pointer; letter-spacing: .05em;
    box-shadow: 0 4px 20px rgba(229,62,62,0.3);
    transition: all .2s;
}
.panic-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 25px rgba(229,62,62,0.45); }

/* ── PRICE TICKER ── */
.ticker-row {
    display: flex; align-items: center; gap: .8rem;
    padding: .7rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.ticker-icon { width: 32px; height: 32px; border-radius: 50%; display:flex; align-items:center; justify-content:center; font-size: 1rem; }
.ticker-name { font-weight: 700; font-size: .88rem; }
.ticker-sub  { font-size: .7rem; color: #8892b0; }
.ticker-price { margin-left: auto; font-family: 'DM Mono', monospace; font-weight: 500; font-size: .9rem; }
.ticker-24h  { font-size: .72rem; font-family: 'DM Mono', monospace; }

/* ── STATUS DOT ── */
.status-dot {
    display: inline-block; width: 8px; height: 8px;
    border-radius: 50%; background: #48bb78;
    box-shadow: 0 0 8px #48bb78;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: .4; }
}

/* ── TOP BAR ── */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 1.5rem; padding-bottom: 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.topbar-title { font-size: 1.3rem; font-weight: 800; }
.topbar-sub   { font-size: .78rem; color: #8892b0; margin-top: .15rem; }
.topbar-right { display: flex; align-items: center; gap: 1rem; }
.mode-pill {
    padding: .3rem .9rem; border-radius: 20px; font-size: .75rem; font-weight: 700;
    font-family: 'Syne', sans-serif;
}
.mode-dry  { background: rgba(246,173,85,0.15); color: #F6AD55; border: 1px solid rgba(246,173,85,0.4); }
.mode-live { background: rgba(252,129,129,0.15); color: #fc8181; border: 1px solid rgba(252,129,129,0.4); }

/* Streamlit overrides */
[data-testid="metric-container"] { display: none; }
div[data-testid="stHorizontalBlock"] { gap: 1rem; }
.stButton > button {
    background: linear-gradient(135deg, #c53030, #e53e3e) !important;
    color: white !important; border: none !important;
    border-radius: 12px !important; font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important; width: 100% !important;
    box-shadow: 0 4px 20px rgba(229,62,62,0.3) !important;
}
</style>
""", unsafe_allow_html=True)


# ── HELPERS ──────────────────────────────────────────────────────────
def run_async(coro):
    try:
        return asyncio.run(coro)
    except Exception:
        return None

@st.cache_data(ttl=6)
def fetch_balances():
    async def _():
        async with BinanceExchange() as ex:
            return await ex.get_all_balances()
    return run_async(_()) or {}

@st.cache_data(ttl=6)
def fetch_price(sym):
    async def _():
        async with BinanceExchange() as ex:
            return await ex.get_price(sym)
    return run_async(_()) or 0.0

@st.cache_data(ttl=30)
def fetch_klines(sym, interval="1m", limit=120):
    async def _():
        async with BinanceExchange() as ex:
            return await ex._client.get_klines(symbol=sym, interval=interval, limit=limit)
    return run_async(_()) or []

def do_panic():
    async def _():
        async with BinanceExchange() as ex:
            return await ex.close_all_positions()
    return run_async(_()) or []


# ── DATA ─────────────────────────────────────────────────────────────
price    = fetch_price(Config.TRADING_PAIR)
balances = fetch_balances()
trades   = TradeLogger.load_trades()
klines   = fetch_klines(Config.TRADING_PAIR)

usdt_bal = balances.get("USDT", 0.0)
btc_bal  = balances.get("BTC", 0.0)

total_pnl   = sum(float(t.get("pnl") or 0) for t in trades)
total_trades = len([t for t in trades if t.get("action") == "BUY"])

# Price change from klines
if len(klines) >= 2:
    open_price  = float(klines[0][1])
    price_chg   = ((price - open_price) / open_price * 100) if open_price else 0
else:
    price_chg = 0.0


# ── SIDEBAR ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="nav-logo">
        <span style="font-size:1.4rem">₿</span>
        Crypto <span class="dot">Admin</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="nav-section">Main</div>', unsafe_allow_html=True)
    st.markdown("""
    <a class="nav-item active" href="#">
        <span>▦</span> Dashboard <span class="nav-badge">Live</span>
    </a>
    <a class="nav-item" href="#">
        <span>◈</span> Reports
    </a>
    <a class="nav-item" href="#">
        <span>⬡</span> Transactions
    </a>
    """, unsafe_allow_html=True)

    st.markdown('<div class="nav-section">Trading</div>', unsafe_allow_html=True)
    st.markdown("""
    <a class="nav-item" href="#">
        <span>◎</span> Charts
    </a>
    <a class="nav-item" href="#">
        <span>⊞</span> Tickers
    </a>
    <a class="nav-item" href="#">
        <span>⟳</span> History
    </a>
    """, unsafe_allow_html=True)

    st.markdown('<div class="nav-section" style="margin-top:1rem">Settings</div>', unsafe_allow_html=True)

    auto_refresh = st.checkbox("Auto-refresh (10s)", value=True)
    refresh_rate = 10

    st.markdown("---")
    st.markdown('<div style="padding:.4rem 1.4rem .8rem; font-size:.75rem; color:#8892b0;">Bot Config</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding:0 1.4rem; font-size:.78rem; color:#8892b0; font-family:'DM Mono',monospace; line-height:2;">
        Par: <span style="color:#E4E8F7">{Config.TRADING_PAIR}</span><br>
        SL: <span style="color:#fc8181">{Config.STOP_LOSS_PCT*100:.1f}%</span> &nbsp;
        TP: <span style="color:#48bb78">{Config.TAKE_PROFIT_PCT*100:.1f}%</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="panic-wrap">', unsafe_allow_html=True)
    if st.button("⛔  PÁNICO — Cerrar Todo"):
        with st.spinner("Cerrando..."):
            r = do_panic()
        st.success(f"{len(r)} posiciones cerradas")
    st.markdown("</div>", unsafe_allow_html=True)


# ── TOPBAR ────────────────────────────────────────────────────────────
mode_class = "mode-dry" if Config.DRY_RUN else "mode-live"
mode_label = "🟡 DRY RUN" if Config.DRY_RUN else "🔴 LIVE"
st.markdown(f"""
<div class="topbar">
  <div>
    <div class="topbar-title">Dashboard &nbsp;<span class="status-dot"></span></div>
    <div class="topbar-sub">Actualizado: {time.strftime('%H:%M:%S')} · Binance Spot</div>
  </div>
  <div class="topbar-right">
    <span class="mode-pill {mode_class}">{mode_label}</span>
    <span style="font-size:.8rem;color:#8892b0;font-family:'DM Mono',monospace">{Config.TRADING_PAIR}</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── METRIC CARDS ──────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

def metric_card(col, icon, icon_bg, label, value, change=None, change_class="neu"):
    col.markdown(f"""
    <div class="metric-card">
      <div class="metric-icon" style="background:{icon_bg}">{icon}</div>
      <div class="metric-label">{label}</div>
      <div class="metric-value">{value}</div>
      {f'<div class="metric-change {change_class}">{change}</div>' if change else ''}
    </div>
    """, unsafe_allow_html=True)

chg_cls = "up" if price_chg >= 0 else "down"
chg_sym = "▲" if price_chg >= 0 else "▼"
metric_card(c1, "₿", "rgba(246,173,85,0.15)", "BTC Price",
            f"${price:,.2f}", f"{chg_sym} {abs(price_chg):.2f}% (2h)", chg_cls)

metric_card(c2, "$", "rgba(99,179,237,0.15)", "Balance USDT",
            f"${usdt_bal:,.2f}", f"{btc_bal:.5f} BTC en cartera", "neu")

pnl_cls = "up" if total_pnl >= 0 else "down"
pnl_sym = "▲" if total_pnl >= 0 else "▼"
metric_card(c3, "◈", "rgba(72,187,120,0.15)", "PnL Total",
            f"${total_pnl:+.2f}", f"{pnl_sym} {total_trades} operaciones", pnl_cls)

metric_card(c4, "🤖", "rgba(159,122,234,0.15)", "Motor IA",
            "Gemini 2.0", "Analizando mercado...", "neu")

st.markdown("<br>", unsafe_allow_html=True)


# ── CHART + TICKERS ───────────────────────────────────────────────────
col_chart, col_ticker = st.columns([3, 1])

with col_chart:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
      <div>
        <div style="font-size:.7rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em">Precio en Tiempo Real</div>
        <div style="font-size:1.6rem;font-weight:800;font-family:'DM Mono',monospace">${price:,.2f}
          <span style="font-size:.9rem;{'color:#48bb78' if price_chg>=0 else 'color:#fc8181'}">
            {'▲' if price_chg>=0 else '▼'} {abs(price_chg):.2f}%
          </span>
        </div>
      </div>
      <div style="font-size:.75rem;color:#8892b0">{Config.TRADING_PAIR} · Binance</div>
    </div>
    """, unsafe_allow_html=True)

    if klines:
        df_k = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qav","nt","tbbav","tbqav","i"])
        for col in ["o","h","l","c","v"]:
            df_k[col] = pd.to_numeric(df_k[col])
        df_k["t"] = pd.to_datetime(df_k["t"], unit="ms")

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_k["t"], open=df_k["o"], high=df_k["h"],
            low=df_k["l"], close=df_k["c"],
            increasing_line_color="#48bb78", decreasing_line_color="#fc8181",
            increasing_fillcolor="rgba(72,187,120,0.7)",
            decreasing_fillcolor="rgba(252,129,129,0.7)",
            name="OHLC",
        ))
        # Volume bars
        fig.add_trace(go.Bar(
            x=df_k["t"], y=df_k["v"],
            yaxis="y2",
            marker_color=["rgba(72,187,120,0.2)" if c >= o else "rgba(252,129,129,0.2)"
                         for c, o in zip(df_k["c"], df_k["o"])],
            name="Volumen",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8892b0", family="DM Mono"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", showgrid=True, rangeslider_visible=False),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", showgrid=True, side="right"),
            yaxis2=dict(overlaying="y", side="left", showgrid=False, showticklabels=False, range=[0, df_k["v"].max()*5]),
            margin=dict(l=0, r=50, t=10, b=10),
            height=320,
            showlegend=False,
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Cargando datos de mercado...")
    st.markdown("</div>", unsafe_allow_html=True)

with col_ticker:
    st.markdown('<div class="card" style="height:100%">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.7rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.8rem">Quick Tickers</div>', unsafe_allow_html=True)

    tickers = [
        ("₿", "#F7931A", "BTC", "Bitcoin",   "BTCUSDT"),
        ("Ξ", "#627EEA", "ETH", "Ethereum",  "ETHUSDT"),
        ("◎", "#9945FF", "SOL", "Solana",     "SOLUSDT"),
        ("✦", "#E84142", "AVAX","Avalanche",  "AVAXUSDT"),
    ]

    for icon, color, sym, name, pair in tickers:
        p = fetch_price(pair)
        st.markdown(f"""
        <div class="ticker-row">
          <div class="ticker-icon" style="background:rgba(255,255,255,0.06)">{icon}</div>
          <div>
            <div class="ticker-name">{sym}</div>
            <div class="ticker-sub">{name}</div>
          </div>
          <div style="text-align:right">
            <div class="ticker-price">${p:,.2f}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ── PNL CHART + TRADE TABLE ───────────────────────────────────────────
col_pnl, col_trades = st.columns([1, 2])

with col_pnl:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.7rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.8rem">Rendimiento PnL</div>', unsafe_allow_html=True)

    if trades:
        df_p = pd.DataFrame(trades)
        df_p["pnl"]       = pd.to_numeric(df_p["pnl"], errors="coerce").fillna(0)
        df_p["timestamp"] = pd.to_datetime(df_p["timestamp"])
        df_p = df_p.sort_values("timestamp")
        df_p["cum"] = df_p["pnl"].cumsum()

        fig2 = go.Figure()
        pos = df_p["cum"] >= 0
        fig2.add_trace(go.Scatter(
            x=df_p["timestamp"], y=df_p["cum"],
            fill="tozeroy",
            line=dict(color="#48bb78" if total_pnl >= 0 else "#fc8181", width=2),
            fillcolor="rgba(72,187,120,0.08)" if total_pnl >= 0 else "rgba(252,129,129,0.08)",
            mode="lines",
        ))
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8892b0", family="DM Mono"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", showgrid=False),
            yaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickprefix="$", side="right"),
            margin=dict(l=0, r=45, t=5, b=5),
            height=260, showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.markdown('<div style="height:200px;display:flex;align-items:center;justify-content:center;color:#4a5578;font-size:.85rem">Sin operaciones aún</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col_trades:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.8rem">
      <div style="font-size:.7rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em">Actividad Reciente</div>
      <div style="font-size:.7rem;color:#63B3ED">Ver todo →</div>
    </div>
    """, unsafe_allow_html=True)

    if trades:
        recent = sorted(trades, key=lambda x: x.get("timestamp",""), reverse=True)[:8]
        rows = ""
        for t in recent:
            action = t.get("action","")
            badge_cls = "badge-buy" if action=="BUY" else "badge-sell"
            pnl_val = float(t.get("pnl") or 0)
            pnl_str = f'<span class="{"up" if pnl_val>=0 else "down"}">${pnl_val:+.2f}</span>' if pnl_val else "—"
            rows += f"""
            <tr>
              <td><span class="badge {badge_cls}">{action}</span></td>
              <td>{t.get('symbol','')}</td>
              <td>${float(t.get('price') or 0):,.2f}</td>
              <td>{float(t.get('qty') or 0):.5f}</td>
              <td>{pnl_str}</td>
              <td style="color:#8892b0;font-size:.75rem">{str(t.get('timestamp',''))[:16]}</td>
              <td style="color:#8892b0;font-size:.72rem">{t.get('reason','—')}</td>
            </tr>"""
        st.markdown(f"""
        <table class="tx-table">
          <thead><tr>
            <th>Acción</th><th>Par</th><th>Precio</th>
            <th>Cantidad</th><th>PnL</th><th>Fecha</th><th>Motivo</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div style="padding:2rem 0;text-align:center;color:#4a5578;font-size:.85rem">El bot aún no ha ejecutado operaciones</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ── BALANCE BREAKDOWN ─────────────────────────────────────────────────
if balances:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.7rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem">Distribución de Cartera</div>', unsafe_allow_html=True)

    cols = st.columns(len(balances)) if len(balances) <= 6 else st.columns(6)
    colors = ["#F7931A","#627EEA","#48bb78","#63B3ED","#9F7AEA","#F6AD55"]
    for i, (asset, amount) in enumerate(list(balances.items())[:6]):
        cols[i % 6].markdown(f"""
        <div style="text-align:center;padding:.5rem">
          <div style="font-size:1.1rem;margin-bottom:.3rem" >●</div>
          <div style="font-weight:700;font-size:.9rem;color:{colors[i%len(colors)]}">{asset}</div>
          <div style="font-family:'DM Mono',monospace;font-size:.8rem;color:#8892b0">{amount:.5f}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# ── AUTO REFRESH ──────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
