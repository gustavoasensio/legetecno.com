"""
Calculador de cartera — sin llamadas a IA.
Corre con: python calcular.py
Resultado: tabla con P&L, stops, exposición y comisiones.
"""
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
BYMA_COMISION_PCT = 0.006    # 0.6% por lado
BYMA_IVA = 0.21              # 21% IVA sobre comisión
COMISION_TOTAL_PCT = BYMA_COMISION_PCT * (1 + BYMA_IVA)  # ≈ 0.726% por lado


def cargar_cartera() -> dict:
    path = BASE_DIR / "cartera.json"
    if not path.exists():
        print("ERROR: cartera.json no encontrado.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def get_precios_ppi(tickers: list) -> dict:
    """Intenta obtener precios reales de PPI. Devuelve {} si no hay credenciales."""
    pub = os.getenv("PPI_PUBLIC_KEY", "")
    priv = os.getenv("PPI_PRIVATE_KEY", "")
    if not pub or not priv:
        return {}
    try:
        sys.path.insert(0, str(BASE_DIR))
        from data.ppi_client import PPIClient
        client = PPIClient(pub, priv)
        client.authenticate()
        precios = {}
        for ticker in tickers:
            p = client.get_cedear_price(ticker)
            if p.get("precio"):
                precios[ticker] = p["precio"]
        return precios
    except Exception as e:
        print(f"[PPI] No se pudieron obtener precios: {e}")
        return {}


def calcular_comision(monto_usd: float, dolar: float) -> float:
    """Comisión BYMA total en USD para una operación (un solo lado)."""
    monto_ars = monto_usd * dolar
    comision_ars = monto_ars * COMISION_TOTAL_PCT
    return comision_ars / dolar


def calcular_dias_desde(fecha_str: str) -> int:
    if not fecha_str:
        return 0
    try:
        entrada = datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
        return (date.today() - entrada).days
    except Exception:
        return 0


def analizar(cartera: dict, precios_ppi: dict) -> dict:
    capital_total = cartera["capital_total_usd"]
    dolar = cartera["dolar_mep_referencia"]
    holdings = [h for h in cartera.get("holdings", []) if h.get("cantidad", 0) > 0]

    resultados = []
    capital_invertido = 0
    riesgo_total_usd = 0
    ganancia_potencial_total = 0
    comisiones_junio = 0

    for h in holdings:
        ticker = h["ticker"]
        cantidad = h["cantidad"]
        entrada = h["precio_entrada_usd"]
        stop = h.get("stop_loss_usd", 0)
        target = h.get("target_usd", 0)
        fecha = h.get("fecha_entrada", "")

        # Precio actual: PPI > entrada (fallback)
        precio_actual = precios_ppi.get(ticker) or precios_ppi.get(f"{ticker}D")
        if precio_actual:
            # PPI devuelve ARS → convertir a USD
            precio_actual_usd = precio_actual / dolar
        else:
            precio_actual_usd = entrada  # sin precio real, usamos entrada
            precio_actual = None

        capital_pos = cantidad * entrada
        capital_actual = cantidad * precio_actual_usd
        pnl_usd = capital_actual - capital_pos
        pnl_pct = (pnl_usd / capital_pos * 100) if capital_pos > 0 else 0
        pct_portfolio = (capital_pos / capital_total * 100)

        # Stop y target
        riesgo_usd = cantidad * (precio_actual_usd - stop) if stop else None
        ganancia_usd = cantidad * (target - precio_actual_usd) if target else None
        rr_ratio = abs(ganancia_usd / riesgo_usd) if (riesgo_usd and ganancia_usd and riesgo_usd != 0) else None

        distancia_stop_pct = ((precio_actual_usd - stop) / precio_actual_usd * 100) if stop and precio_actual_usd else None

        dias = calcular_dias_desde(fecha)

        # Comisión de entrada ya pagada
        com_entrada = calcular_comision(capital_pos, dolar)

        capital_invertido += capital_pos
        if riesgo_usd is not None:
            riesgo_total_usd += abs(riesgo_usd)
        if ganancia_usd is not None:
            ganancia_potencial_total += ganancia_usd

        resultados.append({
            "ticker": ticker,
            "cantidad": cantidad,
            "entrada_usd": entrada,
            "precio_actual_usd": round(precio_actual_usd, 4) if precio_actual_usd else None,
            "precio_actual_fuente": "PPI" if precio_actual else "entrada",
            "capital_pos_usd": round(capital_pos, 2),
            "pct_portfolio": round(pct_portfolio, 1),
            "pnl_usd": round(pnl_usd, 2),
            "pnl_pct": round(pnl_pct, 2),
            "stop_usd": stop,
            "distancia_stop_pct": round(distancia_stop_pct, 1) if distancia_stop_pct is not None else None,
            "riesgo_si_stop_usd": round(abs(riesgo_usd), 2) if riesgo_usd is not None else None,
            "target_usd": target,
            "ganancia_si_target_usd": round(ganancia_usd, 2) if ganancia_usd is not None else None,
            "rr_ratio": round(rr_ratio, 2) if rr_ratio else None,
            "dias_en_posicion": dias,
            "comision_entrada_usd": round(com_entrada, 2),
        })

    # Pérdidas junio
    ops_cerradas = cartera.get("operaciones_cerradas_junio", [])
    perdida_junio = sum(op.get("resultado_usd", 0) for op in ops_cerradas)
    comisiones_estimadas_junio = len(ops_cerradas) * 2 * calcular_comision(3000, dolar)  # estimado

    cash_total = cartera.get("cash_usd", 0) + cartera.get("cash_ars", 0) / dolar
    capital_en_posiciones = capital_invertido
    capital_libre = capital_total - capital_en_posiciones - cash_total

    return {
        "fecha_calculo": datetime.now().isoformat(),
        "capital_total_usd": capital_total,
        "capital_invertido_usd": round(capital_investido := capital_invertido, 2),
        "capital_libre_usd": round(max(capital_libre, 0), 2),
        "pct_invertido": round(capital_invertido / capital_total * 100, 1),
        "pct_cash": round((capital_total - capital_invertido) / capital_total * 100, 1),
        "posiciones": resultados,
        "riesgo_total_si_todos_stops_usd": round(riesgo_total_usd, 2),
        "riesgo_pct_portfolio": round(riesgo_total_usd / capital_total * 100, 2),
        "ganancia_potencial_total_usd": round(ganancia_potencial_total, 2),
        "perdidas_realizadas_junio_usd": round(perdida_junio, 2),
        "comisiones_estimadas_junio_usd": round(comisiones_estimadas_junio, 2),
        "dolar_mep_usado": dolar,
        "reglas": {
            "max_riesgo_por_op_pct": 1.5,
            "max_riesgo_total_pct": 6.0,
            "rr_minimo": 2.0,
            "estado_riesgo": (
                "OK" if riesgo_total_usd / capital_total * 100 <= 6.0
                else "EXCEDIDO"
            ),
        },
    }


def imprimir_reporte(data: dict):
    pos = data["posiciones"]
    ancho = 110
    linea = "─" * ancho

    print()
    print("╔" + "═" * (ancho - 2) + "╗")
    print("║" + " ANÁLISIS DE CARTERA ".center(ancho - 2) + "║")
    print("║" + f" {data['fecha_calculo'][:19]} ".center(ancho - 2) + "║")
    print("╚" + "═" * (ancho - 2) + "╝")

    print()
    print("  RESUMEN")
    print(linea)
    print(f"  Capital total:        US$ {data['capital_total_usd']:>10,.2f}")
    print(f"  Capital invertido:    US$ {data['capital_invertido_usd']:>10,.2f}  ({data['pct_invertido']}%)")
    print(f"  Cash libre:           US$ {data['capital_libre_usd']:>10,.2f}  ({data['pct_cash']}%)")
    print(f"  Riesgo total (stops): US$ {data['riesgo_total_si_todos_stops_usd']:>10,.2f}  ({data['riesgo_pct_portfolio']}%)  [{data['reglas']['estado_riesgo']}]")
    print(f"  Ganancia potencial:   US$ {data['ganancia_potencial_total_usd']:>10,.2f}")
    print(f"  Pérdidas junio:       US$ {data['perdidas_realizadas_junio_usd']:>10,.2f}")
    print(f"  Comisiones junio est: US$ {data['comisiones_estimadas_junio_usd']:>10,.2f}")

    print()
    print("  POSICIONES ABIERTAS")
    print(linea)
    header = f"  {'TICKER':<8} {'CANT':>6} {'ENTRADA':>9} {'ACTUAL':>9} {'P&L %':>7} {'P&L $':>8} {'% PORTF':>8} {'STOP':>9} {'DIST STOP':>10} {'RIESGO $':>9} {'RR':>5} {'DÍAS':>5}"
    print(header)
    print(linea)

    for p in pos:
        pnl_color = "+" if p["pnl_usd"] >= 0 else ""
        fuente = "*" if p["precio_actual_fuente"] == "PPI" else " "
        actual_str = f"{p['precio_actual_usd']:.4f}{fuente}" if p["precio_actual_usd"] else "  N/A   "
        stop_str = f"{p['stop_usd']:.4f}" if p["stop_usd"] else "  N/A  "
        dist_str = f"-{p['distancia_stop_pct']:.1f}%" if p["distancia_stop_pct"] is not None else "  N/A  "
        riesgo_str = f"{p['riesgo_si_stop_usd']:.2f}" if p["riesgo_si_stop_usd"] is not None else "  N/A"
        rr_str = f"{p['rr_ratio']:.1f}:1" if p["rr_ratio"] else "  N/A"

        print(f"  {p['ticker']:<8} {p['cantidad']:>6.0f} {p['entrada_usd']:>9.4f} {actual_str:>9} "
              f"{pnl_color}{p['pnl_pct']:>6.2f}% {pnl_color}{p['pnl_usd']:>8.2f} "
              f"{p['pct_portfolio']:>7.1f}% {stop_str:>9} {dist_str:>10} "
              f"{riesgo_str:>9} {rr_str:>5} {p['dias_en_posicion']:>5}")

    print(linea)
    if any(p["precio_actual_fuente"] == "PPI" for p in pos):
        print("  * precio de PPI en tiempo real")
    else:
        print("  Precios: usando precio de entrada (configurá PPI para precios reales)")

    print()
    print("  ALERTAS")
    print(linea)
    alertas = []
    for p in pos:
        if p["distancia_stop_pct"] is not None and p["distancia_stop_pct"] < 3.0:
            alertas.append(f"  ⚠ {p['ticker']}: a solo {p['distancia_stop_pct']:.1f}% del stop. VIGILAR.")
        if p["rr_ratio"] is not None and p["rr_ratio"] < 2.0:
            alertas.append(f"  ⚠ {p['ticker']}: R/R {p['rr_ratio']:.1f}:1 por debajo del mínimo 2:1.")
        if p["pct_portfolio"] > 20:
            alertas.append(f"  ⚠ {p['ticker']}: {p['pct_portfolio']:.1f}% del portfolio, concentración alta.")

    if data["reglas"]["estado_riesgo"] == "EXCEDIDO":
        alertas.append(f"  🚨 Riesgo total {data['riesgo_pct_portfolio']}% supera el límite de 6%. Reducir exposición.")

    if not alertas:
        alertas.append("  ✓ Sin alertas críticas.")

    for a in alertas:
        print(a)

    print()
    print("  OPERACIONES CERRADAS JUNIO (P&L realizado)")
    print(linea)
    print(f"  Resultado neto junio: US$ {data['perdidas_realizadas_junio_usd']:,.2f}")
    print()


if __name__ == "__main__":
    print("Cargando cartera...")
    cartera = cargar_cartera()

    tickers = [h["ticker"] for h in cartera.get("holdings", []) if h.get("cantidad", 0) > 0]

    print("Buscando precios en PPI..." if os.getenv("PPI_PRIVATE_KEY") else "Sin PPI configurado, usando precios de entrada.")
    precios = get_precios_ppi(tickers)

    data = analizar(cartera, precios)
    imprimir_reporte(data)

    # Guardar JSON para uso del orchestrator
    output_path = BASE_DIR / "ultimo_calculo.json"
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Datos guardados en: {output_path}")
    print()
