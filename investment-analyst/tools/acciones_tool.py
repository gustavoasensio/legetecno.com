"""
Sub-agente: Analista de Acciones Argentinas.
Especializado en acciones del panel Merval/BYMA.
"""
import anthropic
import json
from config import ANALYST_MODEL


def analyze_acciones_argentinas(market_data: dict, capital_disponible_ars: float, perfil_riesgo: str) -> dict:
    """Analiza oportunidades en acciones argentinas del Merval."""
    client = anthropic.Anthropic()

    dolar_ccl = market_data.get("dolar_ccl", 1250)
    acciones = market_data.get("acciones_merval", {})
    macroeconomia = market_data.get("macroeconomia", {})
    inflacion = macroeconomia.get("inflacion", {})
    tasa_pm = macroeconomia.get("tasa_politica_monetaria", {})
    reservas = macroeconomia.get("reservas", {})

    # Enriquecer datos de acciones
    acciones_enriquecidas = []
    for simbolo, data in acciones.items():
        if data.get("precio"):
            precio_en_ars = data["precio"]
            precio_en_usd = None

            if data.get("moneda") == "USD":
                precio_en_usd = data["precio"]
                precio_en_ars = data["precio"] * dolar_ccl
            else:
                precio_en_usd = data["precio"] / dolar_ccl

            acciones_enriquecidas.append({
                "ticker": simbolo,
                "nombre": data.get("nombre", simbolo),
                "precio_ars": round(precio_en_ars, 2),
                "precio_usd": round(precio_en_usd, 4) if precio_en_usd else None,
                "var_1m_pct": data.get("var_1m_pct"),
                "pe_ratio": data.get("pe_ratio"),
                "52w_high": data.get("52w_high"),
                "52w_low": data.get("52w_low"),
                "cotiza_en": data.get("moneda", "ARS"),
                "unidades_comprables": int(capital_disponible_ars / precio_en_ars) if precio_en_ars > 0 else 0,
            })

    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=3000,
        system="""Eres un analista bursátil especializado en el mercado de capitales argentino (BYMA/Merval).

        Conoces en profundidad:
        - Sectores dominantes: Energía (YPF, Pampa), Financiero (GGAL, BMA, SUPV), Materiales (LOMA, TXAR, ALUA), Utilities
        - Impacto de macro argentina: dólar, inflación, riesgo país, cepo, regulaciones
        - Correlación con precios de commodities (petróleo, soja, aluminio)
        - ADRs en NYSE vs acciones locales: paridad y oportunidades de arbitraje
        - Ciclo económico argentino y sus impactos sectoriales

        Responde en español con análisis profesional y objetivo.""",
        messages=[
            {
                "role": "user",
                "content": f"""Analiza el mercado de acciones argentinas para recomendar posiciones:

CONTEXTO MACROECONÓMICO:
- Dólar CCL: ${dolar_ccl:,.2f} ARS
- Inflación mensual: {inflacion.get('inflacion_mensual_pct', 'N/A')}%
- Tasa política monetaria: {tasa_pm.get('tasa_pct_anual', 'N/A')}% anual
- Reservas internacionales: ${reservas.get('reservas_millones_usd', 'N/A')} millones USD
- Capital a invertir: ${capital_disponible_ars:,.0f} ARS

ACCIONES DISPONIBLES CON DATOS ACTUALES:
{json.dumps(acciones_enriquecidas, indent=2, ensure_ascii=False)}

PERFIL DEL INVERSOR: {perfil_riesgo}

Proporciona análisis completo:
1. Evaluación del momento actual del mercado argentino (alcista/bajista/lateral + por qué)
2. TOP 4 acciones recomendadas con:
   - Tesis de inversión (3-4 puntos específicos)
   - Catalizadores positivos en los próximos 3-6 meses
   - Riesgos principales
   - Precio objetivo en ARS y USD
   - Stop loss sugerido
3. Sectores con mayor potencial ahora y por qué
4. Acciones a EVITAR con justificación
5. Asignación de capital recomendada en %
6. Horizonte temporal sugerido para cada posición

Formato JSON con los campos:
- contexto_mercado: evaluación macro
- top_4_recomendadas: array detallado
- sectores_favorables: array
- acciones_evitar: array
- asignacion_capital: objeto con %
- estrategia_general: texto""",
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
        "acciones_analizadas": acciones_enriquecidas,
        "recomendaciones": analysis,
        "capital_analizado_ars": capital_disponible_ars,
    }
