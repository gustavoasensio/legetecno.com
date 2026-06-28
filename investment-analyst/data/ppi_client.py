"""
Cliente oficial de la API de Portfolio Personal Inversiones (PPI).
Docs: https://clientapi.portfoliopersonal.com/swagger

Credenciales en .env:
  PPI_PUBLIC_KEY    → "Key pública" de tu cuenta PPI
  PPI_PRIVATE_KEY   → "Key privada" (pedila a api@portfoliopersonal.com si la perdiste)

Credenciales de aplicación (fijas para todos los usuarios REST — no son secretas):
  AuthorizedClient: API_CLI_REST
  ClientKey:        pp19CliApp12
"""
import httpx
import json
import os
from datetime import datetime, timedelta
from typing import Optional

PPI_BASE_URL_PROD    = "https://clientapi.portfoliopersonal.com"
PPI_BASE_URL_SANDBOX = "https://sandboxclientapi.portfoliopersonal.com"

# Credenciales de aplicación REST (compartidas por todos los usuarios de la API)
PPI_AUTHORIZED_CLIENT = "API_CLI_REST"
PPI_CLIENT_KEY_PROD    = "pp19CliApp12"
PPI_CLIENT_KEY_SANDBOX = "ppApiCliSB"


class PPIAuthError(Exception):
    pass


