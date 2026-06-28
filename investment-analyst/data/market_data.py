"""
Capa de datos de mercado: precios gratuitos sin API key.
- Yahoo Finance via httpx directo (sin pandas/yfinance)
- dolarapi.com para MEP, CCL, Blue
- BCRA API para macro
"""
import httpx
from datetime import datetime, timedelta
from typing import Optional
import json

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
DOLAR_API_URL = "https://dolarapi.com/v1/dolares/{tipo}"
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}


def get_price_yahoo(ticker: str) -> Optional[float]:
    """
    Precio de mercado via Yahoo Finance (sin yfinance, sin pandas).
    ticker puede ser 'ASML.BA' (BYMA en ARS) o 'ASML' (Nasdaq en USD).
    """
    try:
        resp = httpx.get(
            YAHOO_CHART_URL.format(ticker=ticker),
            headers=YAHOO_HEADERS,
            timeout=10,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        result = data["chart"]["result"]
        if not result:
            return None
        return result[0]["meta"]["regularMarketPrice"]
    except Exception:
        return None


def get_cedear_price(ticker: str) -> dict:
    """
    Precio de un CEDEAR en BYMA (ARS) via Yahoo Finance.
    Intenta primero ticker.BA (BYMA), devuelve precio_ars si hay.
    """
    precio = get_price_yahoo(f"{ticker}.BA")
    if precio:
        return {"ticker": ticker, "precio_ars": precio, "fuente": "Yahoo/BYMA"}

    precio_usd = get_price_yahoo(ticker)
    if precio_usd:
        return {"ticker": ticker, "precio_ars": None, "precio_usd": precio_usd, "fuente": "Yahoo/USD"}

    return {"ticker": ticker, "precio_ars": None, "fuente": None, "error": "no disponible"}


def get_prices_bulk(tickers: list, dolar_mep: float = None) -> dict:
    """
    Precios de múltiples tickers en ARS.
    Si no hay precio .BA, convierte USD usando dolar_mep.
    Devuelve dict: {ticker: precio_ars}.
    """
    precios = {}
    for ticker in tickers:
        r = get_cedear_price(ticker)
        if r.get("precio_ars"):
            precios[ticker] = r["precio_ars"]
        elif r.get("precio_usd") and dolar_mep:
            precios[ticker] = r["precio_usd"] * dolar_mep
    return precios


def get_dolar_simple(tipo: str = "mep") -> Optional[float]:
    """Tipo de cambio directo desde dolarapi.com. tipo: mep, ccl, blue, oficial."""
    try:
        resp = httpx.get(
            DOLAR_API_URL.format(tipo=tipo),
            headers=YAHOO_HEADERS,
            timeout=8,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("venta") or data.get("compra")
    except Exception:
        return None


def get_dolar_tipos() -> dict:
    """Obtiene tipos de cambio del dólar desde APIs públicas de Argentina."""
    # Intentar múltiples fuentes
    endpoints = [
        ("https://dolarapi.com/v1/dolares", "dolarapi"),
        ("https://api.bluelytics.com.ar/v2/latest", "bluelytics"),
    ]

    for url, fuente in endpoints:
        try:
            resp = httpx.get(url, timeout=10, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()

                if fuente == "dolarapi" and isinstance(data, list):
                    result = {}
                    for d in data:
                        nombre = d.get("nombre", "").lower()
                        result[nombre] = {
                            "compra": d.get("compra"),
                            "venta": d.get("venta"),
                            "nombre": d.get("nombre"),
                            "casa": d.get("casa"),
                        }
                    return result

                elif fuente == "bluelytics" and isinstance(data, dict):
                    oficial = data.get("oficial", {})
                    blue = data.get("blue", {})
                    return {
                        "oficial": {"compra": oficial.get("value_buy"), "venta": oficial.get("value_sell"), "nombre": "Oficial"},
                        "blue": {"compra": blue.get("value_buy"), "venta": blue.get("value_sell"), "nombre": "Blue"},
                        "bolsa": {"compra": None, "venta": None, "nombre": "Bolsa (MEP)"},
                        "contado con liquidacion": {"compra": None, "venta": None, "nombre": "CCL"},
                    }
        except Exception:
            continue

    # Fallback con valores de referencia (actualizar manualmente si hace falta)
    print("[Market] APIs de dólar no disponibles, usando valores de referencia")
    return {
        "oficial": {"compra": 1050, "venta": 1080, "nombre": "Oficial"},
        "blue": {"compra": 1250, "venta": 1280, "nombre": "Blue"},
        "bolsa": {"compra": 1200, "venta": 1220, "nombre": "Bolsa (MEP)"},
        "contado con liquidacion": {"compra": 1240, "venta": 1260, "nombre": "CCL"},
        "cripto": {"compra": 1260, "venta": 1270, "nombre": "Cripto"},
    }


def get_dolar_mep() -> Optional[float]:
    """Retorna el tipo de cambio MEP/Bolsa."""
    # Intenta endpoint directo primero (más rápido)
    val = get_dolar_simple("mep")
    if val:
        return val
    # Fallback: endpoint de lista
    tipos = get_dolar_tipos()
    mep = tipos.get("bolsa") or tipos.get("mep")
    if mep:
        return mep.get("venta") or mep.get("compra")
    return None


def get_dolar_ccl() -> Optional[float]:
    """Retorna el tipo de cambio CCL (Contado Con Liquidación)."""
    val = get_dolar_simple("ccl")
    if val:
        return val
    tipos = get_dolar_tipos()
    ccl = tipos.get("contado con liquidacion") or tipos.get("ccl")
    if ccl:
        return ccl.get("venta") or ccl.get("compra")
    return None


def get_bcra_reservas() -> dict:
    """Obtiene datos del BCRA vía API pública."""
    try:
        # Reservas internacionales (idVariable=1)
        resp = httpx.get(
            "https://api.bcra.gob.ar/estadisticas/v2.0/datosvariable/1/2025-01-01/"
            + datetime.now().strftime("%Y-%m-%d"),
            timeout=10,
            headers={"Accept": "application/json"},
            verify=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            resultados = data.get("results", [])
            if resultados:
                ultimo = resultados[-1]
                return {
                    "reservas_millones_usd": ultimo.get("valor"),
                    "fecha": ultimo.get("fecha"),
                }
    except Exception:
        pass
    return {"reservas_millones_usd": None, "fecha": None}


def get_inflacion_bcra() -> dict:
    """Obtiene IPC (inflación) del BCRA."""
    try:
        # IPC nacional (idVariable=27)
        resp = httpx.get(
            "https://api.bcra.gob.ar/estadisticas/v2.0/datosvariable/27/2025-01-01/"
            + datetime.now().strftime("%Y-%m-%d"),
            timeout=10,
            headers={"Accept": "application/json"},
            verify=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            resultados = data.get("results", [])
            if len(resultados) >= 2:
                ultimo = resultados[-1]
                penultimo = resultados[-2]
                return {
                    "inflacion_mensual_pct": ultimo.get("valor"),
                    "inflacion_anterior_pct": penultimo.get("valor"),
                    "fecha": ultimo.get("fecha"),
                }
    except Exception:
        pass
    return {"inflacion_mensual_pct": None, "inflacion_anterior_pct": None, "fecha": None}


def get_tasa_politica_monetaria() -> dict:
    """Obtiene tasa de política monetaria del BCRA."""
    try:
        # Tasa de política monetaria (idVariable=7)
        resp = httpx.get(
            "https://api.bcra.gob.ar/estadisticas/v2.0/datosvariable/7/2025-01-01/"
            + datetime.now().strftime("%Y-%m-%d"),
            timeout=10,
            headers={"Accept": "application/json"},
            verify=False,
        )
        if resp.status_code == 200:
            data = resp.json()
            resultados = data.get("results", [])
            if resultados:
                ultimo = resultados[-1]
                return {
                    "tasa_pct_anual": ultimo.get("valor"),
                    "fecha": ultimo.get("fecha"),
                }
    except Exception:
        pass
    return {"tasa_pct_anual": 35.0, "fecha": None}


def get_us_stock_price(ticker: str) -> dict:
    """Obtiene precio y métricas de una acción US via yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1mo")

        precio_actual = info.get("currentPrice") or info.get("regularMarketPrice")
        if not precio_actual and not hist.empty:
            precio_actual = float(hist["Close"].iloc[-1])

        # Variación 1 mes
        var_1m = None
        if not hist.empty and len(hist) > 1:
            precio_inicio = float(hist["Close"].iloc[0])
            precio_fin = float(hist["Close"].iloc[-1])
            var_1m = ((precio_fin - precio_inicio) / precio_inicio) * 100

        return {
            "ticker": ticker,
            "precio_usd": precio_actual,
            "nombre": info.get("shortName", ticker),
            "pe_ratio": info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "market_cap_b": round(info.get("marketCap", 0) / 1e9, 1) if info.get("marketCap") else None,
            "var_1m_pct": round(var_1m, 2) if var_1m else None,
            "sector": info.get("sector"),
            "dividendYield": info.get("dividendYield"),
        }
    except Exception as e:
        return {"ticker": ticker, "precio_usd": None, "error": str(e)}


def get_cedear_price_ars(ticker_us: str, ratio: int, dolar_ccl: float) -> dict:
    """
    Calcula precio teórico CEDEAR en ARS dado el subyacente US.
    precio_cedear_ars = precio_us_usd * dolar_ccl / ratio
    """
    stock_data = get_us_stock_price(ticker_us)
    if stock_data.get("precio_usd") and dolar_ccl:
        precio_teorico = stock_data["precio_usd"] * dolar_ccl / ratio
        return {
            **stock_data,
            "ratio_cedear": ratio,
            "dolar_ccl": dolar_ccl,
            "precio_cedear_ars_teorico": round(precio_teorico, 2),
        }
    return stock_data


def get_bonos_data() -> dict:
    """
    Intenta obtener precios de bonos argentinos.
    Usa la API de Ambito/ArgentinaDatos donde disponible.
    """
    try:
        # API de ambito para bonos (pública, sin auth)
        resp = httpx.get(
            "https://mercados.ambito.com/bonos/nacionales/variaciones",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            bonos = {}
            if isinstance(data, list):
                for bono in data:
                    ticker = bono.get("simbolo", "")
                    if ticker:
                        bonos[ticker] = {
                            "precio": bono.get("ultimo"),
                            "variacion_pct": bono.get("variacion"),
                            "descripcion": bono.get("descripcion"),
                            "moneda": bono.get("moneda"),
                        }
            return bonos
    except Exception:
        pass

    # Datos de referencia aproximados si la API falla
    return {
        "GD30": {"precio": 70.5, "variacion_pct": 1.2, "descripcion": "Bono Global 2030", "moneda": "USD"},
        "GD35": {"precio": 65.8, "variacion_pct": 0.8, "descripcion": "Bono Global 2035", "moneda": "USD"},
        "AL30": {"precio": 68.2, "variacion_pct": 0.5, "descripcion": "Bono Ley Arg 2030", "moneda": "USD"},
        "GD29": {"precio": 72.1, "variacion_pct": 1.5, "descripcion": "Bono Global 2029", "moneda": "USD"},
        "GD41": {"precio": 60.3, "variacion_pct": 0.3, "descripcion": "Bono Global 2041", "moneda": "USD"},
    }


def get_merval_acciones() -> dict:
    """
    Obtiene datos de acciones del Merval.
    Usa Yahoo Finance con sufijo .BA para Argentina.
    """
    tickers_ba = {
        "GGAL": "GGAL.BA",
        "YPF": "YPF",  # YPF cotiza en NYSE también
        "BMA": "BMA",   # Macro cotiza en NYSE ADR
        "PAMP": "PAM",  # Pampa en NYSE
        "LOMA": "LOMA.BA",
        "TECO2": "TECO2.BA",
        "ALUA": "ALUA.BA",
        "TXAR": "TXAR.BA",
        "CEPU": "CEPU.BA",
        "EDN": "EDN",
    }

    acciones = {}
    for simbolo, ticker in tickers_ba.items():
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1mo")

            precio = info.get("currentPrice") or info.get("regularMarketPrice")
            if not precio and not hist.empty:
                precio = float(hist["Close"].iloc[-1])

            var_1m = None
            if not hist.empty and len(hist) > 1:
                v0 = float(hist["Close"].iloc[0])
                vf = float(hist["Close"].iloc[-1])
                var_1m = ((vf - v0) / v0) * 100

            acciones[simbolo] = {
                "ticker": ticker,
                "precio": precio,
                "nombre": info.get("shortName", simbolo),
                "var_1m_pct": round(var_1m, 2) if var_1m else None,
                "pe_ratio": info.get("trailingPE"),
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "moneda": "ARS" if ticker.endswith(".BA") else "USD",
            }
        except Exception as e:
            acciones[simbolo] = {"ticker": ticker, "precio": None, "error": str(e)}

    return acciones


def fetch_all_market_data() -> dict:
    """Obtiene todos los datos de mercado en paralelo."""
    print("[Market] Obteniendo tipos de cambio...")
    dolares = get_dolar_tipos()

    ccl = None
    for key in ["contado con liquidacion", "ccl", "bolsa", "mep"]:
        if key in dolares and dolares[key].get("venta"):
            ccl = dolares[key]["venta"]
            break

    if not ccl:
        ccl = 1250  # fallback

    print("[Market] Obteniendo datos BCRA...")
    inflacion = get_inflacion_bcra()
    tasa_pm = get_tasa_politica_monetaria()
    reservas = get_bcra_reservas()

    print("[Market] Obteniendo datos de bonos...")
    bonos = get_bonos_data()

    print("[Market] Obteniendo acciones Merval...")
    acciones = get_merval_acciones()

    return {
        "fecha_consulta": datetime.now().isoformat(),
        "tipo_cambio": dolares,
        "dolar_ccl": ccl,
        "macroeconomia": {
            "inflacion": inflacion,
            "tasa_politica_monetaria": tasa_pm,
            "reservas": reservas,
        },
        "bonos": bonos,
        "acciones_merval": acciones,
    }
