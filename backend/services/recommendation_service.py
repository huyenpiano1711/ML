"""Backend adapter for the AutoWise vehicle recommendation system."""
from __future__ import annotations

from typing import Mapping

from backend.schemas.vehicle_input import VehicleInput
from src.recommendation.recommend import RecommendationResult, Recommender, get_recommender


def recommend_vehicles(
    vehicle: VehicleInput | Mapping[str, object],
    *,
    recommender: Recommender | None = None,
) -> RecommendationResult:
    """Return recommended catalog cars for a validated form submission."""
    item = vehicle if isinstance(vehicle, VehicleInput) else VehicleInput.from_dict(dict(vehicle))
    item.check()
    engine = recommender if recommender is not None else get_recommender()
    return engine.recommend(item.to_recommendation_query())
