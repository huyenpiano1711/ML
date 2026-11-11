"""Backend adapter for the AutoWise price prediction model."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from backend.schemas.result_schema import CarCard, PriceResult
from backend.schemas.vehicle_input import VehicleInput
from src.prediction.predict import DEFAULT_MODEL_PATH, predict_price, predict_prices

PROJECT_DIR = Path(__file__).resolve().parents[2]
METRICS_PATH = PROJECT_DIR / "models" / "price_prediction" / "metrics.json"


def _metrics(metrics_path: str | Path = METRICS_PATH) -> dict:
    path = Path(metrics_path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _test_mae(metrics_path: str | Path = METRICS_PATH) -> float | None:
    """Sai số trung bình người dùng gặp (MAE theo đường của ứng dụng); bản cũ chỉ có test_metrics.mae_usd."""
    data = _metrics(metrics_path)
    value = data.get("app_mae_usd", data.get("test_metrics", {}).get("mae_usd"))
    return None if value is None else float(value)


def price_interval(predicted: float, metrics_path: str | Path = METRICS_PATH) -> tuple[float, float] | None:
    """Khoảng giá ~80%: tỷ lệ giá thật / giá dự đoán ở phân vị 10% và 90% trên tập validation,
    theo mức giá dự đoán (xe rẻ, xe đắt có sai số khác nhau). Không có bảng -> ± MAE như bản cũ."""
    data = _metrics(metrics_path)
    table = data.get("interval")
    if table and table.get("bins"):
        for row in table["bins"]:
            if row.get("upper_pred_usd") is None or predicted <= row["upper_pred_usd"]:
                return max(100.0, predicted * row["low_ratio"]), predicted * row["high_ratio"]
    mae = _test_mae(metrics_path)
    return None if mae is None else (max(100.0, predicted - mae), predicted + mae)


def predict_vehicle_price(
    vehicle: VehicleInput | Mapping[str, object],
    model_path: str | Path = DEFAULT_MODEL_PATH,
    metrics_path: str | Path = METRICS_PATH,
) -> PriceResult:
    """Return the frontend contract with a validation-based ~80% price range when available."""
    predicted = predict_price(vehicle, model_path=model_path)
    interval = price_interval(predicted, metrics_path)
    return PriceResult(
        predicted_price=round(predicted, 2),
        price_low=None if interval is None else round(interval[0], 2),
        price_high=None if interval is None else round(interval[1], 2),
        model_name=_metrics(metrics_path).get("model_name", "HistGradientBoostingRegressor"),
    )


# Fields of a CarCard the price model reads; "unknown" in the catalog -> left empty, so VehicleInput fills
# the same default as for an empty field of the form.
CARD_MODEL_FIELDS = ("type", "condition", "fuel", "transmission", "title_status", "state")
ANY_BUDGET = 10_000           # the model does not read the budget; VehicleInput only needs a valid value


def estimate_card_prices(cards: list[CarCard], model_path: str | Path = DEFAULT_MODEL_PATH) -> list[float | None]:
    """What the price model estimates for each recommended listing itself (its own year, mileage, title...),
    so the interface can say when an asking price is far below what such a car usually costs."""
    vehicles = []
    for card in cards:
        item = {"manufacturer": card.manufacturer, "model_base": card.model_base, "year": card.year,
                "odometer": card.odometer, "budget_max_usd": ANY_BUDGET}
        for name in CARD_MODEL_FIELDS:
            value = getattr(card, name, None)
            item[name] = None if value in (None, "", "unknown") else value
        vehicles.append(item)
    return predict_prices(vehicles, model_path=model_path)
