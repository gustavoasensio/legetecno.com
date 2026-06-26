"""
Orquestador Principal: Analista de Inversiones Argentino.
Coordina todos los sub-agentes y produce el análisis integral.
"""
import anthropic
import json
import sys
from typing import Any
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from config import ORCHESTRATOR_MODEL
from data.market_data import fetch_all_market_data
from tools.portfolio_tool import analyze_portfolio
from tools.cedear_tool import analyze_cedears
from tools.acciones_tool import analyze_acciones_argentinas
from tools.bond_tool import analyze_bonos
from tools.risk_tool import assess_risk
from tools.report_tool import generate_final_report

console = Console()

# Definición de herramientas para el orquestador
TOOLS = [
    {
        "name": "analyze_portfolio",
        "description": "Analiza la composición, valorización y performance de la cartera actual del cliente. Calcula el valor total, ganancia/pérdida por posición y métricas de concentración.",
        "input_schema": {
            "type": "object",
            "properties": {
                "capital_para_invertir_ars": {
                    "type": "number",
                    "description": "Capital disponible en ARS para nuevas inversiones",
                },
                "perfil_riesgo_estimado": {
                    "type": "string",
                    "enum": ["conservador", "moderado", "agresivo"],
                    "description": "Estimación inicial del perfil de riesgo",
                },
            },
            "required": [],
        },
    },
    {
        "name": "analyze_risk_and_allocation",
        "description": "Evalúa el perfil de riesgo del inversor y determina la asignación óptima de activos (asset allocation) entre CEDEARs, acciones, bonos y cash.",
        "input_schema": {
            "type": "object",
            "properties": {
                "horizonte_inversion": {
                    "type": "string",
                    "enum": ["corto_plazo", "mediano_plazo", "largo_plazo"],
                    "description": "Horizonte de inversión: corto (< 6 meses), mediano (6-24 meses), largo (> 2 años)",
                },
                "objetivo": {
                    "type": "string",
                    "description": "Objetivo principal: preservacion_capital / crecimiento_capital / renta / dolarizacion",
                },
            },
            "required": [],
        },
    },
    {
        "name": "analyze_cedears",
        "description": "Analiza el mercado de CEDEARs (acciones extranjeras en pesos vía BYMA). Obtiene precios actuales de Wall Street, calcula precio teórico en ARS con tipo de cambio CCL, y recomienda las mejores oportunidades.",
        "input_schema": {
            "type": "object",
            "properties": {
                "capital_cedears_ars": {
                    "type": "number",
                    "description": "Capital a asignar en CEDEARs en ARS",
                },
                "perfil_riesgo": {
                    "type": "string",
                    "enum": ["conservador", "moderado", "agresivo"],
                },
            },
            "required": ["capital_cedears_ars"],
        },
    },
    {
        "name": "analyze_acciones_argentinas",
        "description": "Analiza oportunidades en acciones argentinas del panel Merval/BYMA (YPF, GGAL, BMA, Pampa, etc.). Evalúa contexto macro y recomienda las mejores posiciones.",
        "input_schema": {
            "type": "object",
            "properties": {
                "capital_acciones_ars": {
                    "type": "number",
                    "description": "Capital a asignar en acciones argentinas en ARS",
                },
                "perfil_riesgo": {
                    "type": "string",
                    "enum": ["conservador", "moderado", "agresivo"],
                },
            },
            "required": ["capital_acciones_ars"],
        },
    },
    {
        "name": "analyze_bonos",
        "description": "Analiza el mercado de renta fija argentina: bonos soberanos (GD30, AL30, etc.), instrumentos CER, letras del Tesoro y ONs corporativas. Calcula TIR y recomienda estrategia.",
        "input_schema": {
            "type": "object",
            "properties": {
                "capital_bonos_ars": {
                    "type": "number",
                    "description": "Capital a asignar en bonos en ARS",
                },
                "perfil_riesgo": {
                    "type": "string",
                    "enum": ["conservador", "moderado", "agresivo"],
                },
            },
            "required": ["capital_bonos_ars"],
        },
    },
    {
        "name": "generate_final_report",
        "description": "Genera el reporte final integrado con plan de acción concreto, operaciones específicas priorizadas, distribución exacta del capital y objetivos de rendimiento. Llamar ÚLTIMO después de todos los análisis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ready": {
                    "type": "boolean",
                    "description": "Confirma que todos los análisis previos están completos",
                }
            },
            "required": ["ready"],
        },
    },
]


