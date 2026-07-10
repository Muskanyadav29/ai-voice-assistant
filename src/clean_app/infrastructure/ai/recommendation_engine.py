"""Travel recommendation and filtering engine implementation."""

from clean_app.domain.entities.trip import Trip
from clean_app.domain.repositories.vector_store import TripSearchResult
from clean_app.infrastructure.ai.intent_ner_service import ParsedEntities


class RecommendationEngine:
    """Ranks and filters trips using metadata, budget, duration, and semantic criteria."""

    def recommend_trips(self, all_trips: list[Trip], entities: ParsedEntities, top_n: int = 3) -> list[TripSearchResult]:
        """Perform custom metadata scoring and filtering to find optimal trips."""
        scored_trips = []

        for trip in all_trips:
            score = 1.0  # Base similarity/matching score
            matched = True

            # 1. Mood match
            if entities.mood:
                mood_lower = entities.mood.lower()
                trip_tags_and_desc = [t.lower() for t in trip.tags] + trip.description.lower().split()
                if any(mood_lower in t for t in trip_tags_and_desc):
                    score += 4.0

            # 2. Destination / Country filter
            if entities.destination:
                dest = entities.destination.lower()
                trip_dest = trip.destination.lower()
                trip_country = trip.country.lower()
                if dest in trip_dest or dest in trip_country or trip_dest in dest:
                    score += 5.0
                else:
                    # If destination is explicitly specified but doesn't match, penalize
                    score -= 2.0

            # 2. Budget filter
            if entities.max_budget is not None:
                # Give a boost to trips within budget, and heavily penalize trips above budget
                if trip.price <= entities.max_budget:
                    score += 3.0
                    # Additional minor boost for being close to budget (not leaving too much money on the table)
                    score += (trip.price / entities.max_budget) * 0.5
                else:
                    # Let's keep trips slightly above budget (+15% max) but penalize them heavily
                    # Trips more than 15% over budget are completely filtered out
                    if trip.price <= entities.max_budget * 1.15:
                        score -= 4.0
                    else:
                        matched = False

            # 3. Duration filter
            if entities.duration_days is not None:
                diff = abs(trip.duration_days - entities.duration_days)
                if diff == 0:
                    score += 2.0
                elif diff <= 2:
                    score += 1.0
                else:
                    score -= 1.0

            # 4. Tags / Activities filter
            if entities.activities:
                matches = 0
                trip_tags_and_highlights = [t.lower() for t in trip.tags] + [h.lower() for h in trip.highlights]
                for act in entities.activities:
                    act_lower = act.lower()
                    # Check substring match in tags or highlights
                    if any(act_lower in tag for tag in trip_tags_and_highlights):
                        matches += 1
                
                if matches > 0:
                    score += matches * 1.5
                else:
                    # No activities match
                    score -= 1.0

            if matched:
                scored_trips.append((trip, score))

        # Sort by score descending
        scored_trips.sort(key=lambda x: x[1], reverse=True)

        results = [
            TripSearchResult(trip=trip, score=float(score))
            for trip, score in scored_trips[:top_n]
        ]
        return results
