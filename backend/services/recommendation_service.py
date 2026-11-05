"""Backend adapter for the AutoWise vehicle recommendation system (D03).

C02 - "yêu cầu bắt buộc" (tổng quan đồ án, mục 2): ngoài ngân sách, HÃNG XE người dùng chọn là điều kiện
bắt buộc. Top 5 được tìm trong các xe cùng hãng và trong ngân sách, rồi xếp hạng bằng KNN (C03, không đổi).
Nếu hãng đó có ít hơn 5 xe trong ngân sách, phần còn thiếu được bù bằng xe hãng khác gần nhu cầu nhất,
xếp SAU các xe cùng hãng, kèm cảnh báo để giao diện ghi rõ "hãng khác".
"""
from __future__ import annotations

import time
from typing import Mapping

import numpy as np
import pandas as pd

from backend.schemas.vehicle_input import VehicleInput
from src.recommendation.recommend import TOP_K, RecommendationResult, Recommender, get_recommender

REQUIRED_FIELDS = ("manufacturer",)          # điều kiện bắt buộc của C02, ngoài ngân sách

# Cảnh báo cho giao diện (desktop_app/controllers/results_controller.py dịch sang tiếng Anh)
MSG_NO_SAME_MAKE = ("Không có xe {make} nào có giá không vượt quá {budget} USD. "
                    "Đang gợi ý xe hãng khác gần nhu cầu nhất.")
MSG_FEW_SAME_MAKE = ("Chỉ có {n} xe {make} có giá không vượt quá {budget} USD. "
                     "Các xe còn lại là hãng khác gần nhu cầu nhất.")


def _vn_money(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def recommend_vehicles(
    vehicle: VehicleInput | Mapping[str, object],
    *,
    recommender: Recommender | None = None,
    k: int = TOP_K,
) -> RecommendationResult:
    """Top k xe: cùng hãng trước (bắt buộc), sau đó - chỉ khi thiếu - xe hãng khác gần nhu cầu nhất."""
    item = vehicle if isinstance(vehicle, VehicleInput) else VehicleInput.from_dict(dict(vehicle))
    item.check()
    engine = recommender if recommender is not None else get_recommender()
    query = item.to_recommendation_query()
    t0 = time.perf_counter()

    same = engine.recommend(query, k=k, strict=REQUIRED_FIELDS)
    if len(same.cars) >= k:
        return same

    # Hãng này không đủ k xe trong ngân sách: mọi xe cùng hãng hợp lệ đã có trong `same`,
    # nên bỏ chúng ra rồi tìm phần còn thiếu trên toàn catalog -> chỉ còn xe hãng khác.
    other = engine.recommend(query, k=k - len(same.cars), exclude_ids=same.cars["id"].tolist())
    make, budget = item.manufacturer, _vn_money(item.budget_max_usd)
    if other.cars.empty:                        # không có xe nào trong ngân sách: giữ cảnh báo gốc
        return same if not same.cars.empty else other
    warnings = [MSG_FEW_SAME_MAKE.format(n=len(same.cars), make=make.title(), budget=budget)
                if len(same.cars) else MSG_NO_SAME_MAKE.format(make=make.title(), budget=budget)]
    warnings += [w for w in other.warnings if w not in warnings]
    cars = pd.concat([same.cars, other.cars], ignore_index=True)
    cars["rank"] = np.arange(1, len(cars) + 1)
    return RecommendationResult(cars, warnings, same.n_candidates + other.n_candidates,
                                (time.perf_counter() - t0) * 1000, same.method,
                                np.concatenate([same.rows, other.rows]).astype(int))
