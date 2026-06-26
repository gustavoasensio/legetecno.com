"""
Gestor de Riesgo Estricto.
Calcula sizing exacto de posiciones, stop-loss obligatorio y R/R para cada operación.
Regla base: nunca arriesgar más del 1.5% del capital total en una sola operación.
"""
import anthropic
import json
from config import ANALYST_MODEL


# Volatilidad histórica estimada por ticker (daily ATR aproximado como % del precio)
# Fuente: conocimiento de mercado. Se usa para calcular stop-loss dinámico.
VOLATILIDAD_CEDEAR = {
    "NVDA":  {"atr_pct": 3.5, "beta": 1.9, "clasificacion": "alta"},
    "TSLA":  {"atr_pct": 4.5, "beta": 2.2, "clasificacion": "muy_alta"},
    "META":  {"atr_pct": 2.8, "beta": 1.5, "clasificacion": "alta"},
    "AMZN":  {"atr_pct": 2.2, "beta": 1.3, "clasificacion": "moderada-alta"},
    "GOOGL": {"atr_pct": 1.8, "beta": 1.1, "clasificacion": "moderada"},
    "MSFT":  {"atr_pct": 1.6, "beta": 0.9, "clasificacion": "moderada"},
    "AAPL":  {"atr_pct": 1.5, "beta": 0.85, "clasificacion": "moderada"},
    "BABA":  {"atr_pct": 3.8, "beta": 1.8, "clasificacion": "alta"},
    "JPM":   {"atr_pct": 1.4, "beta": 1.1, "clasificacion": "moderada"},
    "WMT":   {"atr_pct": 1.0, "beta": 0.7, "clasificacion": "baja"},
    "KO":    {"atr_pct": 0.9, "beta": 0.6, "clasificacion": "baja"},
    "DIS":   {"atr_pct": 1.8, "beta": 1.1, "clasificacion": "moderada"},
    "PFE":   {"atr_pct": 1.3, "beta": 0.7, "clasificacion": "moderada"},
}

# Límites por clasificación de volatilidad
LIMITES_POR_VOLATILIDAD = {
    "baja":          {"max_pct_portfolio": 0.15, "stop_loss_pct": 0.05, "atr_multiplicador": 2.0},
    "moderada":      {"max_pct_portfolio": 0.12, "stop_loss_pct": 0.07, "atr_multiplicador": 2.5},
    "moderada-alta": {"max_pct_portfolio": 0.10, "stop_loss_pct": 0.09, "atr_multiplicador": 2.5},
    "alta":          {"max_pct_portfolio": 0.07, "stop_loss_pct": 0.12, "atr_multiplicador": 3.0},
    "muy_alta":      {"max_pct_portfolio": 0.05, "stop_loss_pct": 0.15, "atr_multiplicador": 3.0},
}


