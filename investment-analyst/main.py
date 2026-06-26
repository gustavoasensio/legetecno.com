#!/usr/bin/env python3
"""
Punto de entrada del Analista de Inversiones Argentino.
Uso: python main.py [--portfolio archivo.json]
"""
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt, FloatPrompt, Confirm

load_dotenv()

console = Console()

PORTFOLIO_EXAMPLE_PATH = Path(__file__).parent / "mi_cartera.json"


def load_portfolio_interactive() -> dict:
    """Solicita los datos del portafolio al usuario de forma interactiva."""
    console.print("\n[bold cyan]━━━ CONFIGURACIÓN DE CARTERA ━━━[/bold cyan]\n")
    console.print("Ingresá tus datos para el análisis. Dejá en 0 lo que no tengas.\n")

    cash_ars = FloatPrompt.ask("[bold]Cash disponible en PESOS (ARS)[/bold]", default=0.0)
    cash_usd = FloatPrompt.ask("[bold]Cash disponible en DÓLARES (USD)[/bold]", default=0.0)
    ingreso_mensual = FloatPrompt.ask("[bold]Ingreso mensual disponible para invertir (ARS)[/bold]", default=0.0)

    console.print("\n[bold]Horizonte de inversión:[/bold]")
    console.print("  1. Corto plazo (< 6 meses)")
    console.print("  2. Mediano plazo (6 meses - 2 años)")
    console.print("  3. Largo plazo (> 2 años)")
    horizonte_opt = Prompt.ask("Opción", choices=["1", "2", "3"], default="2")
    horizontes = {"1": "corto_plazo", "2": "mediano_plazo", "3": "largo_plazo"}
    horizonte = horizontes[horizonte_opt]

    console.print("\n[bold]Objetivo principal:[/bold]")
    console.print("  1. Crecimiento de capital (máximas ganancias)")
    console.print("  2. Dolarización (convertir pesos a dólares)")
    console.print("  3. Preservación del capital (menor riesgo)")
    console.print("  4. Renta (ingresos periódicos)")
    obj_opt = Prompt.ask("Opción", choices=["1", "2", "3", "4"], default="1")
    objetivos = {
        "1": "crecimiento_capital",
        "2": "dolarizacion",
        "3": "preservacion_capital",
        "4": "renta",
    }
    objetivo = objetivos[obj_opt]

    holdings = []
    agregar_holdings = Confirm.ask("\n¿Tenés posiciones actuales que quieras incluir en el análisis?", default=False)

    if agregar_holdings:
        console.print("\n[dim]Tipos: cedear / accion / bono / plazo_fijo / fci[/dim]")
        while True:
            console.print("\n[cyan]--- Nueva posición ---[/cyan]")
            tipo = Prompt.ask("Tipo", choices=["cedear", "accion", "bono", "plazo_fijo", "fci"])
            ticker = Prompt.ask("Ticker (ej: AAPL, GGAL, GD30)").upper()
            cantidad = FloatPrompt.ask("Cantidad de unidades")
            precio_compra = FloatPrompt.ask("Precio de compra promedio")
            moneda = Prompt.ask("Moneda de compra", choices=["ARS", "USD"], default="ARS")
            precio_actual = FloatPrompt.ask("Precio actual (0 si no sabés)", default=0.0)

            holding = {
                "tipo": tipo,
                "ticker": ticker,
                "cantidad": cantidad,
                "precio_compra": precio_compra,
                "moneda_compra": moneda,
            }
            if precio_actual > 0:
                holding["precio_actual_ars"] = precio_actual

            holdings.append(holding)

            if not Confirm.ask("¿Agregar otra posición?", default=False):
                break

    portfolio = {
        "cash_ars": cash_ars,
        "cash_usd": cash_usd,
        "ingreso_mensual_ars": ingreso_mensual,
        "horizonte_inversion": horizonte,
        "objetivo": objetivo,
        "holdings": holdings,
    }

    guardar = Confirm.ask("\n¿Guardar esta cartera para próximos análisis?", default=True)
    if guardar:
        with open(PORTFOLIO_EXAMPLE_PATH, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Guardado en:[/green] {PORTFOLIO_EXAMPLE_PATH}")

    return portfolio


def load_portfolio_from_file(filepath: str) -> dict:
    """Carga el portafolio desde un archivo JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_report(results: dict, output_path: str = None):
    """Guarda el reporte completo en JSON."""
    if not output_path:
        from datetime import datetime
        output_path = f"reporte_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    console.print(f"\n[green]Reporte guardado en:[/green] {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analista de Inversiones Argentino - Sistema Multi-Agente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py                           # Modo interactivo
  python main.py --portfolio mi_cartera.json  # Desde archivo
  python main.py --demo                    # Cartera de ejemplo
        """,
    )
    parser.add_argument("--portfolio", "-p", help="Ruta al archivo JSON con la cartera")
    parser.add_argument("--output", "-o", help="Ruta para guardar el reporte JSON completo")
    parser.add_argument("--demo", action="store_true", help="Usar cartera de ejemplo para demo")
    args = parser.parse_args()

    # Verificar API key
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY no configurada.[/red]")
        console.print("Crear archivo .env con: ANTHROPIC_API_KEY=tu_clave_aqui")
        sys.exit(1)

    # Cargar portafolio
    if args.demo:
        portfolio = {
            "cash_ars": 500000,
            "cash_usd": 1000,
            "ingreso_mensual_ars": 200000,
            "horizonte_inversion": "mediano_plazo",
            "objetivo": "crecimiento_capital",
            "holdings": [
                {
                    "tipo": "cedear",
                    "ticker": "AAPL",
                    "cantidad": 10,
                    "precio_compra": 8500,
                    "moneda_compra": "ARS",
                },
                {
                    "tipo": "bono",
                    "ticker": "GD30",
                    "cantidad": 100,
                    "precio_compra": 65,
                    "moneda_compra": "USD",
                },
                {
                    "tipo": "accion",
                    "ticker": "GGAL",
                    "cantidad": 500,
                    "precio_compra": 1200,
                    "moneda_compra": "ARS",
                },
            ],
        }
        console.print("[yellow]Usando cartera de DEMO[/yellow]")
    elif args.portfolio:
        portfolio = load_portfolio_from_file(args.portfolio)
        console.print(f"[green]Cartera cargada desde:[/green] {args.portfolio}")
    elif PORTFOLIO_EXAMPLE_PATH.exists():
        usar_guardada = Confirm.ask(
            f"\n¿Usar la cartera guardada anteriormente? ({PORTFOLIO_EXAMPLE_PATH})",
            default=True,
        )
        if usar_guardada:
            portfolio = load_portfolio_from_file(str(PORTFOLIO_EXAMPLE_PATH))
        else:
            portfolio = load_portfolio_interactive()
    else:
        portfolio = load_portfolio_interactive()

    # Ejecutar orquestador
    from orchestrator import run_orchestrator, _print_final_report

    results = run_orchestrator(portfolio)

    # Imprimir reporte final
    _print_final_report(results)

    # Guardar reporte
    save_report(results, args.output)

    console.print("\n[bold green]✓ Análisis completado.[/bold green]")


if __name__ == "__main__":
    main()