def _print_market_snapshot(market_data: dict):
    """Imprime snapshot del mercado en tiempo real."""
    dolares = market_data.get("tipo_cambio", {})
    macro = market_data.get("macroeconomia", {})
    inflacion = macro.get("inflacion", {})
    tasa = macro.get("tasa_politica_monetaria", {})

    tabla = Table(title="📊 Mercado Argentino en Vivo", show_header=True, header_style="bold cyan")
    tabla.add_column("Indicador", style="white")
    tabla.add_column("Valor", style="yellow bold")
    tabla.add_column("Fuente", style="dim")

    for nombre, data in dolares.items():
        if data.get("venta"):
            tabla.add_row(
                f"Dólar {data.get('nombre', nombre).title()}",
                f"${data['venta']:,.2f} ARS",
                "dolarapi.com",
            )

    if inflacion.get("inflacion_mensual_pct"):
        tabla.add_row("Inflación mensual", f"{inflacion['inflacion_mensual_pct']}%", "BCRA")
    if tasa.get("tasa_pct_anual"):
        tabla.add_row("Tasa política monetaria", f"{tasa['tasa_pct_anual']}% TNA", "BCRA")
    if macro.get("reservas", {}).get("reservas_millones_usd"):
        tabla.add_row(
            "Reservas BCRA",
            f"USD {macro['reservas']['reservas_millones_usd']:,.0f}M",
            "BCRA",
        )

    console.print(tabla)


def _process_tool_call(
    tool_name: str,
    tool_input: dict,
    portfolio: dict,
    market_data: dict,
    results_cache: dict,
) -> Any:
    """Ejecuta la herramienta solicitada por el orquestador."""

    console.print(f"\n  [bold cyan]→ Sub-agente:[/bold cyan] [yellow]{tool_name}[/yellow]")

    if tool_name == "analyze_portfolio":
        result = analyze_portfolio(portfolio, market_data)
        results_cache["portfolio_analysis"] = result
        return result

    elif tool_name == "analyze_risk_and_allocation":
        portfolio_enriched = {
            **portfolio,
            "horizonte_inversion": tool_input.get("horizonte_inversion", "mediano_plazo"),
            "objetivo": tool_input.get("objetivo", "crecimiento_capital"),
        }
        portfolio_analysis = results_cache.get("portfolio_analysis", {})
        if not portfolio_analysis:
            portfolio_analysis = analyze_portfolio(portfolio_enriched, market_data)
            results_cache["portfolio_analysis"] = portfolio_analysis

        result = assess_risk(portfolio_enriched, portfolio_analysis, market_data)
        results_cache["risk_assessment"] = result
        return result

    elif tool_name == "analyze_cedears":
        capital = tool_input.get("capital_cedears_ars", portfolio.get("cash_ars", 50000))
        perfil = tool_input.get("perfil_riesgo", "moderado")
        result = analyze_cedears(market_data, capital, perfil)
        results_cache["cedear_analysis"] = result
        return result

    elif tool_name == "analyze_acciones_argentinas":
        capital = tool_input.get("capital_acciones_ars", portfolio.get("cash_ars", 50000))
        perfil = tool_input.get("perfil_riesgo", "moderado")
        result = analyze_acciones_argentinas(market_data, capital, perfil)
        results_cache["acciones_analysis"] = result
        return result

    elif tool_name == "analyze_bonos":
        capital = tool_input.get("capital_bonos_ars", portfolio.get("cash_ars", 50000))
        perfil = tool_input.get("perfil_riesgo", "moderado")
        result = analyze_bonos(market_data, capital, perfil)
        results_cache["bond_analysis"] = result
        return result

    elif tool_name == "generate_final_report":
        result = generate_final_report(
            portfolio=portfolio,
            portfolio_analysis=results_cache.get("portfolio_analysis", {}),
            risk_assessment=results_cache.get("risk_assessment", {}),
            cedear_analysis=results_cache.get("cedear_analysis", {}),
            acciones_analysis=results_cache.get("acciones_analysis", {}),
            bond_analysis=results_cache.get("bond_analysis", {}),
            market_data=market_data,
        )
        results_cache["final_report"] = result
        return result

    return {"error": f"Herramienta desconocida: {tool_name}"}