def calcular_posicion(
    ticker: str,
    precio_entrada_usd: float,
    capital_total_usd: float,
    riesgo_max_por_operacion_pct: float = 0.015,  # 1.5% del capital
) -> dict:
    """
    Calcula el tamaño exacto de la posición usando el modelo de riesgo fijo.

    Fórmula:
        tamaño_posicion = (capital * riesgo_max) / (precio_entrada * stop_loss_pct)

    Esto garantiza que si el stop-loss se ejecuta, la pérdida máxima sea exactamente
    riesgo_max_por_operacion_pct del capital total.
    """
    vol = VOLATILIDAD_CEDEAR.get(ticker, {"atr_pct": 2.0, "beta": 1.2, "clasificacion": "moderada"})
    clasificacion = vol["clasificacion"]
    limites = LIMITES_POR_VOLATILIDAD.get(clasificacion, LIMITES_POR_VOLATILIDAD["moderada"])

    stop_loss_pct = limites["stop_loss_pct"]
    max_pct_portfolio = limites["max_pct_portfolio"]

    # Kelly-ajustado: tamaño por riesgo fijo
    perdida_max_usd = capital_total_usd * riesgo_max_por_operacion_pct
    acciones_por_riesgo = perdida_max_usd / (precio_entrada_usd * stop_loss_pct)

    # Aplicar límite de concentración
    capital_max_posicion = capital_total_usd * max_pct_portfolio
    acciones_por_concentracion = capital_max_posicion / precio_entrada_usd

    # Usar el menor (más conservador)
    acciones_final = min(acciones_por_riesgo, acciones_por_concentracion)
    capital_asignado = acciones_final * precio_entrada_usd

    precio_stop_loss = precio_entrada_usd * (1 - stop_loss_pct)
    perdida_si_stop = acciones_final * (precio_entrada_usd - precio_stop_loss)

    # R/R mínimo 2:1 → target mínimo
    target_minimo_rr2 = precio_entrada_usd * (1 + stop_loss_pct * 2)
    target_conservador = precio_entrada_usd * (1 + stop_loss_pct * 2.5)

    return {
        "ticker": ticker,
        "clasificacion_volatilidad": clasificacion,
        "precio_entrada_usd": round(precio_entrada_usd, 2),
        "acciones_a_comprar": round(acciones_final, 0),
        "capital_asignado_usd": round(capital_asignado, 2),
        "pct_del_portfolio": round(capital_asignado / capital_total_usd * 100, 1),
        "stop_loss": {
            "precio_usd": round(precio_stop_loss, 2),
            "porcentaje": f"-{stop_loss_pct*100:.0f}%",
            "perdida_max_usd": round(perdida_si_stop, 2),
            "perdida_pct_portfolio": round(perdida_si_stop / capital_total_usd * 100, 2),
        },
        "targets": {
            "target_minimo_rr2_usd": round(target_minimo_rr2, 2),
            "ganancia_si_rr2_usd": round(acciones_final * (target_minimo_rr2 - precio_entrada_usd), 2),
            "target_conservador_usd": round(target_conservador, 2),
        },
        "rr_ratio": "2:1 mínimo",
        "regla_aplicada": f"Máx {max_pct_portfolio*100:.0f}% del portfolio en activos de volatilidad {clasificacion}",
    }


def calcular_portfolio_optimo(
    capital_total_usd: float,
    tickers_seleccionados: list,
    precios_usd: dict,
) -> dict:
    """
    Calcula el portafolio óptimo completo con sizing y stops para cada posición.
    """
    posiciones = []
    capital_invertido = 0
    perdida_maxima_total = 0

    for ticker in tickers_seleccionados:
        precio = precios_usd.get(ticker)
        if not precio:
            continue
        pos = calcular_posicion(ticker, precio, capital_total_usd)
        posiciones.append(pos)
        capital_invertido += pos["capital_asignado_usd"]
        perdida_maxima_total += pos["stop_loss"]["perdida_max_usd"]

    cash_reserva = capital_total_usd - capital_invertido

    return {
        "capital_total_usd": capital_total_usd,
        "capital_invertido_usd": round(capital_invertido, 2),
        "cash_reserva_usd": round(cash_reserva, 2),
        "pct_invertido": round(capital_invertido / capital_total_usd * 100, 1),
        "perdida_maxima_si_todo_stop_usd": round(perdida_maxima_total, 2),
        "perdida_maxima_pct_portfolio": round(perdida_maxima_total / capital_total_usd * 100, 2),
        "posiciones": posiciones,
        "cantidad_posiciones": len(posiciones),
    }


