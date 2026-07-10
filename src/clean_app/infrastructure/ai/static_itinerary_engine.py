import json
from pathlib import Path

DEFAULT_TEMPLATES_FILE = Path(__file__).resolve().parent.parent / "data" / "itinerary_templates.json"


class StaticItineraryEngine:
    """Service to load and slice static itineraries for destinations."""

    def __init__(self, templates_file: Path | None = None) -> None:
        self.templates_file = templates_file or DEFAULT_TEMPLATES_FILE
        self._templates = self._load_templates()

    def _load_templates(self) -> dict:
        if not self.templates_file.exists():
            print(f"Itinerary templates file not found at: {self.templates_file}")
            return {}
        try:
            return json.loads(self.templates_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error loading itinerary templates: {e}")
            return {}

    async def get_template(self, destination: str, days: int) -> dict:
        """Find the template for a destination, and slice/pad it to fit the requested day count."""
        dest_key = destination.strip().lower()
        template = self._templates.get(dest_key)

        if not template:
            # Fallback template generation
            return {
                "destination": destination,
                "days": [
                    {
                        "day": i + 1,
                        "title": f"Explore {destination} - Day {i + 1}",
                        "description": f"Discover the local attractions, scenic views, and local experiences of {destination}."
                    }
                    for i in range(days)
                ]
            }

        days_list = template.get("days", [])
        if not days_list:
            return {"destination": template.get("destination", destination), "days": []}

        if len(days_list) >= days:
            sliced_days = days_list[:days]
        else:
            sliced_days = list(days_list)
            while len(sliced_days) < days:
                next_day_num = len(sliced_days) + 1
                sliced_days.append({
                    "day": next_day_num,
                    "title": f"Discover more in {destination} - Day {next_day_num}",
                    "description": f"Continue exploring the sights, local food, and unique activities of {destination}."
                })

        return {
            "destination": template.get("destination", destination),
            "days": sliced_days
        }
