"""
Sub-agente: Generador de Reporte Final.
Sintetiza todos los análisis en un plan de acción concreto y priorizado.
"""
import anthropic
import json
from datetime import datetime
from config import ANALYST_MODEL


def generate_final_report(
    portfolio: dict,
    portfolio_analysis: dict,
    risk_assessment: dict,
    cedear_analysis: dict,
    acciones_analysis: dict,
    bond_analysis: dict,
    market_data: dict,
) -> dict:
    """Genera el reporte final integrado con plan de acción específico."""
    client = anthropic.Anthropic()

    dolar_ccl = market_data.get("dolar_ccl", 1250)
    perfil_riesgo = risk_assessment.get("evaluacion_riesgo", {}).get("perfil_riesgo", "moderado")
    total_ars = risk_assessment.get("patrimonio_ars", 0)
    ingreso_mensual = portfolio.get("ingreso_mensual_ars", 0)
    capital_para_invertir = portfolio.get("cash_ars", 0) + portfolio.get("cash_usd", 0) * dolar_ccl

    # Extraer las mejores recomendaciones de cada sub-agente
    top_cedears = cedear_analysis.get("recomendaciones", {})
    top_acciones = acciones_analysis.get("recomendaciones", {})
    top_bonos = bond_analysis.get("recomendaciones", {})
    asset_allocation = risk_assessment.get("evaluacion_riesgo", {}).get("asset_allocation_optimo", {})

    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=4000,
        system="""Eres el Director de Inversiones de una firma financiera argentina de primer nivel.
        Tu rol es integrar los análisis especializados y generar un plan de acción concreto,
        priorizado y ejecutable para el cliente.

        Eres directo, específico con números y fechas, y optimizas para MAXIMIZAR RETORNOS
        dentro del perfil de riesgo del cliente.

        NO uses lenguaje vago. Cada recomendación debe tener:
        - Ticker específico
        - Monto exacto en ARS
        - Precio máximo de entrada
        - Target de precio o rendimiento objetivo
        - Plazo específico

        Responde en español.""",
        messages=[
            {
                "role": "user",
                "content": f"""Como Director de Inversiones, integra todos los análisis y genera el PLAN DE ACCIÓN FINAL.

RESUMEN EJECUTIVO DEL CLIENTE:
- Patrimonio total: ${total_ars:,.0f} ARS (≈ USD {total_ars/dolar_ccl:,.0f})
- Capital disponible para invertir HOY: ${capital_para_invertir:,.0f} ARS
- Ingreso mensual para invertir: ${ingreso_mensual:,.0f} ARS
- Dólar CCL: ${dolar_ccl:,.2f}
- Perfil de riesgo: {perfil_riesgo}
- Fecha: {datetime.now().strftime('%d/%m/%Y')}

ASSET ALLOCATION ÓPTIMO DETERMINADO:
{json.dumps(asset_allocation, indent=2, ensure_ascii=False)}

MEJORES RECOMENDACIONES CEDEARs:
{json.dumps(top_cedears.get('top_5_recomendados', top_cedears.get('analisis_texto', 'N/A')), indent=2, ensure_ascii=False)}

MEJORES RECOMENDACIONES ACCIONES AR:
{json.dumps(top_acciones.get('top_4_recomendadas', top_acciones.get('analisis_texto', 'N/A')), indent=2, ensure_ascii=False)}

MEJORES RECOMENDACIONES BONOS:
{json.dumps(top_bonos.get('top_3_bonos_soberanos', top_bonos.get('analisis_texto', 'N/A')), indent=2, ensure_ascii=False)}

ANÁLISIS DE CARTERA ACTUAL:
{json.dumps(portfolio_analysis.get('analisis', {}), indent=2, ensure_ascii=False)}

Genera el PLAN DE ACCIÓN DEFINITIVO:

1. RESUMEN EJECUTIVO (3-4 líneas): situación actual y oportunidad

2. OPERACIONES INMEDIATAS (Esta semana):
   Lista ordenada por prioridad, cada una con:
   - Acción: COMPRAR/VENDER/MANTENER
   - Ticker y nombre
   - Cantidad en unidades
   - Monto en ARS
   - Precio máximo de entrada
   - Justificación (1 línea)

3. DISTRIBUCIÓN EXACTA del capital disponible (${capital_para_invertir:,.0f} ARS):
   Tabla con: ticker, monto ARS, %, objetivo

4. PLAN DE INVERSIÓN MENSUAL (${ingreso_mensual:,.0f} ARS/mes):
   Cómo invertirlo de forma sistemática

5. POSICIONES A AJUSTAR en la cartera existente:
   ¿Hay algo que vender/reducir para rebalancear?

6. OBJETIVOS DE RENDIMIENTO:
   - Rendimiento esperado anual en USD
   - Rendimiento esperado anual en ARS (vs inflación)
   - Escenario base, optimista y pesimista

7. ALERTAS DE SEGUIMIENTO:
   5 indicadores clave a monitorear con frecuencia y umbrales de acción

8. PRÓXIMA REVISIÓN: cuándo y qué revisar

Formato: JSON estructurado y COMPLETO.
Campos principales:
- resumen_ejecutivo: string
- operaciones_inmediatas: array de objetos con todos los campos
- distribucion_capital: array detallada
- plan_mensual: objeto con descripción y distribución
- ajustes_cartera_actual: array
- objetivos_rendimiento: objeto con escenarios
- alertas_seguimiento: array
- proxima_revision: objeto con fecha y agenda""",
            }
        ],
    )

    analysis_text = resp.content[0].text

    try:
        if "```json" in analysis_text:
            analysis_text = analysis_text.split("```json")[1].split("```")[0].strip()
        report = json.loads(analysis_text)
    except Exception:
        report = {"reporte_texto": analysis_text}

    return {
        "reporte_final": report,
        "metadata": {
            "fecha_generacion": datetime.now().isoformat(),
            "dolar_ccl": dolar_ccl,
            "patrimonio_total_ars": total_ars,
            "capital_a_invertir_ars": capital_para_invertir,
            "perfil_riesgo": str(perfil_riesgo),
        },
    }
