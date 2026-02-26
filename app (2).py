"""
app.py - Dashboard Crypto Admin con métricas avanzadas
Ejecutar: python -m streamlit run app.py
"""

import sys, asyncio, time, json
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from exchange        import BinanceExchange
from config          import Config
from logger          import TradeLogger
from position_sizing import PositionSizer

st.set_page_config(page_title="Crypto Admin", page_icon="₿", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');
html,body,[data-testid="stAppViewContainer"]{background:#0B0E1A!important;font-family:'Syne',sans-serif;color:#E4E8F7}
[data-testid="stSidebar"]{background:#0D1120!important;border-right:1px solid rgba(255,255,255,0.06)}
#MainMenu,footer,header{visibility:hidden}
[data-testid="stToolbar"]{display:none}
.block-container{padding:1.5rem 2rem!important;max-width:100%!important}
.card{background:linear-gradient(145deg,#131729,#0f1322);border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:1.4rem 1.6rem;position:relative;overflow:hidden;margin-bottom:.5rem}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,rgba(99,179,237,0.4),transparent)}
.mcard{background:linear-gradient(145deg,#131729,#0f1322);border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:1.2rem 1.4rem}
.mlabel{font-size:.7rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.3rem}
.mvalue{font-size:1.45rem;font-weight:800;color:#E4E8F7;font-family:'DM Mono',monospace}
.mchange{font-size:.78rem;margin-top:.25rem;font-family:'DM Mono',monospace}
.up{color:#48bb78}.down{color:#fc8181}.neu{color:#8892b0}
.micon{width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;margin-bottom:.7rem}
.badge{display:inline-block;padding:.18rem .6rem;border-radius:20px;font-size:.7rem;font-weight:600}
.bbuy{background:rgba(72,187,120,0.15);color:#48bb78;border:1px solid rgba(72,187,120,0.3)}
.bsell{background:rgba(252,129,129,0.15);color:#fc8181;border:1px solid rgba(252,129,129,0.3)}
.tx-table{width:100%;border-collapse:collapse;font-family:'DM Mono',monospace;font-size:.82rem}
.tx-table thead th{color:#8892b0;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;padding:.6rem .8rem;text-align:left;border-bottom:1px solid rgba(255,255,255,0.07);font-family:'Syne',sans-serif}
.tx-table tbody td{padding:.7rem .8rem;border-bottom:1px solid rgba(255,255,255,0.04)}
.tx-table tbody tr:hover td{background:rgba(99,179,237,0.04)}
.nav-logo{padding:1.4rem 1.4rem 1rem;font-size:1.1rem;font-weight:800;display:flex;align-items:center;gap:.6rem;border-bottom:1px solid rgba(255,255,255,0.06)}
.nav-sec{padding:.4rem 1.4rem .2rem;font-size:.65rem;color:#4a5578;text-transform:uppercase;letter-spacing:.1em}
.nav-item{display:flex;align-items:center;gap:.7rem;padding:.55rem 1.4rem;font-size:.85rem;color:#8892b0;border-left:2px solid transparent}
.nav-item.active{color:#E4E8F7;background:rgba(99,179,237,0.07);border-left-color:#63B3ED}
.sdot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#48bb78;box-shadow:0 0 8px #48bb78;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid rgba(255,255,255,0.06)}
.pill{padding:.28rem .85rem;border-radius:20px;font-size:.73rem;font-weight:700}
.pill-dry{background:rgba(246,173,85,0.15);color:#F6AD55;border:1px solid rgba(246,173,85,0.4)}
.pill-live{background:rgba(252,129,129,0.15);color:#fc8181;border:1px solid rgba(252,129,129,0.4)}
.stButton>button{background:linear-gradient(135deg,#c53030,#e53e3e)!important;color:white!important;border:none!important;border-radius:12px!important;font-family:'Syne',sans-serif!important;font-weight:700!important;width:100%!important}
.metric-row{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1.2rem}
.stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}
.stat-item{background:rgba(255,255,255,0.03);border-radius:10px;padding:.7rem 1rem}
.stat-label{font-size:.68rem;color:#8892b0;margin-bottom:.2rem}
.stat-val{font-size:.95rem;font-weight:700;font-family:'DM Mono',monospace}
</style>
""", unsafe_allow_html=True)

# ── helpers ──────────────────────────────────────────────────────────
def run_async(coro):
    try: return asyncio.run(coro)
    except: return None

@st.cache_data(ttl=6)
def fetch_balances():
    async def _():
        async with BinanceExchange() as ex: return await ex.get_all_balances()
    return run_async(_()) or {}

@st.cache_data(ttl=6)
def fetch_price(sym):
    async def _():
        async with BinanceExchange() as ex: return await ex.get_price(sym)
    return run_async(_()) or 0.0

@st.cache_data(ttl=30)
def fetch_klines(sym, interval="15m", limit=100):
    async def _():
        async with BinanceExchange() as ex:
            return await ex._client.get_klines(symbol=sym, interval=interval, limit=limit)
    return run_async(_()) or []

def do_panic():
    async def _():
        async with BinanceExchange() as ex: return await ex.close_all_positions()
    return run_async(_()) or []

def load_backtest():
    p = Path("logs/backtest_results.json")
    if p.exists():
        try: return json.loads(p.read_text())
        except: pass
    return None

# ── advanced metrics ─────────────────────────────────────────────────
def compute_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {}
    df = pd.DataFrame(trades)
    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce").fillna(0)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    sells = df[df["action"] == "SELL"]
    if sells.empty:
        return {}
    wins   = sells[sells["pnl"] > 0]
    losses = sells[sells["pnl"] <= 0]
    win_rate    = len(wins) / len(sells) * 100
    avg_win     = wins["pnl"].mean() if not wins.empty else 0
    avg_loss    = losses["pnl"].mean() if not losses.empty else 0
    pf          = abs(wins["pnl"].sum() / losses["pnl"].sum()) if losses["pnl"].sum() != 0 else 999
    df_sorted   = df.sort_values("timestamp")
    cum_pnl     = df_sorted["pnl"].cumsum()
    rolling_max = cum_pnl.cummax()
    drawdown    = cum_pnl - rolling_max
    max_dd      = drawdown.min()
    # Sharpe
    if len(sells) > 1:
        r = sells["pnl"].pct_change().dropna()
        sharpe = (r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0
    else:
        sharpe = 0
    return {
        "total_pnl": df["pnl"].sum(),
        "win_rate":  win_rate,
        "avg_win":   avg_win,
        "avg_loss":  avg_loss,
        "profit_factor": pf,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "total_trades": len(sells),
        "wins": len(wins),
        "losses": len(losses),
    }

# ── data ─────────────────────────────────────────────────────────────
price    = fetch_price(Config.TRADING_PAIR)
balances = fetch_balances()
trades   = TradeLogger.load_trades()
klines   = fetch_klines(Config.TRADING_PAIR)
metrics  = compute_metrics(trades)
bt       = load_backtest()
sizer    = PositionSizer()
usdt_bal = balances.get("USDT", 0.0)
sizing   = sizer.summary(usdt_bal)
price_chg = 0.0
if len(klines) >= 2:
    o = float(klines[0][1])
    price_chg = ((price - o) / o * 100) if o else 0

# ── sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="nav-logo">₿ Crypto <span style="color:#F6AD55">Admin</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-sec">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("", ["📊 Dashboard", "📈 Backtesting", "⚙️ Config"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown(f'<div style="padding:0 1.4rem;font-size:.78rem;color:#8892b0;font-family:\'DM Mono\',monospace;line-height:2.2">Par: <span style="color:#E4E8F7">{Config.TRADING_PAIR}</span><br>SL: <span style="color:#fc8181">{Config.STOP_LOSS_PCT*100:.1f}%</span> &nbsp; TP: <span style="color:#48bb78">{Config.TAKE_PROFIT_PCT*100:.1f}%</span><br>Sizing: <span style="color:#63B3ED">{Config.POSITION_SIZE_PCT*100:.0f}% capital</span></div>', unsafe_allow_html=True)
    st.markdown("")
    auto_refresh = st.checkbox("Auto-refresh (10s)", value=True)
    st.markdown("---")
    if st.button("⛔  PÁNICO — Cerrar Todo"):
        with st.spinner("Cerrando..."):
            r = do_panic()
        st.success(f"{len(r)} posiciones cerradas")

# ════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":

    mode_pill = "pill-dry" if Config.DRY_RUN else "pill-live"
    mode_txt  = "🟡 DRY RUN" if Config.DRY_RUN else "🔴 LIVE"
    st.markdown(f"""
    <div class="topbar">
      <div><div style="font-size:1.3rem;font-weight:800">Dashboard &nbsp;<span class="sdot"></span></div>
           <div style="font-size:.78rem;color:#8892b0">Actualizado: {time.strftime('%H:%M:%S')} · Binance Spot</div></div>
      <div style="display:flex;gap:1rem;align-items:center">
        <span class="pill {mode_pill}">{mode_txt}</span>
        <span style="font-size:.8rem;color:#8892b0;font-family:'DM Mono',monospace">{Config.TRADING_PAIR}</span>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── 4 metric cards ───────────────────────────────────────────────
    c1,c2,c3,c4 = st.columns(4)
    chg_c = "up" if price_chg>=0 else "down"
    chg_s = "▲" if price_chg>=0 else "▼"

    def mcard(col, icon, bg, label, val, sub=None, sub_c="neu"):
        col.markdown(f'<div class="mcard"><div class="micon" style="background:{bg}">{icon}</div><div class="mlabel">{label}</div><div class="mvalue">{val}</div>{f"<div class=\'mchange {sub_c}\'>{sub}</div>" if sub else ""}</div>', unsafe_allow_html=True)

    mcard(c1,"₿","rgba(246,173,85,0.15)","BTC Price",f"${price:,.2f}",f"{chg_s} {abs(price_chg):.2f}% (2h)",chg_c)
    mcard(c2,"$","rgba(99,179,237,0.15)","Balance USDT",f"${usdt_bal:,.2f}",f"Próxima op: ${sizing['trade_amount']:.2f}","neu")
    pnl = metrics.get("total_pnl", 0)
    pnl_c = "up" if pnl>=0 else "down"
    mcard(c3,"◈","rgba(72,187,120,0.15)","PnL Total",f"${pnl:+.2f}",f"Win rate: {metrics.get('win_rate',0):.1f}%",pnl_c)
    mcard(c4,"◎","rgba(159,122,234,0.15)","Sharpe Ratio",f"{metrics.get('sharpe',0):.3f}",f"Max DD: ${metrics.get('max_drawdown',0):.2f}","neu")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Chart + tickers ──────────────────────────────────────────────
    cl, cr = st.columns([3,1])
    with cl:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div style="display:flex;justify-content:space-between;margin-bottom:.8rem"><div><div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em">Precio en Tiempo Real — Velas 15m</div><div style="font-size:1.5rem;font-weight:800;font-family:\'DM Mono\',monospace">${price:,.2f} <span style="font-size:.9rem;color:{"#48bb78" if price_chg>=0 else "#fc8181"}">{"▲" if price_chg>=0 else "▼"} {abs(price_chg):.2f}%</span></div></div><div style="font-size:.75rem;color:#8892b0">{Config.TRADING_PAIR} · Binance</div></div>', unsafe_allow_html=True)
        if klines:
            dk = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qav","nt","tbbav","tbqav","i"])
            for col in ["o","h","l","c","v"]: dk[col] = pd.to_numeric(dk[col])
            dk["t"] = pd.to_datetime(dk["t"], unit="ms")
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=dk["t"],open=dk["o"],high=dk["h"],low=dk["l"],close=dk["c"],
                increasing_line_color="#48bb78",decreasing_line_color="#fc8181",
                increasing_fillcolor="rgba(72,187,120,0.7)",decreasing_fillcolor="rgba(252,129,129,0.7)",name="OHLC"))
            fig.add_trace(go.Bar(x=dk["t"],y=dk["v"],yaxis="y2",
                marker_color=["rgba(72,187,120,0.2)" if c>=o else "rgba(252,129,129,0.2)" for c,o in zip(dk["c"],dk["o"])],name="Vol"))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8892b0",family="DM Mono"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)",rangeslider_visible=False),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)",side="right"),
                yaxis2=dict(overlaying="y",side="left",showgrid=False,showticklabels=False,range=[0,dk["v"].max()*5]),
                margin=dict(l=0,r=50,t=5,b=5),height=320,showlegend=False,hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with cr:
        st.markdown('<div class="card" style="height:100%">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.8rem">Quick Tickers</div>', unsafe_allow_html=True)
        for icon, color, sym, name, pair in [("₿","#F7931A","BTC","Bitcoin","BTCUSDT"),("Ξ","#627EEA","ETH","Ethereum","ETHUSDT"),("◎","#9945FF","SOL","Solana","SOLUSDT"),("✦","#E84142","AVAX","Avalanche","AVAXUSDT")]:
            p = fetch_price(pair)
            st.markdown(f'<div style="display:flex;align-items:center;gap:.8rem;padding:.65rem 0;border-bottom:1px solid rgba(255,255,255,0.04)"><div style="width:30px;height:30px;border-radius:50%;background:rgba(255,255,255,0.06);display:flex;align-items:center;justify-content:center">{icon}</div><div><div style="font-weight:700;font-size:.85rem">{sym}</div><div style="font-size:.68rem;color:#8892b0">{name}</div></div><div style="margin-left:auto;font-family:\'DM Mono\',monospace;font-size:.88rem">${p:,.2f}</div></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Métricas avanzadas ───────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem">📐 Métricas Avanzadas de Rendimiento</div>', unsafe_allow_html=True)
    m1,m2,m3,m4,m5,m6 = st.columns(6)
    def stat(col, label, val, c="neu"):
        col.markdown(f'<div class="stat-item"><div class="stat-label">{label}</div><div class="stat-val {c}">{val}</div></div>', unsafe_allow_html=True)

    stat(m1,"Win Rate",    f"{metrics.get('win_rate',0):.1f}%",    "up" if metrics.get("win_rate",0)>50 else "down")
    stat(m2,"Profit Factor",f"{metrics.get('profit_factor',0):.2f}","up" if metrics.get("profit_factor",0)>1 else "down")
    stat(m3,"Avg Win",     f"${metrics.get('avg_win',0):.2f}",      "up")
    stat(m4,"Avg Loss",    f"${metrics.get('avg_loss',0):.2f}",     "down")
    stat(m5,"Max Drawdown",f"${metrics.get('max_drawdown',0):.2f}", "down")
    stat(m6,"Total Ops",   f"{metrics.get('total_trades',0)}",      "neu")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Position sizing info ─────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    ps1, ps2 = st.columns([1,2])
    with ps1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.8rem">💰 Position Sizing</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="stat-grid">
          <div class="stat-item"><div class="stat-label">Capital</div><div class="stat-val">${sizing['capital']:.2f}</div></div>
          <div class="stat-item"><div class="stat-label">Próx. Operación</div><div class="stat-val up">${sizing['trade_amount']:.2f}</div></div>
          <div class="stat-item"><div class="stat-label">Máx. Pérdida</div><div class="stat-val down">${sizing['max_loss']:.2f}</div></div>
          <div class="stat-item"><div class="stat-label">Máx. Ganancia</div><div class="stat-val up">${sizing['max_gain']:.2f}</div></div>
          <div class="stat-item"><div class="stat-label">Ratio R/R</div><div class="stat-val">{sizing['risk_reward']}</div></div>
          <div class="stat-item"><div class="stat-label">% en Riesgo</div><div class="stat-val">{sizing['pct_at_risk']:.2f}%</div></div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with ps2:
        # PnL curve
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem">📈 Curva de Rendimiento</div>', unsafe_allow_html=True)
        if trades:
            df_p = pd.DataFrame(trades)
            df_p["pnl"] = pd.to_numeric(df_p["pnl"], errors="coerce").fillna(0)
            df_p["timestamp"] = pd.to_datetime(df_p["timestamp"])
            df_p = df_p.sort_values("timestamp")
            df_p["cum"] = df_p["pnl"].cumsum()
            clr = "#48bb78" if pnl >= 0 else "#fc8181"
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df_p["timestamp"],y=df_p["cum"],fill="tozeroy",
                line=dict(color=clr,width=2),fillcolor=f"rgba({'72,187,120' if pnl>=0 else '252,129,129'},0.08)",mode="lines+markers",
                marker=dict(size=4,color=clr)))
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8892b0",family="DM Mono"),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)",showgrid=False),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)",tickprefix="$",side="right"),
                margin=dict(l=0,r=45,t=5,b=5),height=200,showlegend=False)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.markdown('<div style="height:150px;display:flex;align-items:center;justify-content:center;color:#4a5578;font-size:.85rem">Sin operaciones aún</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Trade history ────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="display:flex;justify-content:space-between;margin-bottom:.8rem"><div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em">Historial de Operaciones</div></div>', unsafe_allow_html=True)
    if trades:
        recent = sorted(trades, key=lambda x: x.get("timestamp",""), reverse=True)[:10]
        rows = ""
        for t in recent:
            a = t.get("action","")
            bc = "bbuy" if a=="BUY" else "bsell"
            pv = float(t.get("pnl") or 0)
            ps = f'<span class="{"up" if pv>=0 else "down"}">${pv:+.2f}</span>' if pv else "—"
            rows += f'<tr><td><span class="badge {bc}">{a}</span></td><td>{t.get("symbol","")}</td><td>${float(t.get("price") or 0):,.2f}</td><td>{float(t.get("qty") or 0):.6f}</td><td>{ps}</td><td style="color:#8892b0;font-size:.74rem">{str(t.get("timestamp",""))[:16]}</td><td style="color:#8892b0;font-size:.72rem">{t.get("reason","—")}</td></tr>'
        st.markdown(f'<table class="tx-table"><thead><tr><th>Acción</th><th>Par</th><th>Precio</th><th>Cantidad</th><th>PnL</th><th>Fecha</th><th>Motivo</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="padding:2rem 0;text-align:center;color:#4a5578;font-size:.85rem">Sin operaciones todavía</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
elif page == "📈 Backtesting":

    st.markdown('<div style="font-size:1.3rem;font-weight:800;margin-bottom:1.5rem">📈 Backtesting — Prueba Histórica</div>', unsafe_allow_html=True)

    if bt:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem">Último Resultado</div>', unsafe_allow_html=True)
        b1,b2,b3,b4 = st.columns(4)
        ret_c = "up" if bt.get("total_return_pct",0)>=0 else "down"
        alpha_c = "up" if bt.get("alpha",0)>=0 else "down"
        mcard(b1,"◈","rgba(72,187,120,0.15)","Retorno Bot",f"{bt.get('total_return_pct',0):+.2f}%",f"vs Buy&Hold: {bt.get('buy_hold_pct',0):+.2f}%",ret_c)
        mcard(b2,"▲","rgba(246,173,85,0.15)","Alpha",f"{bt.get('alpha',0):+.2f}%","Ventaja sobre mercado",alpha_c)
        mcard(b3,"◎","rgba(99,179,237,0.15)","Profit Factor",f"{bt.get('profit_factor',0):.2f}",f"Sharpe: {bt.get('sharpe_ratio',0):.3f}","neu")
        mcard(b4,"●","rgba(159,122,234,0.15)","Max Drawdown",f"{bt.get('max_drawdown_pct',0):.2f}%",f"Win Rate: {bt.get('win_rate_pct',0):.1f}%","down")
        st.markdown("<br>", unsafe_allow_html=True)
        g1,g2,g3,g4,g5,g6 = st.columns(6)
        stat(g1,"Capital Inicial",f"${bt.get('initial_capital',0):,.0f}")
        stat(g2,"Capital Final",f"${bt.get('final_equity',0):,.2f}","up" if bt.get("total_return_pct",0)>=0 else "down")
        stat(g3,"Operaciones",str(bt.get("total_trades",0)))
        stat(g4,"Ganancia Prom.",f"${bt.get('avg_win_usd',0):.2f}","up")
        stat(g5,"Pérdida Prom.",f"${bt.get('avg_loss_usd',0):.2f}","down")
        stat(g6,"Sharpe Ratio",f"{bt.get('sharpe_ratio',0):.3f}")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No hay resultados de backtesting aún. Ejecuta el backtest con:")
        st.code("python backtesting.py --days 30 --interval 1h")
        st.code("python backtesting.py --days 90 --interval 4h --capital 1000")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.8rem">Ejecutar Nuevo Backtest</div>', unsafe_allow_html=True)
    bc1,bc2,bc3,bc4 = st.columns(4)
    days_bt     = bc1.selectbox("Período",     [7,14,30,60,90,180], index=2)
    interval_bt = bc2.selectbox("Intervalo",   ["15m","1h","4h","1d"], index=1)
    capital_bt  = bc3.number_input("Capital $", value=1000.0, step=100.0)
    pair_bt     = bc4.text_input("Par",         value=Config.TRADING_PAIR)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("▶  Ejecutar Backtest", use_container_width=False):
        st.info(f"Abre una terminal y ejecuta:")
        st.code(f"python backtesting.py --days {days_bt} --interval {interval_bt} --capital {capital_bt} --pair {pair_bt}")
        st.info("Cuando termine, recarga esta página para ver los resultados.")
    st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════
elif page == "⚙️ Config":

    st.markdown('<div style="font-size:1.3rem;font-weight:800;margin-bottom:1.5rem">⚙️ Configuración del Bot</div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem">Variables Activas</div>', unsafe_allow_html=True)
    cfg_data = {
        "Variable": ["TRADING_PAIR","STOP_LOSS_PCT","TAKE_PROFIT_PCT","TRAILING_STOP_PCT","POSITION_SIZE_PCT","MAX_POSITIONS","MIN_TRADE_USDT","DRY_RUN","LOG_LEVEL"],
        "Valor":    [Config.TRADING_PAIR,f"{Config.STOP_LOSS_PCT*100:.2f}%",f"{Config.TAKE_PROFIT_PCT*100:.2f}%",f"{Config.TRAILING_STOP_PCT*100:.2f}%",f"{Config.POSITION_SIZE_PCT*100:.0f}%",str(Config.MAX_POSITIONS),f"${Config.MIN_TRADE_USDT:.0f}",str(Config.DRY_RUN),Config.LOG_LEVEL],
        "Descripción": ["Par de trading","Pérdida máxima por operación","Ganancia objetivo por operación","Trailing stop desde máximo","% del capital por operación","Máx. posiciones simultáneas","Mínimo en USDT por operación","Modo simulación (sin dinero real)","Nivel de logs"],
    }
    st.dataframe(pd.DataFrame(cfg_data), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:.68rem;color:#8892b0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.8rem">Para cambiar configuración</div>', unsafe_allow_html=True)
    st.code("notepad .env", language="powershell")
    st.markdown("Edita los valores y guarda. Reinicia el bot con <code>python main.py</code>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── auto refresh ─────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(10)
    st.rerun()
