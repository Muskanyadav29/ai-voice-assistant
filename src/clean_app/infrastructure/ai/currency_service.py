"""Currency converter service that fetches live rates from open.er-api.com."""

import httpx
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


class CurrencyService:
    """Service to fetch live currency conversion rates with INR as base."""

    def __init__(self) -> None:
        self._url = "https://open.er-api.com/v6/latest/INR"

    async def get_conversion_rates(self) -> dict[str, float]:
        """Fetch current exchange rates for INR base. Defaults to static fallbacks if offline."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self._url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    rates = data.get("rates", {})
                    logger.info("Successfully fetched live exchange rates from open.er-api.com")
                    return {
                        "USD": rates.get("USD", 0.012),
                        "EUR": rates.get("EUR", 0.011),
                        "GBP": rates.get("GBP", 0.0094),
                    }
        except Exception as e:
            logger.warning(f"Error fetching live exchange rates: {e}. Using static fallbacks.")
        
        # Fallback values
        return {"USD": 0.012, "EUR": 0.011, "GBP": 0.0094}

    async def convert_inr_to(self, amount: float, target_currency: str) -> float:
        """Convert an amount from INR to USD, EUR, or GBP."""
        rates = await self.get_conversion_rates()
        rate = rates.get(target_currency.upper(), 0.012)
        return round(amount * rate, 2)
