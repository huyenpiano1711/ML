"""
app_service.py - HÀM XỬ LÝ CHÍNH CỦA BACKEND

Frontend chỉ cần gọi một hàm khi người dùng bấm "Phân tích và tìm xe":

    from backend.app_service import analyze
    result = analyze(form_dict)          # AnalysisResult, không bao giờ ném lỗi ra ngoài

Luồng xử lý:
  1. Kiểm tra dữ liệu nhập (VehicleInput). Sai -> trả AnalysisResult.failure(errors) ngay.
  2. Dự đoán giá cho cấu hình xe người dùng nhập (prediction_service).
  3. Gợi ý tối đa 5 xe trong ngân sách (recommendation_service).
  4. Tìm tối đa 6 xe khác có giá gần giá dự đoán, không trùng Top 5 (alternative_service).
  5. Gắn ảnh minh họa hoặc ảnh thay thế cho mọi thẻ xe (image_service).
  6. Gom giá, hai danh sách xe, lỗi, cảnh báo và thời gian xử lý vào AnalysisResult.

Quy ước lỗi:
  - errors   : lỗi làm thiếu một phần kết quả (nhập sai, không nạp được mô hình hoặc catalog).
               success = False khi có ít nhất một lỗi. Phần kết quả còn lại vẫn được trả về
               (ví dụ mô hình lỗi nhưng vẫn có Top 5), để giao diện không bị trống.
  - warnings : kết quả vẫn dùng được nhưng cần lưu ý (ít hơn 5 xe, phải mở rộng khoảng giá...).
  - Ảnh thiếu hoặc lỗi không tạo lỗi: image_service thay bằng ảnh thay thế.

Mô hình, catalog và dịch vụ ảnh được nạp MỘT lần cho cả phiên chạy và dùng lại cho mọi lần
bấm nút. Thời gian từng bước của lần gọi gần nhất nằm trong AppService.last_timings (ms).
"""
from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Optional

from backend.schemas.result_schema import AnalysisResult, CarCard, PriceResult
from backend.schemas.vehicle_input import VehicleInput
from backend.services.alternative_service import find_similar_price_vehicles
from backend.services.image_service import ImageService, get_image_service
from backend.services.prediction_service import METRICS_PATH, predict_vehicle_price
from backend.services.recommendation_service import recommend_vehicles
from src.prediction.predict import DEFAULT_MODEL_PATH, load_pipeline
from src.recommendation.recommend import Recommender, get_recommender

log = logging.getLogger("autowise.backend")

STAGES = ("validate", "predict", "recommend", "alternatives", "images", "total")

MSG_BAD_FORM = "Dữ liệu gửi từ giao diện không đúng định dạng (cần một dict các ô nhập)."
MSG_MODEL_MISSING = "Không tìm thấy file mô hình dự đoán giá ({path}). Chưa thể dự đoán giá."
MSG_MODEL_ERROR = "Mô hình dự đoán giá gặp lỗi, chưa thể dự đoán giá cho xe này."
MSG_CATALOG_MISSING = ("Chưa có danh sách xe để gợi ý (recommendation_catalog.pkl). "
                       "Chạy: python -m src.recommendation.build_catalog")
MSG_CATALOG_ERROR = "Không nạp được danh sách xe để gợi ý."
MSG_RECOMMEND_ERROR = "Chức năng gợi ý xe gặp lỗi, chưa thể tìm xe phù hợp."
MSG_ALTERNATIVE_ERROR = "Chức năng tìm xe cùng mức giá gặp lỗi."
MSG_NO_PRICE_FOR_ALTERNATIVES = "Chưa có giá dự đoán nên không tìm được xe cùng mức giá."
MSG_PRICE_OVER_BUDGET = ("Giá dự đoán của xe bạn nhập ({price} USD) cao hơn ngân sách tối đa "
                         "({budget} USD).")


