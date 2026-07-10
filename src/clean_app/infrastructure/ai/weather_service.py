import httpx


def map_weather_code(code: int) -> str:
    """Map weather codes to human-readable weather conditions."""
    mapping = {
        0: "Clear Sky",
        1: "Mainly Clear", 
        2: "Partly Cloudy", 
        3: "Overcast",
        45: "Fog", 
        48: "Depositing Rime Fog",
        51: "Light Drizzle", 
        53: "Moderate Drizzle", 
        55: "Dense Drizzle",
        61: "Slight Rain", 
        63: "Moderate Rain", 
        65: "Heavy Rain",
        71: "Slight Snowfall", 
        73: "Moderate Snowfall", 
        75: "Heavy Snowfall",
        80: "Slight Rain Showers", 
        81: "Moderate Rain Showers", 
        82: "Violent Rain Showers",
        95: "Thunderstorm", 
        96: "Thunderstorm with slight hail", 
        99: "Thunderstorm with heavy hail"
    }
    return mapping.get(code, "Unknown/Moderate")


class WeatherService:
    """Service to fetch real-time weather information from Open-Meteo."""

    async def get_weather(self, lat: float, lng: float) -> dict:
        """Fetch current weather using latitude and longitude."""
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "current_weather": "true"
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    current = data.get("current_weather", {})
                    temp = current.get("temperature")
                    code = current.get("weathercode", 0)
                    condition = map_weather_code(code)
                    return {
                        "temperature": f"{temp}°C" if temp is not None else "N/A",
                        "condition": condition
                    }
        except Exception as e:
            print(f"Error fetching weather: {e}")
        return {"temperature": "N/A", "condition": "Unknown"}

    async def get_mock_weather(self, destination: str) -> dict:
        """Fallback mock weather when coordinates can't be fetched."""
        return {"temperature": "22°C", "condition": "Partly Cloudy (Estimated)"}
