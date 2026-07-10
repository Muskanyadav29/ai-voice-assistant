"""Fetch trips from the Trvios AI trips API."""

from __future__ import annotations

import re

import httpx

from clean_app.domain.entities.trip import ItineraryItem, Trip
from clean_app.domain.repositories.trip_repository import TripRepository

_DURATION_PATTERN = re.compile(r"(\d+)\s*days?", re.IGNORECASE)


class TrviosTripRepository(TripRepository):
    """Trip repository backed by the Trvios external API."""

    def __init__(self, api_url: str, timeout_seconds: float = 30.0) -> None:
        self._api_url = api_url
        self._timeout_seconds = timeout_seconds
        self._trips: list[Trip] | None = None

    def get_all(self) -> list[Trip]:
        if self._trips is None:
            self._trips = self._fetch_trips()
        return list(self._trips)

    def get_by_id(self, trip_id: str) -> Trip | None:
        for trip in self.get_all():
            if trip.id == trip_id:
                return trip
        return None

    def _fetch_trips(self) -> list[Trip]:
        import json
        import time
        from pathlib import Path
        from clean_app.infrastructure.config.logging import get_logger

        logger = get_logger(__name__)
        cache_file = Path("data/cached_trips.json")

        # Create directories if they do not exist
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        max_retries = 3
        backoff_factor = 2.0
        current_delay = 1.0
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Fetching trips from Trvios API (attempt {attempt}/{max_retries})...")
                response = httpx.get(self._api_url, timeout=self._timeout_seconds)
                response.raise_for_status()
                payload = response.json()

                if not payload.get("success"):
                    raise RuntimeError("Trvios trips API returned success=false")

                raw_trips = payload.get("data", [])
                if not isinstance(raw_trips, list):
                    raise RuntimeError("Trvios trips API returned invalid data payload")

                # Cache successful response payload as backup
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2, ensure_ascii=False)
                    logger.info("Successfully updated cached_trips.json backup.")
                except Exception as e:
                    logger.warning(f"Failed to save backup cache file: {e}")

                return [_map_trvios_trip(item) for item in raw_trips]

            except Exception as e:
                last_error = e
                logger.error(f"Attempt {attempt} failed to fetch trips: {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {current_delay:.1f} seconds...")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
                else:
                    logger.error("All attempts to fetch trips from API failed.")

        # If we got here, all attempts failed. Try to load from backup cache.
        if cache_file.exists():
            logger.warning(f"Attempting to load trips from local backup cache: {cache_file}")
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                
                raw_trips = payload.get("data", [])
                if not isinstance(raw_trips, list):
                    raise RuntimeError("Invalid data structure in backup cache")
                
                logger.info(f"Successfully loaded {len(raw_trips)} trips from local backup cache.")
                return [_map_trvios_trip(item) for item in raw_trips]
            except Exception as cache_err:
                logger.error(f"Failed to load from backup cache: {cache_err}")
                raise RuntimeError(f"Failed to fetch trips from API and backup cache is unavailable: {cache_err}") from last_error
        else:
            logger.error("No local backup cache found.")
            raise RuntimeError("Failed to fetch trips from API and no local backup cache exists.") from last_error


def _map_trvios_trip(item: dict[str, object]) -> Trip:
    states = item.get("states", [])
    state = states[0] if isinstance(states, list) and states else "India"

    highlights_raw = item.get("highlights", [])
    highlights = tuple(str(h) for h in highlights_raw) if isinstance(highlights_raw, list) else ()

    if highlights:
        description = ". ".join(highlights)
    else:
        description = str(item.get("title", "Trip"))

    tags_raw = item.get("tags", [])
    tags = tuple(str(tag) for tag in tags_raw) if isinstance(tags_raw, list) else ()

    seasons = item.get("seasons", [])
    start_date = str(seasons[0]) if isinstance(seasons, list) and seasons else ""

    price_raw = item.get("discountPrice", item.get("price", 0))
    price = float(price_raw) if price_raw is not None else 0.0

    itinerary_raw = item.get("itinerary", [])
    itinerary_items = []
    if isinstance(itinerary_raw, list):
        for day_item in itinerary_raw:
            if not isinstance(day_item, dict):
                continue
            day = int(day_item.get("day", 1))
            title = str(day_item.get("title", ""))
            desc = str(day_item.get("description", ""))
            
            activities_raw = day_item.get("activities", [])
            activities = tuple(str(act) for act in activities_raw) if isinstance(activities_raw, list) else ()
            
            location = day_item.get("location", {})
            formatted_address = ""
            if isinstance(location, dict):
                formatted_address = str(location.get("formattedAddress", ""))
                
            itinerary_items.append(
                ItineraryItem(
                    day=day,
                    title=title,
                    description=desc,
                    activities=activities,
                    formatted_address=formatted_address,
                )
            )

    return Trip(
        id=str(item.get("_id", "")),
        title=str(item.get("title", "")),
        destination=str(item.get("destination", "")),
        country=str(state),
        duration_days=_parse_duration_days(str(item.get("duration", ""))),
        price=price,
        currency="INR",
        description=description,
        tags=tags,
        start_date=start_date,
        highlights=highlights,
        itinerary=tuple(itinerary_items),
    )



def _parse_duration_days(duration: str) -> int:
    match = _DURATION_PATTERN.search(duration)
    if match:
        return int(match.group(1))
    return 1
