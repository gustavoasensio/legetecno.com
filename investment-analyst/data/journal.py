"""
Journal de operaciones: registra cada trade con P&L real y comisiones.
Archivo de datos: journal.jsonl (una operación por línea, append-only)
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

JOURNAL_PATH = Path(__file__).parent.parent / "journal.jsonl"
BYMA_COMISION = 0.00726  # 0.6% + 21% IVA por lado


def registrar_operacion(
    ticker: str,
    tipo: str,           # "COMPRA" | "VENTA"
    cantidad: float,
    precio_usd: float,
    dolar_mep: float,
    notas: str = "",
) -> dict:
    """
    Registra una operación en el journal.
    Calcula comisión automáticamente.
    """
    monto_usd = cantidad * precio_usd
    monto_ars = monto_usd * dolar_mep
    comision_usd = monto_usd * BYMA_COMISION

    op = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{ticker}",
        "fecha": datetime.now().isoformat(),
        "ticker": ticker,
        "tipo": tipo.upper(),
        "cantidad": cantidad,
        "precio_usd": precio_usd,
        "monto_usd": round(monto_usd, 2),
        "monto_ars": round(monto_ars, 0),
        "dolar_mep": dolar_mep,
        "comision_usd": round(comision_usd, 2),
        "notas": notas,
    }

    with open(JOURNAL_PATH, "a") as f:
        f.write(json.dumps(op, ensure_ascii=False) + "\n")

    return op


def cargar_journal() -> list:
    """Carga todas las operaciones del journal."""
    if not JOURNAL_PATH.exists():
        return []
    ops = []
    with open(JOURNAL_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    ops.append(json.loads(line))
                except Exception:
                    pass
    return ops


def calcular_pnl_por_ticker(ticker: str) -> dict:
    """
    Calcula el P&L real para un ticker específico usando FIFO.
    """
    ops = [o for o in cargar_journal() if o["ticker"] == ticker]
    compras = []  # cola FIFO de lotes
    ventas = []
    pnl_realizado = 0.0
    comisiones_totales = 0.0

    for op in sorted(ops, key=lambda x: x["fecha"]):
        comisiones_totales += op.get("comision_usd", 0)

        if op["tipo"] == "COMPRA":
            compras.append({
                "cantidad": op["cantidad"],
                "precio": op["precio_usd"],
                "fecha": op["fecha"],
            })

        elif op["tipo"] == "VENTA":
            cantidad_vender = op["cantidad"]
            precio_venta = op["precio_usd"]

            while cantidad_vender > 0 and compras:
                lote = compras[0]
                if lote["cantidad"] <= cantidad_vender:
                    # Consumir lote completo
                    pnl_realizado += lote["cantidad"] * (precio_venta - lote["precio"])
                    cantidad_vender -= lote["cantidad"]
                    compras.pop(0)
                else:
                    # Consumir parcialmente
                    pnl_realizado += cantidad_vender * (precio_venta - lote["precio"])
                    lote["cantidad"] -= cantidad_vender
                    cantidad_vender = 0

            ventas.append(op)

    # Posición abierta restante
    cantidad_abierta = sum(l["cantidad"] for l in compras)
    precio_prom = (
        sum(l["cantidad"] * l["precio"] for l in compras) / cantidad_abierta
        if cantidad_abierta > 0 else 0
    )

    return {
        "ticker": ticker,
        "pnl_realizado_usd": round(pnl_realizado, 2),
        "comisiones_totales_usd": round(comisiones_totales, 2),
        "pnl_neto_usd": round(pnl_realizado - comisiones_totales, 2),
        "cantidad_operaciones": len(ops),
        "posicion_abierta_cantidad": round(cantidad_abierta, 0),
        "precio_promedio_abierto": round(precio_prom, 4),
    }


def resumen_total() -> dict:
    """P&L total del portfolio, todas las operaciones."""
    ops = cargar_journal()
    if not ops:
        return {"mensaje": "Journal vacío. Registrá tus operaciones con registrar_operacion()"}

    tickers = list({o["ticker"] for o in ops})
    resultados = [calcular_pnl_por_ticker(t) for t in tickers]

    pnl_total = sum(r["pnl_realizado_usd"] for r in resultados)
    comisiones_total = sum(r["comisiones_totales_usd"] for r in resultados)
    total_ops = len(ops)

    return {
        "fecha": datetime.now().isoformat(),
        "total_operaciones": total_ops,
        "pnl_realizado_usd": round(pnl_total, 2),
        "comisiones_totales_usd": round(comisiones_total, 2),
        "pnl_neto_usd": round(pnl_total - comisiones_total, 2),
        "por_ticker": resultados,
    }


def importar_historial_junio():
    """
    Carga el historial de junio 2026 que analizamos de los screenshots de PPI.
    Ejecutar una sola vez para inicializar el journal.
    """
    operaciones_historicas = [
        # Posición original INTC (abril)
        {"ticker": "INTC", "tipo": "COMPRA", "cantidad": 221, "precio_usd": 33.56, "dolar_mep": 1280, "notas": "Compra original abril 2026 @ AR$42,291 / CCL $1,260"},
        # Ventas semana del 8-11 junio
        {"ticker": "GOOGL", "tipo": "VENTA", "cantidad": 364, "precio_usd": 6.45, "dolar_mep": 1480, "notas": "Salida posición existente"},
        {"ticker": "NVDA", "tipo": "VENTA", "cantidad": 384, "precio_usd": 8.82, "dolar_mep": 1480, "notas": "Salida posición existente"},
        {"ticker": "INTC", "tipo": "VENTA", "cantidad": 34, "precio_usd": 24.71, "dolar_mep": 1490, "notas": "Venta parcial INTC @ AR$31,140"},
        {"ticker": "SPY", "tipo": "VENTA", "cantidad": 786, "precio_usd": 12.50, "dolar_mep": 1490, "notas": "Liquidación posición SPY"},
        {"ticker": "TSM", "tipo": "VENTA", "cantidad": 24, "precio_usd": 47.02, "dolar_mep": 1490, "notas": ""},
        {"ticker": "QQQ", "tipo": "VENTA", "cantidad": 38, "precio_usd": 36.13, "dolar_mep": 1490, "notas": ""},
        # Reingreso semana del 19 junio (el error)
        {"ticker": "NVDA", "tipo": "COMPRA", "cantidad": 106, "precio_usd": 9.20, "dolar_mep": 1495, "notas": "REINGRESO más caro — error FOMO"},
        {"ticker": "SPY", "tipo": "COMPRA", "cantidad": 379, "precio_usd": 13.04, "dolar_mep": 1495, "notas": "REINGRESO más caro — error FOMO"},
        {"ticker": "GOOGL", "tipo": "COMPRA", "cantidad": 149, "precio_usd": 6.58, "dolar_mep": 1495, "notas": "REINGRESO más caro — error FOMO"},
        {"ticker": "MELI", "tipo": "COMPRA", "cantidad": 69, "precio_usd": 14.09, "dolar_mep": 1499, "notas": "Nueva posición"},
        {"ticker": "SPCE", "tipo": "COMPRA", "cantidad": 60, "precio_usd": 7.89, "dolar_mep": 1499, "notas": "Especulativa — alta volatilidad"},
        {"ticker": "INTC", "tipo": "COMPRA", "cantidad": 221, "precio_usd": 26.90, "dolar_mep": 1499, "notas": "Promediando INTC — error"},
        # Ventas semana del 24-25 junio (capitulación)
        {"ticker": "SPCE", "tipo": "VENTA", "cantidad": 60, "precio_usd": 7.00, "dolar_mep": 1499, "notas": "Salida con pérdida"},
        {"ticker": "NVDA", "tipo": "VENTA", "cantidad": 106, "precio_usd": 8.40, "dolar_mep": 1499, "notas": "Vendido más barato que recompra"},
        {"ticker": "SPY", "tipo": "VENTA", "cantidad": 379, "precio_usd": 12.59, "dolar_mep": 1499, "notas": "Vendido más barato que recompra"},
        {"ticker": "INTC", "tipo": "VENTA", "cantidad": 221, "precio_usd": 26.90, "dolar_mep": 1499, "notas": "Salida INTC"},
        {"ticker": "GOOGL", "tipo": "VENTA", "cantidad": 149, "precio_usd": 6.05, "dolar_mep": 1499, "notas": "Vendido más barato que recompra"},
        # Posiciones actuales abiertas
        {"ticker": "MRVL", "tipo": "COMPRA", "cantidad": 24, "precio_usd": 20.34, "dolar_mep": 1499, "notas": "Nueva posición — con stop en $18.30"},
    ]

    if JOURNAL_PATH.exists():
        print(f"Journal ya existe en {JOURNAL_PATH}. Saltando importación.")
        return

    for op in operaciones_historicas:
        registrar_operacion(**op)

    print(f"✓ Importadas {len(operaciones_historicas)} operaciones en {JOURNAL_PATH}")


if __name__ == "__main__":
    import sys

    if "--importar" in sys.argv:
        importar_historial_junio()
    else:
        resumen = resumen_total()
        print(json.dumps(resumen, indent=2, ensure_ascii=False))
