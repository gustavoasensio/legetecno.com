"""
Script de diagnóstico: verifica que la conexión con PPI funciona.
Corré con: python test_ppi.py
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

def test_ppi():
    sandbox = os.getenv("PPI_SANDBOX", "false").lower() == "true"
    modo = "SANDBOX" if sandbox else "PRODUCCIÓN"

    print("=" * 60)
    print(f"DIAGNÓSTICO DE CONEXIÓN PPI ({modo})")
    print("=" * 60)

    if sandbox:
        pub = os.getenv("PPI_SANDBOX_PUBLIC_KEY", "")
        priv = os.getenv("PPI_SANDBOX_PRIVATE_KEY", "")
        env_pub = "PPI_SANDBOX_PUBLIC_KEY"
        env_priv = "PPI_SANDBOX_PRIVATE_KEY"
    else:
        pub = os.getenv("PPI_PUBLIC_KEY", "")
        priv = os.getenv("PPI_PRIVATE_KEY", "")
        env_pub = "PPI_PUBLIC_KEY"
        env_priv = "PPI_PRIVATE_KEY"

    if not pub:
        print(f"ERROR: {env_pub} no configurada en .env")
        sys.exit(1)

    if not priv:
        print(f"ERROR: {env_priv} no configurada en .env")
        sys.exit(1)

    print(f"  Public key: {pub[:8]}...{pub[-4:]} ✓")
    print(f"  Private key: {'*' * 20} ✓")
    print()

    sys.path.insert(0, os.path.dirname(__file__))
    from data.ppi_client import PPIClient, PPIAuthError

    print("1. Autenticando con PPI...")
    try:
        client = PPIClient()  # Lee sandbox mode y claves desde env
        ok = client.authenticate()
        if ok:
            print("   ✓ Autenticación exitosa")
        else:
            print("   ✗ Autenticación fallida (credenciales incorrectas)")
            sys.exit(1)
    except PPIAuthError as e:
        print(f"   ✗ {e}")
        sys.exit(1)

    print()
    print("2. Obteniendo cuentas...")
    accounts = client.get_accounts()
    if accounts:
        print(f"   ✓ {len(accounts)} cuenta(s) encontrada(s)")
        for acc in accounts:
            print(f"     → {acc}")
    else:
        print("   ⚠ No se encontraron cuentas (puede ser normal en sandbox)")

    print()
    print("3. Obteniendo portfolio...")
    portfolio = client.get_portfolio_formatted()
    if portfolio.get("holdings"):
        print(f"   ✓ {len(portfolio['holdings'])} posición(es) en cartera")
        print(f"   → Cash ARS:  ${portfolio.get('cash_ars', 0):,.0f}")
        print(f"   → Cash USD:  U${portfolio.get('cash_usd', 0):,.2f}")
        print()
        print("   POSICIONES:")
        for h in portfolio["holdings"]:
            pnl = f"{h['pnl_pct']:+.1f}%" if h.get("pnl_pct") is not None else "N/A"
            print(f"     {h['ticker']:10s}  {h['cantidad']:>8.0f} u  "
                  f"${h['precio_mercado']:>10,.2f}  P&L: {pnl}")
    else:
        print("   ⚠ Portfolio vacío o estructura desconocida")
        print("   → Raw response guardado en ppi_raw_debug.json")
        with open("ppi_raw_debug.json", "w") as f:
            json.dump(portfolio.get("_raw", portfolio), f, indent=2, ensure_ascii=False)

    print()
    print("4. Probando precio de un CEDEAR (MELI)...")
    precio = client.get_cedear_price("MELI")
    if precio.get("precio"):
        print(f"   ✓ MELI: ${precio['precio']:,.2f} ARS")
    else:
        print(f"   ⚠ No se pudo obtener precio: {precio.get('error', 'sin datos')}")

    print()
    print("5. Obteniendo dólar MEP desde BYMA...")
    mep = client.get_dolar_mep()
    if mep:
        print(f"   ✓ Dólar MEP: ${mep:,.2f} ARS")
    else:
        print("   ⚠ No se pudo calcular MEP (normal fuera de horario de mercado)")

    print()
    print("=" * 60)
    print("DIAGNÓSTICO COMPLETADO")
    print("Si todos los checks pasaron, el sistema está listo.")
    print("=" * 60)

if __name__ == "__main__":
    test_ppi()
