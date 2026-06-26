"""
Screener de CEDEARs con filtros estrictos de riesgo/retorno.
Solo muestra oportunidades con R/R >= 2:1 y stop técnico definido.
"""
import anthropic
import json
from config import ANALYST_MODEL
from tools.risk_manager import VOLATILIDAD_CEDEAR, LIMITES_POR_VOLATILIDAD, calcular_posicion


def screen_cedears_riguroso(
    capital_usd: float,
    dolar_ccl: float,
    objetivo: str = "crecimiento_capital",
    max_posiciones: int = 8,
) -> dict:
    """
    Screener profesional: filtra CEDEARs por calidad de oportunidad.
    Descarta tickers con R/R < 2:1 o sin nivel técnico de stop claro.
    Solo recomienda cuando hay convicción real.
    """
    client = anthropic.Anthropic()

    # Construir perfil de riesgo del portfolio
    riesgo_max_por_op_usd = capital_usd * 0.015
    riesgo_max_total_usd = capital_usd * 0.06  # máximo 6% pérdida total si todos los stops saltan

    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=5000,
        system="""Eres un portfolio manager de primer nivel especializado en CEDEARs argentinos.

        Tus estándares son los de un hedge fund institucional:
        - R/R mínimo 2:1 para ABRIR cualquier posición (si el stop es -8%, el target mínimo es +16%)
        - Solo operás cuando hay catalizador claro (earnings, producto nuevo, macro favorable)
        - Preferís 4 posiciones de alta convicción a 12 posiciones mediocres
        - Sizing correcto: nunca más del 15% en una sola posición para volatilidad baja,
          10% para moderada, 7% para alta, 5% para muy alta
        - Stop-loss basado en soporte técnico, NUNCA arbitrario
        - Considerás la correlación: si ya tenés NVDA no sumás otro chip de IA puro

        Tu rol es DESCARTAR activamente las malas oportunidades.
        Respondés en español con datos precisos.""",
        messages=[
            {
                "role": "user",
                "content": f"""Realizá un screening riguroso de CEDEARs para este inversor.

CONTEXTO DEL INVERSOR:
- Capital total: USD {capital_usd:,.0f}
- Dólar CCL: ${dolar_ccl:,.0f} ARS
- Objetivo: {objetivo}
- Máximo de posiciones simultáneas: {max_posiciones}
- Riesgo máximo por operación: USD {riesgo_max_por_op_usd:,.0f} (1.5% del capital)
- Pérdida máxima aceptable si todos los stops se ejecutan: USD {riesgo_max_total_usd:,.0f} (6%)
- Fecha: junio 2026

UNIVERSO A ANALIZAR:
CEDEARs disponibles en BYMA: AAPL, MSFT, GOOGL, NVDA, META, AMZN, TSLA, JPM, WMT, KO,
BABA, DIS, PFE, GGAL (como acción/CEDEAR), BRKA, XOM (ExxonMobil), BAC, INTC, AMD, PYPL

PROCESO DE SCREENING (aplicar en orden, descartar si no cumple):

FILTRO 1 - FUNDAMENTAL:
¿Tiene catalizador concreto en los próximos 3-6 meses? ¿Los fundamentos son sólidos?
Descartá las que no tienen catalizador claro.

FILTRO 2 - TÉCNICO:
¿Hay un nivel de soporte técnico claro donde poner el stop?
¿Está el precio en zona de acumulación o en máximos (riesgo de comprar el techo)?
Descartá las que están en zona de distribución/techo.

FILTRO 3 - R/R:
Calculá el stop técnico y el target realista.
R/R = (target - entrada) / (entrada - stop)
Descartá todas las que tengan R/R < 2:1.

FILTRO 4 - CORRELACIÓN:
¿El portfolio resultante tiene exposición concentrada en un sector o factor?
Ajustá para que no haya más de 40% en tech puro, 30% en un solo sector.

FILTRO 5 - LIQUIDEZ BYMA:
¿El CEDEAR tiene suficiente liquidez para operar sin impacto de precio?
Descartá los illíquidos para este tamaño de capital.

RESULTADO DEL SCREENING:

Para cada CEDEAR que PASA los filtros, proporcioná:
{{
  "ticker": "MSFT",
  "nombre": "Microsoft Corp.",
  "ratio_cedear": 8,
  "precio_subyacente_usd_estimado": 450,
  "precio_cedear_ars_teorico": 70875,
  "volatilidad_clasificacion": "moderada",
  "filtros_superados": ["fundamental", "tecnico", "rr", "correlacion", "liquidez"],
  "catalizador_principal": "...",
  "stop_loss_tecnico_usd": 420,
  "stop_loss_pct": "-6.7%",
  "target_12m_usd": 520,
  "target_pct": "+15.6%",
  "rr_ratio": 2.3,
  "conviction_score": 8.5,  // 1-10
  "sizing_sugerido_pct_portfolio": 12,
  "sizing_usd": 2376,
  "tesis_corta": "..."
}}

Para cada CEDEAR RECHAZADO:
{{
  "ticker": "TSLA",
  "filtro_que_fallo": "tecnico",
  "razon_rechazo": "..."
}}

Finalizá con:
- resumen_portfolio_screening: descripción del portafolio resultante
- correlacion_sectorial: análisis de diversificación
- advertencias_riesgo: 3 riesgos sistémicos a monitorear

Formato JSON con:
- cedears_aprobados: array (máximo {max_posiciones})
- cedears_rechazados: array
- resumen_portfolio: objeto
- advertencias_riesgo: array de 3 items""",
            }
        ],
    )

    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()

    try:
        screening = json.loads(text)
    except Exception:
        screening = {"texto": text}

    return {
        "capital_analizado_usd": capital_usd,
        "dolar_ccl": dolar_ccl,
        "screening": screening,
        "parametros_riesgo": {
            "riesgo_max_por_op_usd": round(riesgo_max_por_op_usd, 2),
            "riesgo_max_por_op_pct": "1.5%",
            "perdida_maxima_total_usd": round(riesgo_max_total_usd, 2),
            "perdida_maxima_total_pct": "6%",
            "rr_minimo_exigido": "2:1",
        },
    }
