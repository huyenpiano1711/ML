"""Automated tests for the D01 frontend/backend data contract."""
from __future__ import annotations

import json

import pytest

from backend.schemas.result_schema import AnalysisResult, CarCard, PriceResult
from backend.schemas.vehicle_input import InputValidationError, VehicleInput


def _valid_form() -> dict[str, object]:
    return {
        "user_name": "Duy",
        "manufacturer": "Ford",
        "model_base": "f150",
        "year": "2015",
        "type": "pickup",
        "odometer": 60_000,
        "condition": "good",
        "fuel": "gas",
        "transmission": "automatic",
        "budget_max_usd": 20_000,
        "drive": "",
    }


def test_vehicle_input_normalizes_and_builds_model_row():
    vehicle = VehicleInput.from_dict(_valid_form()).check()

    assert vehicle.manufacturer == "ford"
    assert vehicle.year == 2015
    assert vehicle.drive is None
    assert vehicle.title == "Ford F150 2015"

    model_row = vehicle.to_model_row()
    assert "budget_max_usd" not in model_row
    assert model_row["manufacturer"] == "ford"
    assert model_row["drive"] == "unknown"


def test_vehicle_input_builds_recommendation_query():
    vehicle = VehicleInput.from_dict(_valid_form()).check()
    query = vehicle.to_recommendation_query()

    assert query["budget_max_usd"] == 20_000
    assert query["preferences"]["manufacturer"] == "ford"
    assert "user_name" not in query["preferences"]


def test_vehicle_input_rejects_all_invalid_fields():
    invalid = VehicleInput.from_dict({
        "manufacturer": "ford",
        "model_base": "camry",
        "year": 1980,
        "type": "boat",
        "odometer": "abc",
        "condition": "good",
        "fuel": "gas",
        "transmission": "automatic",
    })

    with pytest.raises(InputValidationError) as exc_info:
        invalid.check()

    assert len(exc_info.value.errors) == 5


def test_analysis_result_is_json_serializable():
    vehicle = VehicleInput.from_dict(_valid_form()).check()
    card = CarCard.from_row({
        "id": 7_301_583_321,
        "manufacturer": "dodge",
        "model_base": "durango",
        "year": 2013,
        "price": 18_997,
        "odometer": 96_475,
        "type": "suv",
        "condition": "excellent",
        "fuel": "gas",
        "transmission": "automatic",
    }, score=0.92)
    result = AnalysisResult(
        success=True,
        vehicle_title=vehicle.title,
        price=PriceResult(
            predicted_price=18_500,
            model_name="HistGradientBoostingRegressor",
        ),
        top_matches=[card],
    )

    payload = result.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)

    assert json.loads(encoded)["success"] is True
    assert payload["price"]["currency"] == "USD"
    assert payload["top_matches"][0]["score"] == pytest.approx(0.92)
    assert AnalysisResult.failure(["invalid input"]).success is False