def run_orchestrator(portfolio: dict) -> dict:
    """
    Ejecuta el orquestador completo de análisis de inversiones.

    portfolio = {
        "cash_ars": float,
        "cash_usd": float,
        "ingreso_mensual_ars": float,
        "horizonte_inversion": "corto_plazo|mediano_plazo|largo_plazo",
        "objetivo": "crecimiento_capital|preservacion_capital|renta|dolarizacion",
        "holdings": [...]
    }
    """
    console.print(
        Panel.fit(
            "[bold white]ANALISTA DE INVERSIONES ARGENTINO[/bold white]\n"
            "[dim]Sistema Multi-Agente de Análisis de Cartera[/dim]",
            style="bold blue",
        )
    )

    # 1. Obtener datos de mercado en tiempo real
    console.print("\n[bold]1. Obteniendo datos de mercado en tiempo real...[/bold]")
    market_data = fetch_all_market_data()
    _print_market_snapshot(market_data)

    # 2. Inicializar el cliente y el estado del orquestador
    client = anthropic.Anthropic()
    results_cache = {}

    dolar_ccl = market_data.get("dolar_ccl", 1250)
    capital_total_ars = (
        portfolio.get("cash_ars", 0)
        + portfolio.get("cash_usd", 0) * dolar_ccl
    )

    system_prompt = f"""Eres el Director de Inversiones de una firma financiera argentina de primer nivel.
Tu misión es coordinar un análisis exhaustivo de la cartera del cliente y generar las mejores recomendaciones
de inversión en CEDEARs, acciones argentinas y bonos para MAXIMIZAR sus ganancias.

CONTEXTO DEL CLIENTE:
- Cash disponible: ${portfolio.get('cash_ars', 0):,.0f} ARS + USD {portfolio.get('cash_usd', 0):,.0f}
- Capital total a invertir: ~${capital_total_ars:,.0f} ARS (≈ USD {capital_total_ars/dolar_ccl:,.0f})
- Ingreso mensual para invertir: ${portfolio.get('ingreso_mensual_ars', 0):,.0f} ARS
- Horizonte: {portfolio.get('horizonte_inversion', 'mediano_plazo')}
- Objetivo: {portfolio.get('objetivo', 'crecimiento_capital')}
- Holdings actuales: {len(portfolio.get('holdings', []))} posiciones

INSTRUCCIONES:
1. Primero analiza la cartera actual
2. Luego evalúa el riesgo y determina el asset allocation óptimo
3. Analiza CADA clase de activo: CEDEARs, acciones argentinas, bonos
4. Finalmente genera el reporte integrado con plan de acción concreto

Usa las herramientas en ESTE ORDEN:
1. analyze_portfolio → análisis de cartera actual
2. analyze_risk_and_allocation → perfil de riesgo y asset allocation
3. analyze_cedears → mejores CEDEARs
4. analyze_acciones_argentinas → mejores acciones AR
5. analyze_bonos → mejores bonos
6. generate_final_report → plan de acción final

Sé metódico. Completa TODOS los análisis antes del reporte final."""

    messages = [
        {
            "role": "user",
            "content": f"""Realiza el análisis completo de mi cartera de inversiones argentina.

Mi portfolio:
- Cash ARS: ${portfolio.get('cash_ars', 0):,.0f}
- Cash USD: ${portfolio.get('cash_usd', 0):,.0f}
- Ingreso mensual para invertir: ${portfolio.get('ingreso_mensual_ars', 0):,.0f} ARS
- Posiciones actuales: {json.dumps(portfolio.get('holdings', []), ensure_ascii=False)}
- Horizonte de inversión: {portfolio.get('horizonte_inversion', 'mediano_plazo')}
- Objetivo principal: {portfolio.get('objetivo', 'crecimiento_capital')}

Por favor coordina todos los sub-agentes y dame el análisis completo con el plan de acción.""",
        }
    ]

    console.print("\n[bold]2. Iniciando análisis multi-agente...[/bold]\n")

    # Agentic loop del orquestador
    iteration = 0
    max_iterations = 20

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model=ORCHESTRATOR_MODEL,
            max_tokens=4096,
            tools=TOOLS,
            system=system_prompt,
            messages=messages,
        )

        # Agregar respuesta del asistente al historial
        messages.append({"role": "assistant", "content": response.content})

        # Verificar si hay tool_use
        has_tool_use = any(block.type == "tool_use" for block in response.content)

        if not has_tool_use:
            # El orquestador terminó su análisis
            break

        # Procesar tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                tool_result = _process_tool_call(
                    tool_name, tool_input, portfolio, market_data, results_cache
                )

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })

        messages.append({"role": "user", "content": tool_results})

        # Mostrar stop_reason
        if response.stop_reason == "end_turn":
            break

    return results_cache


