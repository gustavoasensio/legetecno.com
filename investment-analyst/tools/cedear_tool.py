"""
Sub-agente: Especialista en CEDEARs.
Analiza oportunidades en CEDEARs con cobertura de tipo de cambio implícita.
"""
import anthropic
import json
from config import ANALYST_MODEL, CEDEARS_PRINCIPALES
from data.market_data import get_us_stock_price


def analyze_cedears(market_data: dict, capital_disponible_ars: float, perfil_riesgo: str) -> dict:
    """Analiza los mejores CEDEARs para el capital disponible."""
    client = anthropic.Anthropic()

    dolar_ccl = market_data.get("dolar_ccl", 1250)

    print("[CEDEAR] Obteniendo precios de subyacentes en Wall Street...")
    cedears_data = []

    # Analizar los principales CEDEARs
    tickers_a_analizar = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "WMT", "KO"]

    for ticker in tickers_a_analizar:
        if ticker in CEDEARS_PRINCIPALES:
            info_cedear = CEDEARS_PRINCIPALES[ticker]
            stock = get_us_stock_price(info_cedear["subyacente"])

            if stock.get("precio_usd"):
                precio_ars_teorico = stock["precio_usd"] * dolar_ccl / info_cedear["ratio"]
                cedears_data.append({
                    "ticker_cedear": ticker,
                    "subyacente": info_cedear["subyacente"],
                    "nombre": info_cedear["nombre"],
                    "ratio": info_cedear["ratio"],
                    "precio_usd_subyacente": stock["precio_usd"],
                    "precio_ars_teorico": round(precio_ars_teorico, 2),
                    "pe_ratio": stock.get("pe_ratio"),
                    "var_1m_pct": stock.get("var_1m_pct"),
                    "market_cap_b_usd": stock.get("market_cap_b"),
                    "52w_high": stock.get("52w_high"),
                    "52w_low": stock.get("52w_low"),
                    "sector": stock.get("sector"),
                    "dividendo_yield": stock.get("dividendYield"),
                    "dolar_ccl_aplicado": dolar_ccl,
                    "cedears_comprables_con_capital": int(capital_disponible_ars / precio_ars_teorico) if precio_ars_teorico > 0 else 0,
                })

    sin_datos_live = len(cedears_data) == 0
    datos_str = (
        json.dumps(cedears_data, indent=2, ensure_ascii=False)
        if cedears_data
        else "⚠ Datos en tiempo real no disponibles (API externa sin acceso). Usa tu conocimiento actualizado del mercado para hacer las recomendaciones."
    )

    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=3000,
        system="""Eres un analista experto en CEDEARs argentinos.
        Los CEDEARs son certificados de depósito argentinos que representan acciones extranjeras.
        Tienen la ventaja de cobertura cambiaria implícita (CCL) y acceso a grandes empresas globales.

        Considera:
        - Valuación actual vs histórica (P/E, 52w range)
        - Momentum y tendencias recientes
        - Diversificación sectorial
        - Liquidez en el mercado local
        - Potencial de apreciación tanto del subyacente como del tipo de cambio
        - Sectores con mejor perspectiva: tech, energía, financiero, consumo

        Cuando no hay datos en tiempo real, basá tus recomendaciones en tu conocimiento del
        mercado pero indicá explícitamente que los precios deben verificarse antes de operar.
        Responde en español con análisis profesional.""",
        messages=[
            {
                "role": "user",
                "content": f"""Analiza estas oportunidades de CEDEARs para un inversor argentino:

DATOS DEL MERCADO:
- Dólar CCL referencia: ${dolar_ccl:,.2f} ARS
- Capital disponible: ${capital_disponible_ars:,.0f} ARS (≈ USD {capital_disponible_ars/dolar_ccl:,.0f})
- Perfil de riesgo del inversor: {perfil_riesgo}
- Datos en tiempo real: {"NO disponibles — usar conocimiento propio" if sin_datos_live else "DISPONIBLES"}

CEDEARS DISPONIBLES CON PRECIOS:
{datos_str}

Proporciona:
1. TOP 5 CEDEARs recomendados con justificación detallada (fundamentos, momentum, valuación)
2. Asignación de capital sugerida en % para cada uno
3. Análisis de riesgo por posición
4. Precio de entrada óptimo y target de salida para cada recomendado
5. CEDEARs a EVITAR actualmente y por qué
6. Estrategia específica de diversificación sectorial
7. Horizonte de inversión recomendado por posición

Responde en formato JSON estructurado con los campos:
- top_5_recomendados: array con análisis detallado de cada uno
- asignacion_capital: porcentajes sugeridos
- estrategia_general: texto con la estrategia
- alertas_riesgo: array de riesgos a monitorear
- cedears_evitar: array con tickers y razones""",
            }
        ],
    )

    analysis_text = resp.content[0].text

    try:
        if "```json" in analysis_text:
            analysis_text = analysis_text.split("```json")[1].split("```")[0].strip()
        analysis = json.loads(analysis_text)
    except Exception:
        analysis = {"analisis_texto": analysis_text}

    return {
        "cedears_analizados": cedears_data,
        "recomendaciones": analysis,
        "dolar_ccl": dolar_ccl,
        "capital_analizado_ars": capital_disponible_ars,
    }
