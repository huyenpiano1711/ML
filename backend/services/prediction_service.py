"""Backend adapter for the AutoWise price prediction model."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from backend.schemas.result_schema import PriceResult
from backend.schemas.vehicle_input import VehicleInput
from src.prediction.predict import DEFAULT_MODEL_PATH, predict_price

PROJECT_DIR = Path(__file__).resolve().parents[2]
METRICS_PATH = PROJECT_DIR / "models" / "price_prediction" / "metrics.json"


def _test_mae(metrics_path: str | Path = METRICS_PATH) -> float | None:
    path = Path(metrics_path)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = data.get("test_metrics", {}).get("mae_usd")
    return None if value is None else float(value)


def predict_vehicle_price(
    vehicle: VehicleInput | Mapping[str, object],
    model_path: str | Path = DEFAULT_MODEL_PATH,
    metrics_path: str | Path = METRICS_PATH,
) -> PriceResult:
    """Return the frontend contract, with a test-MAE reference interval when available."""
    predicted = predict_price(vehicle, model_path=model_path)
    mae = _test_mae(metrics_path)
    return PriceResult(
        predicted_price=round(predicted, 2),
        price_low=None if mae is None else round(max(100.0, predicted - mae), 2),
        price_high=None if mae is None else round(predicted + mae, 2),
        model_name="HistGradientBoostingRegressor",
    )

