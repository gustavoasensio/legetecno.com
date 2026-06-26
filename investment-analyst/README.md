# Analista de Inversiones Argentino — Sistema Multi-Agente

Sistema de análisis de cartera con inteligencia artificial que coordina múltiples sub-agentes especializados para maximizar tus ganancias en el mercado argentino.

## Arquitectura

```
Orquestador (Director de Inversiones)
├── Sub-agente 1: Portfolio Analyzer    → valoriza cartera actual
├── Sub-agente 2: Risk Assessor         → perfil de riesgo + asset allocation
├── Sub-agente 3: CEDEAR Specialist     → mejores CEDEARs (Apple, NVDA, etc.)
├── Sub-agente 4: Acciones AR Analyst   → mejores acciones Merval (YPF, GGAL...)
├── Sub-agente 5: Bond Analyst          → bonos soberanos y CER (GD30, AL30...)
└── Sub-agente 6: Report Generator      → plan de acción concreto y priorizado
```

## Datos en tiempo real

- **Tipo de cambio**: dolarapi.com / bluelytics.com.ar (CCL, MEP, Blue, Oficial)
- **Macro BCRA**: inflación mensual, tasa política monetaria, reservas internacionales
- **Precios Wall Street**: Yahoo Finance (subyacentes de CEDEARs)
- **Acciones argentinas**: ADRs en NYSE vía Yahoo Finance (GGAL, YPF, BMA, PAMP...)
- **Bonos**: Ámbit.com / datos de referencia

## Instalación

```bash
cd investment-analyst
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tu ANTHROPIC_API_KEY
```

## Uso

```bash
# Modo interactivo (recomendado la primera vez)
python main.py

# Con cartera guardada previamente
python main.py --portfolio mi_cartera.json

# Demo con cartera de ejemplo
python main.py --demo

# Guardar reporte completo en JSON
python main.py --output reporte_junio2025.json
```

## Configuración de la cartera (mi_cartera.json)

```json
{
  "cash_ars": 500000,
  "cash_usd": 1500,
  "ingreso_mensual_ars": 250000,
  "horizonte_inversion": "mediano_plazo",
  "objetivo": "crecimiento_capital",
  "holdings": [
    {
      "tipo": "cedear",
      "ticker": "AAPL",
      "cantidad": 15,
      "precio_compra": 8200,
      "moneda_compra": "ARS"
    },
    {
      "tipo": "bono",
      "ticker": "GD30",
      "cantidad": 200,
      "precio_compra": 63.5,
      "moneda_compra": "USD"
    },
    {
      "tipo": "accion",
      "ticker": "GGAL",
      "cantidad": 800,
      "precio_compra": 1150,
      "moneda_compra": "ARS"
    }
  ]
}
```

### Tipos de activos soportados
- `cedear`: CEDEARs (AAPL, MSFT, NVDA, GOOGL, TSLA, META, AMZN, JPM, KO...)
- `accion`: Acciones locales (GGAL, YPF, BMA, PAMP, LOMA, TXAR, ALUA...)
- `bono`: Bonos soberanos (GD29, GD30, GD35, AL29, AL30, TX26, DICP...)
- `plazo_fijo`: Plazo fijo en banco
- `fci`: Fondo Común de Inversión

## Output del sistema

1. **Snapshot de mercado**: tipos de cambio, inflación, tasas, reservas
2. **Análisis de cartera**: valorización actual, ganancia/pérdida por posición
3. **Evaluación de riesgo**: perfil determinado + asset allocation óptimo
4. **Análisis CEDEAR**: TOP 5 con precios, P/E, targets
5. **Análisis acciones AR**: TOP 4 Merval con tesis de inversión
6. **Análisis bonos**: TIR, estrategia dolarización vs CER
7. **Plan de acción final**: operaciones específicas con monto, precio de entrada y target

## Requisitos

- Python 3.10+
- Clave API de Anthropic (claude.ai/settings → API Keys)
- Conexión a internet para datos en tiempo real
