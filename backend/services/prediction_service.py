"""Backend adapter for the AutoWise price prediction model."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from backend.schemas.result_schema import CarCard, PriceResult
from backend.schemas.vehicle_input import VehicleInput
from src.prediction.predict import DEFAULT_MODEL_PATH, predict_price, predict_prices, price_interval

PROJECT_DIR = Path(__file__).resolve().parents[2]
METRICS_PATH = PROJECT_DIR / "models" / "price_prediction" / "metrics.json"


def _interval_bands(metrics_path: str | Path = METRICS_PATH) -> list[dict] | None:
    """Band table of the reference range (quantiles of actual/predicted on the validation set, by
    predicted price), written by src/prediction/evaluate.py. None when the file or the table is missing."""
    path = Path(metrics_path)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("price_interval", {}).get("bands") or None


def predict_vehicle_price(
    vehicle: VehicleInput | Mapping[str, object],
    model_path: str | Path = DEFAULT_MODEL_PATH,
    metrics_path: str | Path = METRICS_PATH,
) -> PriceResult:
    """Return the frontend contract. The range is where about 80% of real listings fell around such a
    prediction on the validation set (wider in USD for dearer cars), not a fixed +/- MAE."""
    predicted = predict_price(vehicle, model_path=model_path)
    bands = _interval_bands(metrics_path)
    low, high = (None, None) if bands is None else price_interval(predicted, bands)
    return PriceResult(
        predicted_price=round(predicted, 2),
        price_low=None if low is None else round(low, 2),
        price_high=None if high is None else round(high, 2),
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
