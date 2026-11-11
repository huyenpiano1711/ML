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
    test_ids = pd.read_csv(PROJECT_DIR / "data" / "splits" / "test_ids.csv")["id"]
    assert test_metrics["sample_size"] == len(test_ids)
    assert metrics["test_metrics_app_path"]["sample_size"] == len(test_ids)
    assert metrics["interval"]["bins"] and metrics["app_mae_usd"] >= test_metrics["mae_usd"] * 0.9
    assert all(test_metrics[key] >= 0 for key in ("mae_usd", "rmse_usd", "medae_usd"))
    assert -1 <= test_metrics["r2_usd"] <= 1


def test_backend_rejects_impossible_mileage(valid_form):
    """Quy tắc số dặm nằm ở VehicleInput.validate() (không chỉ ở giao diện) - review ML-07."""
    errors = VehicleInput.from_dict({**valid_form, "year": 2021, "odometer": 400_000}).validate()
    assert any(e.startswith("Số dặm ") for e in errors)
    errors = VehicleInput.from_dict({**valid_form, "condition": "new", "odometer": 150_000, "year": 2015}).validate()
    assert any(e.startswith("Xe tình trạng 'new'") for e in errors)


def test_price_range_depends_on_price_level(valid_form):
    """Khoảng giá lấy từ bảng phân vị theo mức giá (review ML-05): xe đắt có khoảng rộng hơn xe rẻ."""
    from backend.services.prediction_service import price_interval
    low_lo, low_hi = price_interval(5_000)
    high_lo, high_hi = price_interval(60_000)
    assert low_lo < 5_000 < low_hi and high_lo < 60_000 < high_hi
    assert (high_hi - high_lo) > (low_hi - low_lo)
