"""Tests for the D04 Backend adapter to similar-price recommendations."""
from __future__ import annotations

import pandas as pd

from backend.schemas.result_schema import CarCard, MAX_ALTERNATIVES
from backend.services.alternative_service import find_similar_price_vehicles
from src.recommendation.recommend import RecommendationResult, Recommender


def _recommender() -> Recommender:
    prices = [19_800, 20_200, 19_500, 20_500, 17_000, 23_000, 15_000, 18_000, 22_000]
    catalog = pd.DataFrame([
        {
            "id": index,
            "manufacturer": "ford",
            "model_base": f"model{index}",
            "make_model": f"ford model{index}",
            "year": 2018,
            "car_age": 3,
            "price": price,
            "odometer": 60_000,
            "type": "pickup",
            "condition": "good",
            "fuel": "gas",
            "transmission": "automatic",
            "drive": "4wd",
            "image_path": None,
            "image_match": "none",
        }
        for index, price in enumerate(prices, start=1)
    ])
    return Recommender(catalog)


def test_finds_up_to_six_similar_price_cars_and_excludes_top_matches():
    result = find_similar_price_vehicles(
        20_000,
        exclude_ids=[1, 2],
        recommender=_recommender(),
    )

    assert isinstance(result, RecommendationResult)
    assert len(result.cars) == MAX_ALTERNATIVES
    assert not {1, 2}.intersection(result.cars["id"])
    assert (result.cars["price"].between(14_000, 26_000)).all()
    assert any("mở rộng khoảng giá" in warning for warning in result.warnings)
    cards = result.to_cards()
    assert all(isinstance(card, CarCard) for card in cards)
    assert all(card.score is None for card in cards)


def test_returns_warning_when_no_catalog_cars_are_near_prediction():
    result = find_similar_price_vehicles(
        100_000,
        recommender=_recommender(),
    )

    assert result.cars.empty
    assert result.n_candidates == 0
    assert result.warnings


def test_uses_backend_recommender_loader(monkeypatch):
    monkeypatch.setattr(
        "backend.services.alternative_service.get_recommender",
        _recommender,
    )

    result = find_similar_price_vehicles(20_000)

    assert len(result.cars) == MAX_ALTERNATIVES
