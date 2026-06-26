"""
Sub-agente: Evaluador de Riesgo.
Determina perfil de riesgo y calcula métricas de riesgo del portafolio.
"""
import anthropic
import json
from config import ANALYST_MODEL


def assess_risk(portfolio: dict, portfolio_analysis: dict, market_data: dict) -> dict:
    """
    Evalúa el perfil de riesgo y propone una asignación estratégica óptima.
    """
    client = anthropic.Anthropic()

    dolar_ccl = market_data.get("dolar_ccl", 1250)
    inflacion = market_data.get("macroeconomia", {}).get("inflacion", {})
    tasa_pm = market_data.get("macroeconomia", {}).get("tasa_politica_monetaria", {})

    portfolio_val = portfolio_analysis.get("portfolio_valorado", {})
    total_ars = portfolio_val.get("total_valorizado_ars", 0)
    total_usd = portfolio_val.get("total_valorizado_usd", 0)
    ingreso_mensual = portfolio.get("ingreso_mensual_ars", 0)
    horizonte = portfolio.get("horizonte_inversion", "mediano_plazo")
    objetivo = portfolio.get("objetivo", "crecimiento_capital")

    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=2500,
        system="""Eres un analista de riesgo financiero especializado en el mercado argentino.

        Evalúas:
        - Riesgo sistémico (inflación, devaluación, riesgo país, cepo)
        - Riesgo específico por activo (liquidez, volatilidad, concentración)
        - Métricas de riesgo: VaR, Sharpe, correlaciones
        - Capacidad de absorción de pérdidas del inversor
        - Riesgo de contraparte (broker, custodia)

        Eres objetivo y no suavizas los riesgos.
        Responde en español.""",
        messages=[
            {
                "role": "user",
                "content": f"""Evalúa el perfil de riesgo y la cartera actual:

DATOS DEL INVERSOR:
- Patrimonio total valorado: ${total_ars:,.0f} ARS (≈ USD {total_usd:,.0f})
- Ingreso mensual disponible para invertir: ${ingreso_mensual:,.0f} ARS
- Horizonte de inversión: {horizonte}
- Objetivo declarado: {objetivo}
- Cash actual ARS: ${portfolio.get('cash_ars', 0):,.0f}
- Cash actual USD: ${portfolio.get('cash_usd', 0):,.0f}

CARTERA ANALIZADA:
{json.dumps(portfolio_analysis.get('analisis', {}), indent=2, ensure_ascii=False)}

CONTEXTO DE RIESGO MACRO ARGENTINA:
- Dólar CCL: ${dolar_ccl:,.2f}
- Inflación mensual reciente: {inflacion.get('inflacion_mensual_pct', 'N/A')}%
- Tasa política monetaria: {tasa_pm.get('tasa_pct_anual', 'N/A')}% anual
- Contexto: Argentina en proceso de estabilización macro, cepo cambiario, alta incertidumbre

Proporciona:
1. PERFIL DE RIESGO DETERMINADO: conservador / moderado / agresivo (con justificación basada en datos)

2. RIESGOS ACTUALES DE LA CARTERA:
   - Concentración (sectorial, geográfica, por tipo de activo)
   - Riesgo cambiario (exposición USD vs ARS)
   - Riesgo de liquidez (¿puede salir rápido si necesita?)
   - Riesgo de inflación (¿está protegido?)
   - Riesgo político/regulatorio

3. MÉTRICAS DE RIESGO ESTIMADAS:
   - Correlación entre posiciones actuales
   - Volatilidad estimada del portfolio
   - VaR mensual aproximado (% que podría perder en mes malo)

4. ASIGNACIÓN ESTRATÉGICA ÓPTIMA (Asset Allocation) recomendada:
   Para maximizar Sharpe ratio dado el perfil:
   - % CEDEARs (dolarización + growth)
   - % Acciones argentinas (beta local)
   - % Bonos USD soberanos (carry + dolarización)
   - % Bonos CER (cobertura inflación)
   - % Letras Tesoro (liquidez + rendimiento corto)
   - % Cash USD (reserva)
   - % Cash ARS (operativo)

5. LÍMITES DE POSICIÓN sugeridos:
   - Máximo por activo individual (%)
   - Máximo por sector (%)
   - Mínimo de liquidez a mantener

6. PLAN DE INVERSIÓN DEL INGRESO MENSUAL:
   ¿Cómo invertir los ${ingreso_mensual:,.0f} ARS mensuales de manera óptima?

Formato JSON con:
- perfil_riesgo: string con justificación
- riesgos_cartera_actual: objeto con categorías
- metricas_riesgo: objeto con métricas
- asset_allocation_optimo: porcentajes
- limites_posicion: objeto
- plan_ingreso_mensual: descripción estratégica""",
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
        "evaluacion_riesgo": analysis,
        "patrimonio_ars": total_ars,
        "patrimonio_usd": total_usd,
        "ingreso_mensual_ars": ingreso_mensual,
    }
