import httpx
from clean_app.infrastructure.config.settings import Settings


class GooglePlacesService:
    """Service to fetch hotels, attractions, and restaurants in a destination using Google Places API."""

    def __init__(self, settings: Settings) -> None:
        # Default key provided by user, check settings or fallback
        self.api_key = getattr(settings, "google_places_api_key", "AIzaSyCcJn4CxZmLGoNXB2G10XV2N4K_gqRK6ww")

    async def get_places(self, destination: str, query_type: str, limit: int = 5) -> list[dict]:
        """Fetch places matching query_type (hotels, attractions, restaurants) in a destination."""
        if not self.api_key:
            print("Google Places API Key is missing.")
            return []

        if query_type == "hotels":
            query = f"hotels in {destination}"
        elif query_type == "attractions":
            query = f"tourist attractions in {destination}"
        elif query_type == "restaurants":
            query = f"restaurants in {destination}"
        else:
            query = f"{query_type} in {destination}"

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "key": self.api_key
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    places = []
                    for item in results[:limit]:
                        photo_ref = None
                        photos = item.get("photos", [])
                        if photos and isinstance(photos, list):
                            photo_ref = photos[0].get("photo_reference")
                        places.append({
                            "name": item.get("name"),
                            "rating": item.get("rating"),
                            "address": item.get("formatted_address"),
                            "price_level": item.get("price_level"),
                            "photo_reference": photo_ref,
                        })
                    return places
                else:
                    print(f"Places API returned status: {response.status_code}")
        except Exception as e:
            print(f"Error fetching Google Places for {query}: {e}")
        return []

    async def get_coordinates(self, destination: str) -> tuple[float, float] | None:
        """Fetch latitude and longitude coordinates for a destination name."""
        if not self.api_key:
            return None

        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": destination,
            "key": self.api_key
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    if results:
                        location = results[0].get("geometry", {}).get("location", {})
                        lat = location.get("lat")
                        lng = location.get("lng")
                        if lat is not None and lng is not None:
                            return (lat, lng)
        except Exception as e:
            print(f"Error getting coordinates for {destination}: {e}")
        return None