def _print_final_report(results: dict):
    """Imprime el reporte final en formato rico."""
    final_report_data = results.get("final_report", {})
    report = final_report_data.get("reporte_final", {})
    metadata = final_report_data.get("metadata", {})

    if not report:
        console.print("[red]No se pudo generar el reporte final[/red]")
        return

    console.print("\n")
    console.print(
        Panel.fit(
            "[bold white]REPORTE DE INVERSIÓN - PLAN DE ACCIÓN[/bold white]",
            style="bold green",
        )
    )

    # Metadata
    console.print(f"\n[dim]Generado: {metadata.get('fecha_generacion', 'N/A')}[/dim]")
    console.print(f"[dim]Dólar CCL: ${metadata.get('dolar_ccl', 'N/A'):,.2f} | Patrimonio: ${metadata.get('patrimonio_total_ars', 0):,.0f} ARS | Perfil: {metadata.get('perfil_riesgo', 'N/A')}[/dim]\n")

    # Resumen ejecutivo
    resumen = report.get("resumen_ejecutivo", "")
    if resumen:
        console.print(Panel(resumen, title="[bold]Resumen Ejecutivo[/bold]", border_style="cyan"))

    # Operaciones inmediatas
    ops = report.get("operaciones_inmediatas", [])
    if ops:
        console.print("\n[bold cyan]OPERACIONES INMEDIATAS[/bold cyan]")
        tabla_ops = Table(show_header=True, header_style="bold")
        tabla_ops.add_column("#", style="dim", width=3)
        tabla_ops.add_column("Acción", style="bold")
        tabla_ops.add_column("Ticker")
        tabla_ops.add_column("Monto ARS", justify="right")
        tabla_ops.add_column("Cantidad")
        tabla_ops.add_column("P. Entrada Máx", justify="right")
        tabla_ops.add_column("Justificación")

        for i, op in enumerate(ops, 1):
            accion = op.get("accion", op.get("tipo", ""))
            color = "green" if "COMPRAR" in str(accion).upper() else "red" if "VENDER" in str(accion).upper() else "yellow"
            tabla_ops.add_row(
                str(i),
                f"[{color}]{accion}[/{color}]",
                str(op.get("ticker", op.get("simbolo", ""))),
                f"${op.get('monto_ars', op.get('monto', 0)):,.0f}" if op.get("monto_ars") or op.get("monto") else "-",
                str(op.get("cantidad", op.get("unidades", ""))),
                f"${op.get('precio_maximo_entrada', op.get('precio_entrada', ''))}" if op.get("precio_maximo_entrada") or op.get("precio_entrada") else "-",
                str(op.get("justificacion", op.get("razon", "")))[:50],
            )
        console.print(tabla_ops)

    # Distribución de capital
    dist = report.get("distribucion_capital", [])
    if dist:
        console.print("\n[bold cyan]DISTRIBUCIÓN DEL CAPITAL[/bold cyan]")
        tabla_dist = Table(show_header=True, header_style="bold")
        tabla_dist.add_column("Ticker/Instrumento")
        tabla_dist.add_column("Monto ARS", justify="right")
        tabla_dist.add_column("%", justify="right")
        tabla_dist.add_column("Objetivo")

        for item in dist:
            tabla_dist.add_row(
                str(item.get("ticker", item.get("instrumento", ""))),
                f"${item.get('monto_ars', item.get('monto', 0)):,.0f}" if item.get("monto_ars") or item.get("monto") else "-",
                f"{item.get('porcentaje', item.get('pct', ''))}%",
                str(item.get("objetivo", item.get("target", "")))[:40],
            )
        console.print(tabla_dist)

    # Objetivos de rendimiento
    objetivos = report.get("objetivos_rendimiento", {})
    if objetivos:
        console.print("\n[bold cyan]OBJETIVOS DE RENDIMIENTO[/bold cyan]")
        for escenario, datos in objetivos.items():
            if isinstance(datos, dict):
                console.print(f"  [bold]{escenario.upper()}:[/bold] ARS: {datos.get('rendimiento_ars', '')} | USD: {datos.get('rendimiento_usd', '')}")
            else:
                console.print(f"  [bold]{escenario.upper()}:[/bold] {datos}")

    # Alertas
    alertas = report.get("alertas_seguimiento", [])
    if alertas:
        console.print("\n[bold yellow]⚠ ALERTAS DE SEGUIMIENTO[/bold yellow]")
        for alerta in alertas:
            if isinstance(alerta, dict):
                console.print(f"  • [bold]{alerta.get('indicador', alerta.get('nombre', ''))}[/bold]: {alerta.get('descripcion', alerta.get('accion', ''))}")
            else:
                console.print(f"  • {alerta}")

    # Próxima revisión
    revision = report.get("proxima_revision", {})
    if revision:
        console.print("\n[bold]PRÓXIMA REVISIÓN[/bold]")
        if isinstance(revision, dict):
            console.print(f"  Fecha: {revision.get('fecha', 'N/A')}")
            for item in revision.get("agenda", []):
                console.print(f"  • {item}")
        else:
            console.print(f"  {revision}")
