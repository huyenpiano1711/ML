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