def _usd(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for s in items:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


class AppService:
    """Điều phối toàn bộ luồng Backend. Tạo một lần (get_app_service()) rồi gọi analyze() nhiều lần."""

    def __init__(self, model_path: str | Path = DEFAULT_MODEL_PATH,
                 metrics_path: str | Path = METRICS_PATH,
                 recommender: Recommender | None = None,
                 recommender_factory: Callable[[], Recommender] = get_recommender,
                 image_service: ImageService | None = None):
        self.model_path = Path(model_path)
        self.metrics_path = Path(metrics_path)
        self._recommender = recommender
        self._recommender_factory = recommender_factory
        self._images = image_service
        self._lock = threading.Lock()
        self.last_timings: dict[str, float] = {}

    # ------------------------------------------------------------------ nạp tài nguyên (1 lần)
    @property
    def images(self) -> ImageService:
        if self._images is None:
            self._images = get_image_service()
        return self._images

    def recommender(self) -> Recommender:
        """Catalog được nạp ở lần gọi đầu tiên rồi giữ lại. Lỗi nạp không được lưu lại,
        nên nếu người dùng tạo catalog trong lúc ứng dụng đang mở, lần bấm sau sẽ thành công."""
        if self._recommender is None:
            with self._lock:
                if self._recommender is None:
                    self._recommender = self._recommender_factory()
        return self._recommender

    def warm_up(self) -> list[str]:
        """Nạp sẵn mô hình, catalog và danh mục ảnh lúc mở ứng dụng (gọi từ main.py),
        để lần bấm nút đầu tiên không phải chờ. Trả danh sách lỗi (rỗng = sẵn sàng)."""
        errors = []
        try:
            load_pipeline(self.model_path)
        except FileNotFoundError:
            errors.append(MSG_MODEL_MISSING.format(path=self.model_path.name))
        except Exception:                                   # noqa: BLE001
            log.exception("Không nạp được mô hình")
            errors.append(MSG_MODEL_ERROR)
        try:
            self.recommender()
        except FileNotFoundError:
            errors.append(MSG_CATALOG_MISSING)
        except Exception:                                   # noqa: BLE001
            log.exception("Không nạp được catalog")
            errors.append(MSG_CATALOG_ERROR)
        self.images.placeholder_path()
        self.images.lookup("", "", 0)                       # quét danh mục ảnh một lần
        return errors

    # ------------------------------------------------------------------ luồng chính
    def analyze(self, form: object) -> AnalysisResult:
        """Nhận dict từ Frontend, trả AnalysisResult. Không ném lỗi ra ngoài."""
        t_start = time.perf_counter()
        timings = {s: 0.0 for s in STAGES}
        try:
            result = self._analyze(form, timings)
        except Exception:                                   # noqa: BLE001 - lưới an toàn cuối cùng
            log.exception("Lỗi không lường trước trong analyze()")
            result = AnalysisResult.failure(["Đã xảy ra lỗi không mong muốn khi phân tích. Vui lòng thử lại."])
        timings["total"] = (time.perf_counter() - t_start) * 1000
        result.elapsed_ms = round(timings["total"], 2)
        self.last_timings = {k: round(v, 3) for k, v in timings.items()}
        return result

    def _analyze(self, form: object, timings: dict[str, float]) -> AnalysisResult:
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Kiểm tra dữ liệu nhập
        t = time.perf_counter()
        if not isinstance(form, Mapping):
            return AnalysisResult.failure([MSG_BAD_FORM])
        try:
            car = VehicleInput.from_dict(dict(form))
            input_errors = car.validate()
        except Exception:                                   # noqa: BLE001
            log.exception("Không đọc được dữ liệu form")
            return AnalysisResult.failure([MSG_BAD_FORM])
        timings["validate"] = (time.perf_counter() - t) * 1000
        if input_errors:
            return AnalysisResult.failure(input_errors)

        # 2. Dự đoán giá
        t = time.perf_counter()
        price: Optional[PriceResult] = None
        try:
            price = predict_vehicle_price(car, model_path=self.model_path, metrics_path=self.metrics_path)
        except FileNotFoundError:
            errors.append(MSG_MODEL_MISSING.format(path=self.model_path.name))
        except Exception:                                   # noqa: BLE001
            log.exception("Lỗi dự đoán giá")
            errors.append(MSG_MODEL_ERROR)
        if price is not None and not (math.isfinite(price.predicted_price) and price.predicted_price > 0):
            log.error("Giá dự đoán không hợp lệ: %r", price.predicted_price)
            errors.append(MSG_MODEL_ERROR)
            price = None
        if price is not None and price.predicted_price > car.budget_max_usd:
            warnings.append(MSG_PRICE_OVER_BUDGET.format(price=_usd(price.predicted_price),
                                                         budget=_usd(car.budget_max_usd)))
        timings["predict"] = (time.perf_counter() - t) * 1000

        # 3. Gợi ý Top 5
        t = time.perf_counter()
        top_cards: list[CarCard] = []
        engine: Optional[Recommender] = None
        try:
            engine = self.recommender()
        except FileNotFoundError:
            errors.append(MSG_CATALOG_MISSING)
        except Exception:                                   # noqa: BLE001
            log.exception("Không nạp được catalog")
            errors.append(MSG_CATALOG_ERROR)
        if engine is not None:
            try:
                top = recommend_vehicles(car, recommender=engine)
                top_cards = top.to_cards()
                warnings += top.warnings
            except Exception:                               # noqa: BLE001
                log.exception("Lỗi gợi ý xe")
                errors.append(MSG_RECOMMEND_ERROR)
        timings["recommend"] = (time.perf_counter() - t) * 1000

        # 4. Xe cùng mức giá
        t = time.perf_counter()
        alt_cards: list[CarCard] = []
        if engine is not None and price is not None:
            try:
                alt = find_similar_price_vehicles(
                    price.predicted_price, exclude_ids=[c.id for c in top_cards],
                    preferences=car.to_recommendation_query()["preferences"], recommender=engine)
                alt_cards = alt.to_cards()
                warnings += alt.warnings
            except Exception:                               # noqa: BLE001
                log.exception("Lỗi tìm xe cùng mức giá")
                errors.append(MSG_ALTERNATIVE_ERROR)
        elif engine is not None:
            warnings.append(MSG_NO_PRICE_FOR_ALTERNATIVES)
        timings["alternatives"] = (time.perf_counter() - t) * 1000

        # 5. Gắn ảnh (không bao giờ làm hỏng kết quả)
        t = time.perf_counter()
        try:
            top_cards = self.images.with_images(top_cards)
            alt_cards = self.images.with_images(alt_cards)
        except Exception:                                   # noqa: BLE001
            log.exception("Lỗi gắn ảnh")
        timings["images"] = (time.perf_counter() - t) * 1000

        return AnalysisResult(success=not errors, vehicle_title=car.title, price=price,
                              top_matches=top_cards, similar_price=alt_cards,
                              errors=_dedupe(errors), warnings=_dedupe(warnings))


# Hàm tiện lợi cho Frontend: một AppService cho cả phiên chạy
_DEFAULT: AppService | None = None
_DEFAULT_LOCK = threading.Lock()


def get_app_service() -> AppService:
    global _DEFAULT
    if _DEFAULT is None:
        with _DEFAULT_LOCK:
            if _DEFAULT is None:
                _DEFAULT = AppService()
    return _DEFAULT


def analyze(form: object) -> AnalysisResult:
    """Gọi từ Frontend (results_controller.py): analyze(form_dict) -> AnalysisResult."""
    return get_app_service().analyze(form)
