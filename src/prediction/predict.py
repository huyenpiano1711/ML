"""Inference API for the trained AutoWise price pipeline."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sys
from typing import Mapping

# Cho phep bam "Run Python File" truc tiep tu VS Code/PyCharm.
PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

import joblib
import numpy as np
import pandas as pd

from backend.schemas.vehicle_input import VehicleInput

DEFAULT_MODEL_PATH = PROJECT_DIR / "models" / "price_prediction" / "final_pipeline.joblib"


@lru_cache(maxsize=4)
def load_pipeline(model_path: str | Path = DEFAULT_MODEL_PATH):
    """Load and cache a fitted pipeline; never trains during inference."""
    path = Path(model_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"Price model not found at {path}. Run `python -m src.prediction.evaluate` once."
        )
    return joblib.load(path)


def predict_price(
    vehicle: VehicleInput | Mapping[str, object],
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> float:
    """Validate UI input and return one finite, non-negative USD prediction."""
    item = vehicle if isinstance(vehicle, VehicleInput) else VehicleInput.from_dict(dict(vehicle))
    item.check()
    row = pd.DataFrame([item.to_model_row()])
    prediction = float(load_pipeline(model_path).predict(row)[0])
    if not np.isfinite(prediction):
        raise ValueError("The price model returned a non-finite prediction.")
    return max(100.0, prediction)


def predict_prices(
    vehicles: list[VehicleInput | Mapping[str, object]],
    model_path: str | Path = DEFAULT_MODEL_PATH,
) -> list[float | None]:
    """One prediction per vehicle in a single call of the pipeline; None for a vehicle that does not pass
    VehicleInput.check() (the others are still predicted)."""
    rows, positions = [], []
    for n, vehicle in enumerate(vehicles):
        try:
            item = vehicle if isinstance(vehicle, VehicleInput) else VehicleInput.from_dict(dict(vehicle))
            item.check()
        except Exception:                                   # noqa: BLE001
            continue
        rows.append(item.to_model_row())
        positions.append(n)
    result: list[float | None] = [None] * len(vehicles)
    if rows:
        for n, value in zip(positions, load_pipeline(model_path).predict(pd.DataFrame(rows))):
            result[n] = max(100.0, float(value)) if np.isfinite(value) else None
    return result
