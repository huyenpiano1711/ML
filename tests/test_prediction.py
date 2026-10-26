"""B07 integration checks for model inference and the backend adapter."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import pytest

from backend.schemas.vehicle_input import InputValidationError, VehicleInput
from backend.services.prediction_service import predict_vehicle_price
from src.prediction.predict import DEFAULT_MODEL_PATH, load_pipeline, predict_price

PROJECT_DIR = Path(__file__).resolve().parents[1]
METRICS_PATH = PROJECT_DIR / "models" / "price_prediction" / "metrics.json"


@pytest.fixture(scope="module")
def valid_form():
    return {
        "manufacturer": "ford", "model_base": "f150", "year": 2018,
        "type": "pickup", "odometer": 60000, "condition": "good",
        "fuel": "gas", "transmission": "automatic", "budget_max_usd": 25000,
        "drive": "4wd", "cylinders": "6 cylinders", "paint_color": "white",
        "title_status": "clean", "state": "ca",
    }


def test_saved_pipeline_loads_and_predicts_without_training(valid_form):
    assert DEFAULT_MODEL_PATH.is_file()
    model = joblib.load(DEFAULT_MODEL_PATH)
    row = pd.DataFrame([VehicleInput.from_dict(valid_form).check().to_model_row()])
    assert float(model.predict(row)[0]) > 0


def test_predict_function_and_backend_are_consistent(valid_form):
    load_pipeline.cache_clear()
    direct = predict_price(valid_form)
    result = predict_vehicle_price(valid_form)
    assert result.predicted_price == pytest.approx(direct, abs=0.01)
    assert result.currency == "USD"
    assert result.price_low < result.predicted_price < result.price_high


def test_budget_is_not_a_model_feature(valid_form):
    low = {**valid_form, "budget_max_usd": 5000}
    high = {**valid_form, "budget_max_usd": 100000}
    assert predict_price(low) == pytest.approx(predict_price(high))


def test_invalid_ui_input_is_rejected(valid_form):
    with pytest.raises(InputValidationError):
        predict_price({**valid_form, "year": 1980})


def test_metrics_match_independent_test_contract():
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    test_metrics = metrics["test_metrics"]
    assert test_metrics["sample_size"] == 29778
    assert all(test_metrics[key] >= 0 for key in ("mae_usd", "rmse_usd", "medae_usd"))
    assert -1 <= test_metrics["r2_usd"] <= 1