class PPIClient:
    def __init__(
        self,
        public_key: str = None,
        private_key: str = None,
        sandbox: bool = None,
    ):
        # sandbox=None → usa PPI_SANDBOX env var; True/False → fuerza modo
        if sandbox is None:
            sandbox = os.getenv("PPI_SANDBOX", "false").lower() == "true"

        self.sandbox = sandbox
        self.base_url = PPI_BASE_URL_SANDBOX if sandbox else PPI_BASE_URL_PROD
        self.client_key = PPI_CLIENT_KEY_SANDBOX if sandbox else PPI_CLIENT_KEY_PROD

        # Claves de usuario: sandbox o producción según modo
        if sandbox:
            self.public_key = public_key or os.getenv("PPI_SANDBOX_PUBLIC_KEY", "")
            self.private_key = private_key or os.getenv("PPI_SANDBOX_PRIVATE_KEY", "")
        else:
            self.public_key = public_key or os.getenv("PPI_PUBLIC_KEY", "")
            self.private_key = private_key or os.getenv("PPI_PRIVATE_KEY", "")

        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

        if not self.public_key:
            env_var = "PPI_SANDBOX_PUBLIC_KEY" if sandbox else "PPI_PUBLIC_KEY"
            raise PPIAuthError(f"Falta {env_var} en el archivo .env")

    # ── Autenticación ─────────────────────────────────────────────────────────

    def _app_headers(self) -> dict:
        """Headers de identificación de aplicación — van en TODOS los requests."""
        return {
            "AuthorizedClient": PPI_AUTHORIZED_CLIENT,
            "ClientKey": self.client_key,
            "Content-Type": "application/json",
        }

    def _is_token_valid(self) -> bool:
        if not self._token or not self._token_expires:
            return False
        return datetime.now() < self._token_expires - timedelta(minutes=5)

    def authenticate(self) -> bool:
        """Obtiene JWT de acceso usando las credenciales de API."""
        try:
            body = {"PublicKey": self.public_key}
            if self.private_key:
                body["PrivateKey"] = self.private_key

            resp = httpx.post(
                f"{self.base_url}/api/OAuth/LoginApi",
                headers=self._app_headers(),
                json=body,
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                self._token = (
                    data.get("AccessToken")
                    or data.get("access_token")
                    or data.get("token")
                    or data.get("Token")
                )
                expires_in = data.get("ExpiresIn") or data.get("expires_in") or 3600
                self._token_expires = datetime.now() + timedelta(seconds=int(expires_in))
                return bool(self._token)
            else:
                raise PPIAuthError(
                    f"PPI auth falló [{resp.status_code}]: {resp.text[:400]}"
                )
        except PPIAuthError:
            raise
        except Exception as e:
            raise PPIAuthError(f"Error de conexión con PPI: {e}")

    def _ensure_auth(self):
        if not self._is_token_valid():
            self.authenticate()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict | list:
        self._ensure_auth()
        resp = httpx.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params or {},
            timeout=20,
        )
        if resp.status_code == 401:
            # Token expirado → re-autenticar
            self._token = None
            self.authenticate()
            resp = httpx.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                params=params or {},
                timeout=20,
            )
        resp.raise_for_status()
        return resp.json()

    # ── Cuenta ────────────────────────────────────────────────────────────────

    def get_accounts(self) -> list:
        """Lista las cuentas comitentes del usuario."""
        try:
            data = self._get("/api/Account/GetAccounts")
            return data if isinstance(data, list) else data.get("Accounts", [])
        except Exception as e:
            print(f"[PPI] Error cuentas: {e}")
            return []

    def get_balance(self, account_number: str = None) -> dict:
        """Saldo disponible en ARS y USD."""
        try:
            params = {}
            if account_number:
                params["accountNumber"] = account_number
            return self._get("/api/Account/GetBalance", params)
        except Exception as e:
            print(f"[PPI] Error saldo: {e}")
            return {}

    # ── Portfolio ─────────────────────────────────────────────────────────────

    def get_portfolio(self, account_number: str = None) -> dict:
        """
        Posiciones actuales con precio de mercado y valuación.
        Devuelve el raw JSON de PPI.
        """
        try:
            params = {}
            if account_number:
                params["accountNumber"] = account_number
            return self._get("/api/Portfolio/GetPortfolio", params)
        except Exception as e:
            print(f"[PPI] Error portfolio: {e}")
            return {}

    def get_portfolio_formatted(self, account_number: str = None) -> dict:
        """
        Portfolio formateado para el sistema de análisis.
        Normaliza el JSON de PPI al formato que usa el orchestrator.
        """
        raw = self.get_portfolio(account_number)
        balance = self.get_balance(account_number)

        holdings = []
        total_ars = 0
        total_usd = 0

        # PPI puede usar distintas estructuras según versión de API
        items = (
            raw.get("Items")
            or raw.get("Positions")
            or raw.get("Holdings")
            or raw.get("Portfolio")
            or []
        )

        for item in items:
            ticker = item.get("Symbol") or item.get("Ticker") or item.get("Instrument", "")
            cantidad = item.get("Quantity") or item.get("Shares") or 0
            precio_mercado = item.get("Price") or item.get("MarketPrice") or item.get("LastPrice") or 0
            precio_compra = item.get("PurchasePrice") or item.get("AveragePrice") or 0
            valuacion = item.get("Value") or item.get("MarketValue") or (cantidad * precio_mercado)
            moneda = item.get("Currency") or item.get("Moneda") or "ARS"
            tipo = item.get("Type") or item.get("InstrumentType") or "CEDEAR"
            pnl_pct = (
                ((precio_mercado - precio_compra) / precio_compra * 100)
                if precio_compra and precio_mercado
                else None
            )

            holding = {
                "ticker": ticker,
                "tipo": tipo,
                "cantidad": cantidad,
                "precio_mercado": precio_mercado,
                "precio_compra_promedio": precio_compra,
                "valuacion": valuacion,
                "moneda": moneda,
                "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
            }
            holdings.append(holding)

            if moneda == "USD":
                total_usd += valuacion
            else:
                total_ars += valuacion

        # Saldo disponible
        cash_ars = (
            balance.get("AvailableARS")
            or balance.get("CashARS")
            or balance.get("Disponible")
            or 0
        )
        cash_usd = (
            balance.get("AvailableUSD")
            or balance.get("CashUSD")
            or balance.get("DisponibleUSD")
            or 0
        )

        return {
            "fecha": datetime.now().isoformat(),
            "fuente": "PPI API (tiempo real)",
            "cuenta": account_number,
            "holdings": holdings,
            "cash_ars": cash_ars,
            "cash_usd": cash_usd,
            "total_valorizado_ars": total_ars,
            "total_valorizado_usd": total_usd,
            "cantidad_posiciones": len(holdings),
            "_raw": raw,
        }

    # ── Movimientos / Historial ───────────────────────────────────────────────

    def get_movements(
        self,
        days_back: int = 90,
        account_number: str = None,
    ) -> list:
        """
        Historial de operaciones de los últimos N días.
        """
        try:
            date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            date_to = datetime.now().strftime("%Y-%m-%d")
            params = {"dateFrom": date_from, "dateTo": date_to}
            if account_number:
                params["accountNumber"] = account_number
            data = self._get("/api/Account/GetMovements", params)
            return data if isinstance(data, list) else data.get("Movements", [])
        except Exception as e:
            print(f"[PPI] Error movimientos: {e}")
            return []

    def get_operations(
        self,
        days_back: int = 90,
        account_number: str = None,
    ) -> list:
        """Historial de órdenes ejecutadas."""
        try:
            date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            date_to = datetime.now().strftime("%Y-%m-%d")
            params = {"dateFrom": date_from, "dateTo": date_to}
            if account_number:
                params["accountNumber"] = account_number
            data = self._get("/api/Order/GetOrders", params)
            return data if isinstance(data, list) else data.get("Orders", [])
        except Exception as e:
            print(f"[PPI] Error operaciones: {e}")
            return []

    # ── Precios de mercado ────────────────────────────────────────────────────

    def get_price(self, ticker: str, settlement: str = "T+1") -> dict:
        """
        Precio de mercado de un instrumento en BYMA.
        settlement: 'T+0', 'T+1', 'T+2'
        """
        try:
            data = self._get(
                "/api/MarketData/GetMarketData",
                {"ticker": ticker, "settlement": settlement},
            )
            return {
                "ticker": ticker,
                "precio": data.get("Price") or data.get("LastPrice") or data.get("Close"),
                "apertura": data.get("Open"),
                "maximo": data.get("High"),
                "minimo": data.get("Low"),
                "volumen": data.get("Volume"),
                "variacion_pct": data.get("Change") or data.get("VariationPct"),
                "fecha": data.get("Date") or datetime.now().strftime("%Y-%m-%d"),
            }
        except Exception as e:
            return {"ticker": ticker, "precio": None, "error": str(e)}

    def get_cedear_price(self, ticker: str) -> dict:
        """Precio de un CEDEAR en BYMA (ARS)."""
        return self.get_price(ticker, settlement="T+1")

    def get_dolar_mep(self) -> Optional[float]:
        """
        Obtiene el dólar MEP calculado desde precios de BYMA.
        Usa AL30D (con y sin retención) como referencia estándar.
        """
        try:
            # AL30 en ARS / AL30D en USD → tipo de cambio implícito
            al30_ars = self.get_price("AL30", "T+1")
            al30_usd = self.get_price("AL30D", "T+1")

            precio_ars = al30_ars.get("precio")
            precio_usd = al30_usd.get("precio")

            if precio_ars and precio_usd and precio_usd > 0:
                return round(precio_ars / precio_usd, 2)
        except Exception:
            pass
        return None


