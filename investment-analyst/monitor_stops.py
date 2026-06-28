"""
Monitor de stops: compara precios actuales contra stops definidos en cartera.json
Corré con: python monitor_stops.py
Diseñado para correr una vez por día o cuando te preocupe el mercado.
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).parent


def cargar_cartera():
    with open(BASE_DIR / "cartera.json") as f:
        return json.load(f)


def get_precios(tickers):
    """Obtiene precios en USD via Yahoo Finance (BYMA). Sin API key."""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from data.market_data import get_prices_bulk, get_dolar_mep
        dolar = get_dolar_mep() or cargar_cartera().get("dolar_mep_referencia", 1499)
        precios_ars = get_prices_bulk(tickers, dolar_mep=dolar)
        precios_usd = {t: p / dolar for t, p in precios_ars.items()}
        if precios_usd:
            print(f"  Precios de Yahoo Finance: {list(precios_usd.keys())}")
        return precios_usd
    except Exception as e:
        print(f"  Yahoo Finance no disponible: {e}")
        return {}


def monitorear():
    cartera = cargar_cartera()
    holdings = [h for h in cartera.get("holdings", []) if h.get("cantidad", 0) > 0 and h.get("stop_loss_usd")]
    dolar = cartera.get("dolar_mep_referencia", 1499)

    tickers = [h["ticker"] for h in holdings]
    precios = get_precios(tickers)

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║              MONITOR DE STOP-LOSS                           ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    hay_alerta = False

    for h in holdings:
        ticker = h["ticker"]
        stop = h["stop_loss_usd"]
        entrada = h["precio_entrada_usd"]
        cantidad = h["cantidad"]
        target = h.get("target_usd", 0)

        precio_actual = precios.get(ticker, entrada)  # fallback a entrada si no hay precio
        fuente = "PPI" if ticker in precios else "entrada (sin precio real)"

        dist_stop_pct = (precio_actual - stop) / precio_actual * 100 if precio_actual else 0
        pnl_pct = (precio_actual - entrada) / entrada * 100

        if dist_stop_pct < 0:
            estado = "🚨 STOP TOCADO — VENDER YA"
            hay_alerta = True
        elif dist_stop_pct < 3.0:
            estado = "⚠  ALERTA: muy cerca del stop"
            hay_alerta = True
        elif dist_stop_pct < 7.0:
            estado = "👁  Vigilar"
        else:
            estado = "✓  OK"

        print(f"  {ticker}")
        print(f"    Precio actual:  US$ {precio_actual:.4f}  [{fuente}]")
        print(f"    Stop-loss:      US$ {stop:.4f}  ({dist_stop_pct:+.1f}% de distancia)")
        print(f"    Entrada:        US$ {entrada:.4f}  (P&L: {pnl_pct:+.1f}%)")
        if target:
            dist_target_pct = (target - precio_actual) / precio_actual * 100
            print(f"    Target:         US$ {target:.4f}  ({dist_target_pct:+.1f}% hasta target)")
        print(f"    Estado:         {estado}")
        print()

    if hay_alerta:
        print("  ╔══════════════════════════════════════════════════════════╗")
        print("  ║  HAY ALERTAS ACTIVAS. Revisá las posiciones indicadas.  ║")
        print("  ║  Si el stop fue tocado, ejecutá la venta SIN DUDAR.     ║")
        print("  ╚══════════════════════════════════════════════════════════╝")
    else:
        print("  Todas las posiciones dentro de rangos normales.")

    print()
    print("  REGLA: Si el precio toca el stop → VENDER. Sin excepciones. Sin 'esperar un poco'.")
    print()


if __name__ == "__main__":
    monitorear()