def analyze_loss_and_risk(
    capital_actual_usd: float,
    capital_previo_usd: float,
    market_data: dict,
    posiciones_actuales: list = None,
) -> dict:
    """
    Analiza la pérdida reciente e identifica las causas estructurales.
    Proporciona un plan de recuperación con gestión de riesgo estricta.
    """
    client = anthropic.Anthropic()

    perdida_usd = capital_previo_usd - capital_actual_usd
    perdida_pct = (perdida_usd / capital_previo_usd) * 100
    dolar_ccl = market_data.get("dolar_ccl", 1260)
    perdida_ars = perdida_usd * dolar_ccl

    resp = client.messages.create(
        model=ANALYST_MODEL,
        max_tokens=4000,
        system="""Eres un gestor de riesgo de hedge fund con 20 años de experiencia.
        Especializado en mercados emergentes y en particular en el mercado argentino.

        Tu filosofía:
        - La preservación del capital es SIEMPRE la primera prioridad
        - Nunca arriesgar más del 1.5% del capital en una sola operación
        - R/R mínimo de 2:1 para abrir cualquier posición
        - Stop-loss es OBLIGATORIO y nunca se mueve hacia abajo (solo trailing up)
        - La mayor pérdida viene de errores emocionales: FOMO, revenge trading, promediar perdedores
        - Recuperar el 10% de pérdida requiere ganar 11.1% — no es imposible pero requiere disciplina

        Eres directo, sin suavizar nada. Respondés en español.""",
        messages=[
            {
                "role": "user",
                "content": f"""Un inversor argentino perdió USD {perdida_usd:,.0f} en la última semana en CEDEARs.
Esto representa el {perdida_pct:.1f}% de su capital.

SITUACIÓN ACTUAL:
- Capital previo: USD {capital_previo_usd:,.0f}
- Capital actual: USD {capital_actual_usd:,.0f}
- Pérdida: USD {perdida_usd:,.0f} (≈ ARS {perdida_ars:,.0f} al CCL ${dolar_ccl:,.0f})
- Pérdida porcentual: {perdida_pct:.1f}%
- Tipo de activos: CEDEARs en BYMA
- Dólar CCL referencia: ${dolar_ccl:,.0f}

POSICIONES ACTUALES (si las hay): {json.dumps(posiciones_actuales or [], ensure_ascii=False)}

Analizá en detalle:

1. DIAGNÓSTICO DE LA PÉRDIDA:
   - ¿Qué errores estructurales de gestión de riesgo explican una pérdida del {perdida_pct:.1f}% en UNA SEMANA?
   - ¿Cuáles son los 5 errores más comunes que llevan a este resultado en CEDEARs?
   - ¿Qué señales de alerta debería haber visto antes de llegar a esta pérdida?

2. REGLAS DE HIERRO para este inversor desde hoy:
   Lista exactamente 10 reglas no negociables, específicas para alguien con USD {capital_actual_usd:,.0f} en CEDEARs.
   Cada regla con un ejemplo concreto de cómo aplicarla.

3. PLAN DE RECUPERACIÓN:
   - ¿Cuánto tiempo realistamente toma recuperar {perdida_pct:.1f}% con gestión conservadora?
   - ¿Con gestión moderada? ¿Con gestión agresiva (pero correcta)?
   - ¿Cuándo NO abrir posiciones nuevas? (señales de "salir del mercado")

4. ERRORES PSICOLÓGICOS a evitar AHORA:
   El mayor peligro tras una pérdida del {perdida_pct:.1f}% es el "revenge trading".
   Describí los 3 trampas mentales más peligrosas y cómo evitarlas.

5. CARTERA ÓPTIMA CON USD {capital_actual_usd:,.0f}:
   Considerando que ya perdió {perdida_pct:.1f}%, recomendá:
   - Asset allocation entre CEDEARs/bonos/cash
   - Máximo de posiciones simultáneas
   - Sizing máximo por posición en USD
   - Stop-loss obligatorio en % para cada tipo de activo

Formato JSON con:
- diagnostico: objeto con causas y señales de alerta
- reglas_hierro: array de 10 reglas con ejemplos
- plan_recuperacion: objeto con timeframes y condiciones
- errores_psicologicos: array de 3 trampas con soluciones
- cartera_recomendada: objeto con allocation y límites
- accion_inmediata: string con qué hacer LAS PRÓXIMAS 48 HORAS""",
            }
        ],
    )

    text = resp.content[0].text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()

    try:
        analysis = json.loads(text)
    except Exception:
        analysis = {"analisis_texto": text}

    return {
        "perdida_analizada": {
            "capital_previo_usd": capital_previo_usd,
            "capital_actual_usd": capital_actual_usd,
            "perdida_usd": perdida_usd,
            "perdida_pct": round(perdida_pct, 2),
            "perdida_ars": round(perdida_ars, 0),
            "necesario_para_recuperar_pct": round((perdida_usd / capital_actual_usd) * 100, 2),
        },
        "analisis_riesgo": analysis,
    }
