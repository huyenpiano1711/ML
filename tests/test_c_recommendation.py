"""Automated checks for AutoWise Recommendation tasks C01-C03."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.schemas.result_schema import CarCard
from backend.schemas.vehicle_input import VehicleInput
from src.recommendation.build_catalog import (
    CATALOG_COLUMNS,
    REQUIRED_NOT_NULL,
    validate_catalog,
)
from src.recommendation.recommend import Recommender

PROJECT_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = PROJECT_DIR / "data" / "processed" / "recommendation_catalog.pkl"


@pytest.fixture(scope="session")
def catalog() -> pd.DataFrame:
    assert CATALOG_PATH.is_file(), f"Missing catalog: {CATALOG_PATH}"
    return pd.read_pickle(CATALOG_PATH)


@pytest.fixture(scope="session")
def recommender() -> Recommender:
    return Recommender.from_pickle()


@pytest.fixture(scope="session")
def query() -> dict:
    car = VehicleInput.from_dict({
        "manufacturer": "ford",
        "model_base": "f150",
        "year": 2018,
        "type": "pickup",
        "odometer": 60_000,
        "condition": "good",
        "fuel": "gas",
        "transmission": "automatic",
        "budget_max_usd": 25_000,
    }).check()
    return car.to_recommendation_query()


def test_catalog_contract_and_unique_ids(catalog):
    assert list(catalog.columns) == CATALOG_COLUMNS
    assert catalog["id"].is_unique
    assert not catalog[REQUIRED_NOT_NULL].isna().any().any()
    assert validate_catalog(catalog) == []


@pytest.mark.parametrize("method", ["knn", "cosine"])
def test_recommend_returns_unique_top_five_within_budget(recommender, query, method):
    result = recommender.recommend(query, k=5, method=method)
    assert len(result.cars) == 5
    assert result.cars["id"].is_unique
    assert (result.cars["price"] <= query["budget_max_usd"]).all()
    assert result.cars["rank"].tolist() == [1, 2, 3, 4, 5]
    assert result.cars["score"].between(0, 1).all()


def test_strict_filter_matches_requested_fields(recommender, query):
    result = recommender.recommend(
        query,
        k=5,
        strict=("type", "fuel", "transmission"),
    )
    assert len(result.cars) == 5
    assert (result.cars["type"] == "pickup").all()
    assert (result.cars["fuel"] == "gas").all()
    assert (result.cars["transmission"] == "automatic").all()


def test_exclude_ids_removes_selected_car(recommender, query):
    first = recommender.recommend(query, k=5)
    excluded_id = int(first.cars.iloc[0]["id"])
    second = recommender.recommend(query, k=5, exclude_ids=[excluded_id])
    assert excluded_id not in second.cars["id"].tolist()


def test_result_converts_to_backend_car_cards(recommender, query):
    cards = recommender.recommend(query, k=5).to_cards()
    assert len(cards) == 5
    assert all(isinstance(card, CarCard) for card in cards)
    assert all(card.price <= query["budget_max_usd"] for card in cards)
    assert all(card.score is not None for card in cards)


@pytest.mark.parametrize("bad_query", [
    {},
    {"budget_max_usd": None, "preferences": {}},
    {"budget_max_usd": 0, "preferences": {}},
    {"budget_max_usd": -1, "preferences": {}},
])
def test_invalid_budget_is_rejected(recommender, bad_query):
    with pytest.raises(ValueError):
        recommender.recommend(bad_query)


def test_no_result_returns_empty_frame_and_warning(recommender):
    result = recommender.recommend({"budget_max_usd": 1, "preferences": {}}, k=5)
    assert result.cars.empty
    assert result.n_candidates == 0
    assert result.warnings

