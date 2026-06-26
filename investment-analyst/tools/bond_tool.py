"""
Sub-agente: Analista de Bonos Argentinos.
Especializado en deuda soberana, ON corporativas y letras del Tesoro.
"""
import anthropic
import json
from config import ANALYST_MODEL, BONOS_PRINCIPALES


def analyze_bonos(market_data: dict, capital_disponible_ars: float, perfil_riesgo: str) -> dict:
    """Analiza oportunidades en bonos soberanos y corporativos argentinos."""
    client = anthropic.Anthropic()

    dolar_ccl = market_data.get("dolar_ccl", 1250)
    bonos_precios = market_data.get("bonos", {})
    macroeconomia = market_data.get("macroeconomia", {})
    inflacion = macroeconomia.get("inflacion", {})
    tasa_pm = macroeconomia.get("tasa_politica_monetaria", {})
    reservas = macroeconomia.get("reservas", {})

    # Combinar precios del mercado con info estática
    bonos_completos = []
    for ticker, info_estatica in BONOS_PRINCIPALES.items():
        precio_mercado = bonos_precios.get(ticker, {})
        bonos_completos.append({
            "ticker": ticker,
            "descripcion": info_estatica["descripcion"],
            "moneda": info_estatica["moneda"],
            "ley": info_estatica.get("ley"),
            "ajuste": info_estatica.get("ajuste"),
            "precio_usd": precio_mercado.get("precio") if info_estatica["moneda"] == "USD" else None,
            "precio_ars": precio_mercado.get("precio") if info_estatica["moneda"] == "ARS" else None,
            "variacion_pct": precio_mercado.get("variacion_pct"),
            "capital_comprable_ars": capital_disponible_ars,
            "lotes_de_100_comprables": int(capital_disponible_ars / (precio_mercado.get("precio", 100) * dolar_ccl / 100))
            if precio_mercado.get("precio") and info_estatica["moneda"] == "USD"
            else None,
        })

    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=3000,
        system="""Eres un analista de renta fija especializado en deuda soberana argentina y obligaciones negociables.

        Conoces en profundidad:
        - Curva de rendimientos soberanos AR (GD y AL series): paridad, TIR, duración
        - Diferencia entre bonos ley Argentina vs ley Nueva York (riesgo de restructuración)
        - Instrumentos CER: DICP, TX, protección contra inflación
        - Instrumentos dólar-linked: DLK, cobertura cambiaria
        - Letras del Tesoro: rendimiento implícito, descuento
        - ONs corporativas investment grade: YPF, Arcor, Pampa, etc.
        - Riesgo país (EMBI+) y su impacto en precios
        - Estrategias: carry trade, dolarización del portafolio, cobertura inflación

        Responde en español con análisis técnico profesional.""",
        messages=[
            {
                "role": "user",
                "content": f"""Analiza el mercado de renta fija argentina para maximizar rendimientos:

CONTEXTO MACROECONÓMICO ACTUAL:
- Dólar CCL: ${dolar_ccl:,.2f} ARS
- Inflación mensual: {inflacion.get('inflacion_mensual_pct', 'N/A')}%
- Tasa política monetaria BCRA: {tasa_pm.get('tasa_pct_anual', 'N/A')}% anual
- Reservas internacionales: ${reservas.get('reservas_millones_usd', 'N/A')} millones USD
- Capital total disponible: ${capital_disponible_ars:,.0f} ARS (≈ USD {capital_disponible_ars/dolar_ccl:,.0f})

BONOS DISPONIBLES:
{json.dumps(bonos_completos, indent=2, ensure_ascii=False)}

PERFIL DEL INVERSOR: {perfil_riesgo}

Analiza y recomienda:
1. ESTRATEGIA MACRO: ¿conviene más dolarizar (bonos USD) o buscar rendimiento en ARS ajustado? Justifica.

2. TOP 3 BONOS SOBERANOS recomendados:
   - TIR estimada actual
   - Paridad y upside si Argentina mejora rating
   - Riesgo de restructuración (ley NY vs ley AR)
   - Horizonte óptimo de tenencia
   - Precio de entrada sugerido

3. INSTRUMENTOS DE COBERTURA INFLACIÓN (CER):
   - ¿Vale la pena vs inflación esperada?
   - Cuáles y por qué

4. LETRAS DEL TESORO:
   - TNA implícita vs inflación y dólar
   - ¿Son competitivas ahora?

5. ONs CORPORATIVAS para considerar (si aplica con capital disponible)

6. ASIGNACIÓN DE CAPITAL en renta fija:
   - % en USD-denominados
   - % en CER
   - % en tasa fija pesos
   - % en Letras corto plazo

7. Riesgos críticos a monitorear

Formato JSON con:
- estrategia_macro: texto con recomendación estratégica
- top_3_bonos_soberanos: array detallado
- cobertura_inflacion: análisis CER
- letras_tesoro: análisis
- asignacion_capital: porcentajes
- riesgos_principales: array""",
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
        "bonos_analizados": bonos_completos,
        "recomendaciones": analysis,
        "capital_analizado_ars": capital_disponible_ars,
        "dolar_ccl": dolar_ccl,
    }
