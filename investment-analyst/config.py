"""
Configuración del sistema de análisis de inversiones.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# API Keys (configurar en .env)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
IOL_USER = os.getenv("IOL_USER", "")
IOL_PASSWORD = os.getenv("IOL_PASSWORD", "")

# Modelo Claude
ORCHESTRATOR_MODEL = "claude-sonnet-4-6"
ANALYST_MODEL = "claude-sonnet-4-6"

# Tasas de referencia Argentina (se actualizan via API)
TASA_PLAZO_FIJO_REF = 0.35  # 35% anual referencia
TASA_POLÍTICA_MONETARIA_REF = 0.40  # 40% anual

# CEDEARs populares con sus ratios (ticker_byma: {subyacente, ratio})
CEDEARS_PRINCIPALES = {
    "AAPL": {"subyacente": "AAPL", "ratio": 10, "nombre": "Apple Inc."},
    "GOOGL": {"subyacente": "GOOGL", "ratio": 8, "nombre": "Alphabet Inc."},
    "MSFT": {"subyacente": "MSFT", "ratio": 8, "nombre": "Microsoft Corp."},
    "AMZN": {"subyacente": "AMZN", "ratio": 22, "nombre": "Amazon.com Inc."},
    "TSLA": {"subyacente": "TSLA", "ratio": 10, "nombre": "Tesla Inc."},
    "META": {"subyacente": "META", "ratio": 7, "nombre": "Meta Platforms"},
    "NVDA": {"subyacente": "NVDA", "ratio": 3, "nombre": "NVIDIA Corp."},
    "BABA": {"subyacente": "BABA", "ratio": 8, "nombre": "Alibaba Group"},
    "DIS": {"subyacente": "DIS", "ratio": 15, "nombre": "Walt Disney Co."},
    "JPM": {"subyacente": "JPM", "ratio": 10, "nombre": "JPMorgan Chase"},
    "WMT": {"subyacente": "WMT", "ratio": 8, "nombre": "Walmart Inc."},
    "BRKA": {"subyacente": "BRK-A", "ratio": 200, "nombre": "Berkshire Hathaway A"},
    "KO": {"subyacente": "KO", "ratio": 10, "nombre": "Coca-Cola Co."},
    "PFE": {"subyacente": "PFE", "ratio": 25, "nombre": "Pfizer Inc."},
}

# Acciones argentinas Merval
ACCIONES_MERVAL = {
    "GGAL": "Grupo Financiero Galicia",
    "YPF": "YPF S.A.",
    "BMA": "Banco Macro",
    "PAMP": "Pampa Energía",
    "LOMA": "Loma Negra",
    "SUPV": "Banco Supervielle",
    "TECO2": "Telecom Argentina",
    "ALUA": "Aluar Aluminio",
    "CRES": "Cresud",
    "EDN": "Edenor",
    "TXAR": "Ternium Argentina",
    "VALO": "Grupo Financiero Valores",
    "METR": "Metrogas",
    "CEPU": "Central Puerto",
    "BYMA": "BYMA",
}

# Bonos soberanos de referencia
BONOS_PRINCIPALES = {
    "AL29": {"descripcion": "Bono Ley Arg 2029 USD", "moneda": "USD", "ley": "ARG"},
    "AL30": {"descripcion": "Bono Ley Arg 2030 USD", "moneda": "USD", "ley": "ARG"},
    "AL35": {"descripcion": "Bono Ley Arg 2035 USD", "moneda": "USD", "ley": "ARG"},
    "GD29": {"descripcion": "Bono Global 2029 USD", "moneda": "USD", "ley": "NY"},
    "GD30": {"descripcion": "Bono Global 2030 USD", "moneda": "USD", "ley": "NY"},
    "GD35": {"descripcion": "Bono Global 2035 USD", "moneda": "USD", "ley": "NY"},
    "GD38": {"descripcion": "Bono Global 2038 USD", "moneda": "USD", "ley": "NY"},
    "GD41": {"descripcion": "Bono Global 2041 USD", "moneda": "USD", "ley": "NY"},
    "GD46": {"descripcion": "Bono Global 2046 USD", "moneda": "USD", "ley": "NY"},
    "T2X5": {"descripcion": "Bono CER 2025", "moneda": "ARS", "ajuste": "CER"},
    "TX26": {"descripcion": "Bono CER 2026", "moneda": "ARS", "ajuste": "CER"},
    "DICP": {"descripcion": "Discount CER", "moneda": "ARS", "ajuste": "CER"},
    "AE38": {"descripcion": "Bono Ley Arg 2038", "moneda": "USD", "ley": "ARG"},
}

# Letras del Tesoro
LETRAS_PRINCIPALES = {
    "S28F5": "Letra Tes. Descuento Feb 2025",
    "S31M5": "Letra Tes. Descuento Mar 2025",
    "S30J5": "Letra Tes. Descuento Jun 2025",
}
