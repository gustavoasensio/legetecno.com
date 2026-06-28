"""
Diagnóstico de conexión: Yahoo Finance + dolarapi.com + PPI (opcional).
Corré con: python test_conexion.py
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from data.market_data import get_cedear_price, get_dolar_mep, get_dolar_ccl, get_dolar_simple


def main():
    print("=" * 60)
    print("DIAGNÓSTICO DE CONEXIÓN — COPILOT INVERSIONES")
    print("=" * 60)
    print()

    # ── 1. Dólar MEP ────────────────────────────────────────────
    print("1. Dólar MEP (dolarapi.com)...")
    mep = get_dolar_mep()
    ccl = get_dolar_ccl()
    blue = get_dolar_simple("blue")
    if mep:
        print(f"   ✓ MEP:  ARS {mep:,.2f}")
        print(f"   ✓ CCL:  ARS {ccl:,.2f}" if ccl else "   ⚠ CCL: no disponible")
        print(f"   ✓ Blue: ARS {blue:,.2f}" if blue else "   ⚠ Blue: no disponible")
    else:
        print("   ✗ No se pudo obtener el dólar MEP")
        print("     → Verificá tu conexión a internet")
    print()

    # ── 2. CEDEARs en BYMA ──────────────────────────────────────
    print("2. Precios CEDEAR en BYMA (Yahoo Finance)...")
    tickers = ["ASML", "META", "MSFT", "MELI", "KO"]
    ok_count = 0
    for t in tickers:
        r = get_cedear_price(t)
        if r.get("precio_ars"):
            print(f"   ✓ {t:6s}  ARS {r['precio_ars']:>12,.2f}  [{r['fuente']}]")
            ok_count += 1
        elif r.get("precio_usd"):
            usd_str = f"USD {r['precio_usd']:>10,.2f}"
            print(f"   ~ {t:6s}  {usd_str}  [Yahoo/USD — sin precio BYMA]")
            ok_count += 1
        else:
            print(f"   ✗ {t:6s}  sin precio")
    print()

    # ── Resumen ──────────────────────────────────────────────────
    if mep and ok_count > 0:
        print("=" * 60)
        print("✓ SISTEMA LISTO — podés correr:")
        print("    python calcular.py      → análisis completo de cartera")
        print("    python monitor_stops.py → chequeo de stops")
        print("=" * 60)
    else:
        print("=" * 60)
        print("✗ Hay problemas de conectividad. Verificá tu red.")
        print("=" * 60)
    print()


if __name__ == "__main__":
    main()
