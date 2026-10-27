"""Backend adapter for finding cars near the predicted price."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from src.recommendation.recommend import RecommendationResult, Recommender, get_recommender


def find_similar_price_vehicles(
    predicted_price: float,
    *,
    exclude_ids: Iterable[int] = (),
    preferences: Mapping[str, object] | None = None,
    recommender: Recommender | None = None,
) -> RecommendationResult:
    """Find catalog cars near the prediction, excluding the existing Top matches."""
    engine = recommender if recommender is not None else get_recommender()
    return engine.similar_price(
        predicted_price,
        exclude_ids=tuple(int(car_id) for car_id in exclude_ids),
        preferences=None if preferences is None else dict(preferences),
    )