# ── Funciones de conveniencia ──────────────────────────────────────────────────

def get_ppi_client() -> Optional[PPIClient]:
    """Crea y autentica un cliente PPI desde variables de entorno."""
    try:
        client = PPIClient()
        client.authenticate()
        return client
    except PPIAuthError as e:
        print(f"[PPI] {e}")
        return None


def fetch_portfolio_from_ppi() -> dict:
    """
    Punto de entrada principal para obtener el portfolio real desde PPI.
    Retorna dict formateado o dict vacío si no hay credenciales.
    """
    client = get_ppi_client()
    if not client:
        return {}
    return client.get_portfolio_formatted()


def fetch_pnl_analysis_from_ppi(days_back: int = 90) -> dict:
    """
    Obtiene y analiza el historial de operaciones para calcular P&L real.
    """
    client = get_ppi_client()
    if not client:
        return {}

    movements = client.get_movements(days_back)
    operations = client.get_operations(days_back)

    compras = []
    ventas = []

    for op in operations:
        tipo = (op.get("Type") or op.get("OperationType") or "").upper()
        ticker = op.get("Symbol") or op.get("Ticker") or ""
        cantidad = op.get("ExecutedQuantity") or op.get("Quantity") or 0
        precio = op.get("ExecutedPrice") or op.get("Price") or 0
        monto = op.get("Amount") or (cantidad * precio)
        fecha = op.get("Date") or op.get("DateTime") or ""
        moneda = op.get("Currency") or "ARS"

        registro = {
            "ticker": ticker,
            "cantidad": cantidad,
            "precio": precio,
            "monto": monto,
            "fecha": fecha,
            "moneda": moneda,
        }

        if "COMPR" in tipo or "BUY" in tipo:
            compras.append(registro)
        elif "VENT" in tipo or "SELL" in tipo:
            ventas.append(registro)

    return {
        "periodo_dias": days_back,
        "total_operaciones": len(operations),
        "compras": compras,
        "ventas": ventas,
        "movimientos_raw": movements[:50],  # primeros 50 para no inflar
    }
