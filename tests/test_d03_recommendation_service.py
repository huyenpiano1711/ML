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


# ---------------------------------------------------------------- C02: make is a required condition
def _mixed_recommender(tesla_prices) -> Recommender:
    rows = []
    def add(make, model, year, price, fuel="gas", type_="sedan"):
        rows.append({"id": len(rows) + 1, "manufacturer": make, "model_base": model, "make_model": f"{make} {model}",
                     "year": year, "car_age": 2021 - year, "price": price, "odometer": 40_000 + len(rows) * 500,
                     "type": type_, "condition": "excellent", "fuel": fuel, "transmission": "automatic",
                     "drive": "rwd", "image_path": None, "image_match": "none"})
    for i, price in enumerate(tesla_prices):
        add("tesla", "model s", 2014 + i, price, fuel="electric")
    for i in range(8):                          # cheaper electric / similar cars of other makes
        add(["bmw", "nissan", "toyota", "ford"][i % 4], f"m{i}", 2017 + i % 3, 15_000 + i * 500, fuel="electric")
    return Recommender(pd.DataFrame(rows))


def _tesla_form(budget):
    return {"manufacturer": "tesla", "model_base": "model s", "year": 2016, "type": "sedan", "odometer": 40_000,
            "condition": "excellent", "fuel": "electric", "transmission": "automatic", "budget_max_usd": budget}


def test_top5_contains_only_the_chosen_make_when_it_has_enough_cars():
    result = recommend_vehicles(_tesla_form(40_000), recommender=_mixed_recommender([30_000] * 6))
    assert (result.cars["manufacturer"] == "tesla").all()
    assert len(result.cars) == 5


def test_other_makes_only_fill_the_missing_places_after_the_chosen_make():
    result = recommend_vehicles(_tesla_form(20_000), recommender=_mixed_recommender([18_000, 19_500, 35_000]))
    makes = result.cars["manufacturer"].tolist()
    assert makes[:2] == ["tesla", "tesla"] and "tesla" not in makes[2:]
    assert len(makes) == 5 and result.cars["rank"].tolist() == [1, 2, 3, 4, 5]
    assert (result.cars["price"] <= 20_000).all()
    assert result.cars["id"].is_unique
    assert result.warnings[0].startswith("Chỉ có 2 xe Tesla có giá không vượt quá 20.000 USD")


def test_no_car_of_the_make_in_budget_gives_other_makes_with_a_warning():
    result = recommend_vehicles(_tesla_form(20_000), recommender=_mixed_recommender([45_000, 50_000]))
    assert len(result.cars) == 5 and "tesla" not in result.cars["manufacturer"].tolist()
    assert result.warnings[0].startswith("Không có xe Tesla nào có giá không vượt quá 20.000 USD")
