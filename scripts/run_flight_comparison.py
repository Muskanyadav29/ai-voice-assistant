"""Standalone Flight Price Aggregator Script demonstrating parallel polling across providers."""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class FlightOffer:
    provider_name: str
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price_inr: float
    deep_link: str


class AmadeusAdapter:
    """Simulated Amadeus GDS API Adapter."""

    async def fetch_offers(self, origin: str, dest: str, date: str) -> list[FlightOffer]:
        await asyncio.sleep(0.3)
        return [
            FlightOffer(
                provider_name="Amadeus GDS",
                airline="Air India",
                flight_number="AI-101",
                origin=origin,
                destination=dest,
                departure_time=f"{date}T08:00:00",
                arrival_time=f"{date}T10:15:00",
                price_inr=5400.0,
                deep_link=f"https://airindia.com/select?from={origin}&to={dest}"
            )
        ]


class DuffelAdapter:
    """Simulated Duffel NDC API Adapter."""

    async def fetch_offers(self, origin: str, dest: str, date: str) -> list[FlightOffer]:
        await asyncio.sleep(0.2)
        return [
            FlightOffer(
                provider_name="Duffel NDC",
                airline="IndiGo",
                flight_number="6E-205",
                origin=origin,
                destination=dest,
                departure_time=f"{date}T09:30:00",
                arrival_time=f"{date}T11:45:00",
                price_inr=4800.0,
                deep_link=f"https://goindigo.in/booking?from={origin}&to={dest}"
            )
        ]


class MakeMyTripAdapter:
    """Simulated MakeMyTrip OTA API Adapter."""

    async def fetch_offers(self, origin: str, dest: str, date: str) -> list[FlightOffer]:
        await asyncio.sleep(0.4)
        return [
            FlightOffer(
                provider_name="MakeMyTrip OTA",
                airline="IndiGo",
                flight_number="6E-205",
                origin=origin,
                destination=dest,
                departure_time=f"{date}T09:30:00",
                arrival_time=f"{date}T11:45:00",
                price_inr=4650.0,  # Cheaper OTA deal
                deep_link=f"https://makemytrip.com/flights?from={origin}&to={dest}"
            ),
            FlightOffer(
                provider_name="MakeMyTrip OTA",
                airline="Vistara",
                flight_number="UK-945",
                origin=origin,
                destination=dest,
                departure_time=f"{date}T14:00:00",
                arrival_time=f"{date}T16:15:00",
                price_inr=6100.0,
                deep_link=f"https://makemytrip.com/flights?from={origin}&to={dest}"
            )
        ]


class FlightPriceComparisonEngine:
    """Parallel flight aggregator engine."""

    def __init__(self) -> None:
        self.adapters = [
            AmadeusAdapter(),
            DuffelAdapter(),
            MakeMyTripAdapter()
        ]

    async def search_and_compare(self, origin: str, destination: str, date: str) -> dict[str, Any]:
        start_time = time.time()
        
        # Parallel async fan-out polling
        tasks = [adapter.fetch_offers(origin, destination, date) for adapter in self.adapters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_offers: list[FlightOffer] = []
        for res in results:
            if isinstance(res, list):
                all_offers.extend(res)

        # Group by flight number for deduplication
        grouped: dict[str, list[FlightOffer]] = {}
        for offer in all_offers:
            key = f"{offer.airline}_{offer.flight_number}"
            grouped.setdefault(key, []).append(offer)

        # Sort prices for each flight
        compared_flights = []
        for key, offers in grouped.items():
            sorted_offers = sorted(offers, key=lambda x: x.price_inr)
            best = sorted_offers[0]
            compared_flights.append({
                "flight_key": key,
                "airline": best.airline,
                "flight_number": best.flight_number,
                "departure": best.departure_time,
                "arrival": best.arrival_time,
                "cheapest_price_inr": best.price_inr,
                "best_provider": best.provider_name,
                "all_provider_prices": [
                    {
                        "provider": o.provider_name,
                        "price_inr": o.price_inr,
                        "deep_link": o.deep_link
                    }
                    for o in sorted_offers
                ]
            })

        compared_flights.sort(key=lambda x: x["cheapest_price_inr"])
        elapsed = round((time.time() - start_time) * 1000, 2)

        return {
            "status": "success",
            "query": {"origin": origin, "destination": destination, "date": date},
            "latency_ms": elapsed,
            "total_flights_found": len(compared_flights),
            "flights": compared_flights
        }


if __name__ == "__main__":
    print("Executing Flight Price Comparison Engine...")
    engine = FlightPriceComparisonEngine()
    output = asyncio.run(engine.search_and_compare("DEL", "BOM", "2026-10-15"))
    print("\n--- Aggregated Flight Price Comparison Results ---")
    print(json.dumps(output, indent=2))
