"""
Sub-agente: Analizador de Cartera.
Evalúa la composición actual, concentración y performance de la cartera.
"""
import anthropic
import json
from config import ANALYST_MODEL


def analyze_portfolio(portfolio: dict, market_data: dict) -> dict:
    """
    Analiza la cartera actual del usuario.

    portfolio = {
        "cash_ars": float,           # pesos disponibles
        "cash_usd": float,           # dólares disponibles
        "ingreso_mensual_ars": float, # ingreso para invertir
        "holdings": [
            {
                "tipo": "cedear|accion|bono|plazo_fijo|fci",
                "ticker": str,
                "cantidad": float,
                "precio_compra": float,
                "moneda_compra": "ARS|USD",
                "fecha_compra": str (opcional)
            }
        ]
    }
    """
    client = anthropic.Anthropic()

    dolar_ccl = market_data.get("dolar_ccl", 1250)
    acciones = market_data.get("acciones_merval", {})
    bonos = market_data.get("bonos", {})

    # Valorizar la cartera actual
    holdings_valorados = []
    total_ars = portfolio.get("cash_ars", 0)

    for holding in portfolio.get("holdings", []):
        tipo = holding.get("tipo", "")
        ticker = holding.get("ticker", "")
        cantidad = holding.get("cantidad", 0)
        precio_compra = holding.get("precio_compra", 0)
        moneda = holding.get("moneda_compra", "ARS")

        precio_actual = None
        if tipo == "accion" and ticker in acciones:
            precio_actual = acciones[ticker].get("precio")
        elif tipo == "bono" and ticker in bonos:
            precio_actual = bonos[ticker].get("precio")
        elif tipo == "cedear":
            precio_actual = holding.get("precio_actual_ars")

        valor_compra_ars = cantidad * precio_compra
        if moneda == "USD":
            valor_compra_ars *= dolar_ccl

        valor_actual_ars = None
        ganancia_pct = None
        if precio_actual:
            valor_actual_ars = cantidad * precio_actual
            moneda_actual = acciones.get(ticker, {}).get("moneda", "ARS") if tipo == "accion" else "ARS"
            if moneda_actual == "USD":
                valor_actual_ars *= dolar_ccl
            if valor_compra_ars > 0:
                ganancia_pct = ((valor_actual_ars - valor_compra_ars) / valor_compra_ars) * 100

        h = {
            **holding,
            "precio_actual": precio_actual,
            "valor_compra_ars": round(valor_compra_ars, 2),
            "valor_actual_ars": round(valor_actual_ars, 2) if valor_actual_ars else None,
            "ganancia_pct": round(ganancia_pct, 2) if ganancia_pct else None,
        }
        holdings_valorados.append(h)

        if valor_actual_ars:
            total_ars += valor_actual_ars
        elif valor_compra_ars:
            total_ars += valor_compra_ars

    total_ars += portfolio.get("cash_usd", 0) * dolar_ccl

    portfolio_summary = {
        "total_valorizado_ars": round(total_ars, 2),
        "total_valorizado_usd": round(total_ars / dolar_ccl, 2),
        "cash_ars": portfolio.get("cash_ars", 0),
        "cash_usd": portfolio.get("cash_usd", 0),
        "ingreso_mensual_ars": portfolio.get("ingreso_mensual_ars", 0),
        "holdings": holdings_valorados,
        "dolar_ccl_usado": dolar_ccl,
    }

    # Claude analiza la composición
    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=2000,
        system="""Eres un analista de portfolio argentino experto.
        Analiza la composición de la cartera, identifica concentración de riesgo,
        diversificación, correlaciones y proporciona métricas clave.
        Sé conciso pero preciso. Responde en español.""",
        messages=[
            {
                "role": "user",
                "content": f"""Analiza esta cartera de inversión argentina:

DATOS DE LA CARTERA:
{json.dumps(portfolio_summary, indent=2, ensure_ascii=False)}

CONTEXTO MACRO:
- Dólar CCL: ${dolar_ccl}
- Inflación mensual: {market_data.get('macroeconomia', {}).get('inflacion', {}).get('inflacion_mensual_pct')}%
- Tasa política monetaria: {market_data.get('macroeconomia', {}).get('tasa_politica_monetaria', {}).get('tasa_pct_anual')}% anual

Proporciona:
1. Resumen de composición por tipo de activo y porcentajes
2. Análisis de diversificación y concentración de riesgo
3. Performance actual de las posiciones con precio conocido
4. Liquidez disponible (ARS y USD equivalente)
5. Puntos críticos que necesitan atención
6. Score general de la cartera (1-10) con justificación

Formato de respuesta: JSON estructurado.""",
            }
        ],
    )

    analysis_text = resp.content[0].text

    # Intentar parsear como JSON, sino devolver como texto
    try:
        if "```json" in analysis_text:
            analysis_text = analysis_text.split("```json")[1].split("```")[0].strip()
        analysis = json.loads(analysis_text)
    except Exception:
        analysis = {"analisis_texto": analysis_text}

    return {
        "portfolio_valorado": portfolio_summary,
        "analisis": analysis,
    }
