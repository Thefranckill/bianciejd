"""
setup_credentials.py
--------------------
Asistente de configuración inicial.  Ejecuta este script una sola vez
para crear tu archivo .env con las credenciales necesarias.

Uso:  python setup_credentials.py

NOTA: Usa input() normal en lugar de getpass para compatibilidad
con Windows PowerShell (getpass congela la terminal en PS).
Las claves se muestran mientras escribes — asegúrate de estar
en un entorno privado.
"""

import sys
from pathlib import Path

BANNER = r"""
 ██████╗ ██╗████████╗ ██████╗ ██████╗ ██╗███╗   ██╗ ██████╗
 ██╔══██╗██║╚══██╔══╝██╔════╝██╔═══██╗██║████╗  ██║██╔════╝
 ██████╔╝██║   ██║   ██║     ██║   ██║██║██╔██╗ ██║██║  ███╗
 ██╔══██╗██║   ██║   ██║     ██║   ██║██║██║╚██╗██║██║   ██║
 ██████╔╝██║   ██║   ╚██████╗╚██████╔╝██║██║ ╚████║╚██████╔╝
 ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝
             Trading Bot — Configuración Inicial
"""


def ask(prompt: str, default: str = "") -> str:
    """Input simple compatible con Windows PowerShell."""
    display = f"  {prompt} [{default}]: " if default else f"  {prompt}: "
    try:
        value = input(display)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelado.")
        sys.exit(0)
    return value.strip() or default


def main():
    print(BANNER)
    print("  AVISO: Las claves se muestran al escribir. Asegurate de estar en privado.\n")

    env_path = Path(".env")
    if env_path.exists():
        overwrite = ask("Ya existe un archivo .env. Sobreescribir? (s/n)", default="n")
        if overwrite.lower() != "s":
            print("  Operacion cancelada. Se mantiene el archivo existente.")
            sys.exit(0)

    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  [1/4] CONFIGURACION DE BINANCE")
    print("  Obtén tus claves en:")
    print("  https://www.binance.com/es/my/settings/api-management")
    print("="*60)
    binance_api_key    = ask("Binance API Key")
    binance_secret_key = ask("Binance Secret Key")

    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  [2/4] CONFIGURACION DE GOOGLE GEMINI (IA para señales)")
    print("  Obtén tu API Key gratis en:")
    print("  https://aistudio.google.com/app/apikey")
    print("="*60)
    gemini_api_key = ask("Google Gemini API Key")

    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  [3/4] GOOGLE SHEETS para logs (opcional)")
    print("  Presiona Enter para omitir")
    print("="*60)
    google_sheet = ask("ID de Google Sheet", default="")

    # ------------------------------------------------------------------
    print("\n" + "="*60)
    print("  [4/4] PARAMETROS DEL BOT")
    print("="*60)
    pair          = ask("Par de trading", default="BTCUSDT")
    amount        = ask("Capital por operacion (USDT)", default="50")
    stop_loss     = ask("Stop Loss %", default="1.5")
    take_profit   = ask("Take Profit %", default="3.0")
    trailing_stop = ask("Trailing Stop %", default="1.0")
    dry_run       = ask("Modo simulacion DRY_RUN (true/false)", default="true")

    # ------------------------------------------------------------------
    env_content = f"""# Auto-generado por setup_credentials.py
# NO subas este archivo al repositorio.

# --- Binance ---
BINANCE_API_KEY={binance_api_key}
BINANCE_SECRET_KEY={binance_secret_key}

# --- Google Gemini (IA para señales de trading) ---
GEMINI_API_KEY={gemini_api_key}

# --- Google Sheets (logs) ---
GOOGLE_SHEET_ID={google_sheet}

# --- Parametros del bot ---
TRADING_PAIR={pair}
TRADE_AMOUNT_USDT={amount}
STOP_LOSS_PCT={float(stop_loss)/100:.4f}
TAKE_PROFIT_PCT={float(take_profit)/100:.4f}
TRAILING_STOP_PCT={float(trailing_stop)/100:.4f}
DRY_RUN={dry_run.lower()}
LOG_LEVEL=INFO
"""

    env_path.write_text(env_content, encoding="utf-8")
    print("\n" + "="*60)
    print("  ARCHIVO .env CREADO CORRECTAMENTE")
    print("="*60)
    print("  Ejecuta el bot:     python main.py")
    print("  Abre el dashboard:  streamlit run dashboard/app.py")
    print()


if __name__ == "__main__":
    main()
