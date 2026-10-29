"""Tests for the D03 Backend adapter to the recommendation algorithm."""
from __future__ import annotations

import pandas as pd
import pytest

from backend.schemas.result_schema import CarCard
from backend.schemas.vehicle_input import InputValidationError, VehicleInput
from backend.services.recommendation_service import recommend_vehicles
from src.recommendation.recommend import RecommendationResult, Recommender


def _valid_form() -> dict[str, object]:
    return {
        "manufacturer": "ford",
        "model_base": "f150",
        "year": 2018,
        "type": "pickup",
        "odometer": 60_000,
        "condition": "good",
        "fuel": "gas",
        "transmission": "automatic",
        "budget_max_usd": 25_000,
    }


def _recommender() -> Recommender:
    catalog = pd.DataFrame([
        {
            "id": index,
            "manufacturer": "ford",
            "model_base": "f150",
            "make_model": "ford f150",
            "year": year,
            "car_age": 2021 - year,
            "price": price,
            "odometer": 60_000 + index * 1_000,
            "type": "pickup",
            "condition": "good",
            "fuel": "gas",
            "transmission": "automatic",
            "drive": "4wd",
            "image_path": None,
            "image_match": "none",
        }
        for index, (year, price) in enumerate(
            [(2018, 24_000), (2017, 22_000), (2016, 20_000), (2015, 18_000), (2014, 16_000), (2013, 14_000)],
            start=1,
        )
    ])
    return Recommender(catalog)


def test_recommend_vehicles_returns_top_five_cards_within_budget():
    result = recommend_vehicles(_valid_form(), recommender=_recommender())

    assert isinstance(result, RecommendationResult)
    assert len(result.cars) == 5
    assert (result.cars["price"] <= 25_000).all()
    assert result.cars["rank"].tolist() == [1, 2, 3, 4, 5]
    cards = result.to_cards()
    assert all(isinstance(card, CarCard) for card in cards)
    assert all(card.price <= 25_000 for card in cards)


def test_recommend_vehicles_accepts_validated_vehicle_input():
    vehicle = VehicleInput.from_dict(_valid_form()).check()

    result = recommend_vehicles(vehicle, recommender=_recommender())

    assert len(result.cars) == 5
    assert result.method == "knn"


def test_recommend_vehicles_uses_backend_recommender_loader(monkeypatch):
    monkeypatch.setattr(
        "backend.services.recommendation_service.get_recommender",
        _recommender,
    )

    result = recommend_vehicles(_valid_form())

    assert len(result.cars) == 5


def test_recommend_vehicles_rejects_invalid_form():
    invalid_form = {**_valid_form(), "year": 1980}

    with pytest.raises(InputValidationError):
        recommend_vehicles(invalid_form, recommender=_recommender())


def test_recommend_vehicles_preserves_empty_result_warning():
    vehicle = {**_valid_form(), "budget_max_usd": 1_000}

    result = recommend_vehicles(vehicle, recommender=_recommender())

    assert result.cars.empty
    assert result.n_candidates == 0
    assert result.warnings
