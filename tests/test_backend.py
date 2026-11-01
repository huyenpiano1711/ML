"""Kiểm thử Backend: app_service.analyze() với dữ liệu đúng, thiếu, sai, lỗi nạp mô hình/catalog,
không tìm thấy xe, thiếu ảnh, và kiểm tra không nạp lại mô hình mỗi lần bấm nút."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from backend import app_service as app_mod
from backend.app_service import AppService
from backend.schemas.result_schema import MAX_ALTERNATIVES, TOP_K, AnalysisResult
from backend.services.image_service import ImageService
from src.prediction.predict import DEFAULT_MODEL_PATH, load_pipeline, predict_price
from src.recommendation.recommend import CATALOG_PKL, Recommender

pytestmark = pytest.mark.skipif(not DEFAULT_MODEL_PATH.is_file(), reason="thiếu final_pipeline.joblib")

FORM = {
    "user_name": "Kha", "manufacturer": "ford", "model_base": "f150", "year": 2018,
    "type": "pickup", "odometer": 60000, "condition": "good", "fuel": "gas",
    "transmission": "automatic", "budget_max_usd": 30000, "drive": "4wd",
    "cylinders": "6 cylinders", "paint_color": "white", "title_status": "clean", "state": "ca",
}
IMG_REL = "assets/car_images_unique"


def _catalog() -> pd.DataFrame:
    """Catalog nhỏ: 12 xe giá 8.000-40.000 USD, 6 dòng xe, 2 xe có ảnh (1 ảnh hỏng)."""
    rows = []
    models = [("ford", "f150", "pickup"), ("chevrolet", "silverado 1500", "pickup"), ("ram", "1500", "pickup"),
              ("toyota", "tacoma", "pickup"), ("toyota", "camry", "sedan"), ("honda", "civic", "sedan")]
    for i in range(12):
        make, model, body = models[i % len(models)]
        year = 2012 + i % 8
        rows.append({"id": 1000 + i, "manufacturer": make, "model_base": model, "make_model": f"{make} {model}",
                     "year": year, "car_age": 2021 - year, "price": 8000 + 3000 * i,
                     "odometer": 30000 + 9000 * i, "type": body, "condition": "good", "fuel": "gas",
                     "transmission": "automatic", "drive": "4wd" if body == "pickup" else "fwd",
                     "image_path": None, "image_match": "none"})
    rows[0]["image_path"] = f"{IMG_REL}/ford_f150_2012.jpg"
    rows[1]["image_path"] = f"{IMG_REL}/chevrolet_silverado_1500_2013.jpg"     # file hỏng
    return pd.DataFrame(rows)


@pytest.fixture()
def images(tmp_path: Path) -> ImageService:
    d = tmp_path / IMG_REL
    d.mkdir(parents=True)
    Image.new("RGB", (40, 30), (10, 120, 200)).save(d / "ford_f150_2012.jpg", format="JPEG")
    (d / "chevrolet_silverado_1500_2013.jpg").write_bytes(b"broken")
    return ImageService(project_dir=tmp_path)


@pytest.fixture()
def service(images) -> AppService:
    return AppService(recommender=Recommender(_catalog()), image_service=images)


def _ok(result: AnalysisResult):
    assert isinstance(result, AnalysisResult)
    json.dumps(result.to_dict(), ensure_ascii=False)            # giao diện/ghi log đọc được
    assert result.elapsed_ms is not None and result.elapsed_ms >= 0


# ---------------------------------------------------------------- 1. luồng đầy đủ
def test_full_flow_returns_price_top5_alternatives_and_images(service):
    r = service.analyze(FORM)
    _ok(r)
    assert r.success and r.errors == []
    assert r.vehicle_title == "Ford F150 2018"
    assert r.price.predicted_price > 0 and r.price.currency == "USD"
    assert r.price.price_low < r.price.predicted_price < r.price.price_high
    assert 1 <= len(r.top_matches) <= TOP_K
    assert all(c.price <= FORM["budget_max_usd"] for c in r.top_matches)
    assert all(c.score is not None for c in r.top_matches)
    assert len(r.similar_price) <= MAX_ALTERNATIVES
    assert not {c.id for c in r.top_matches} & {c.id for c in r.similar_price}
    for c in r.top_matches + r.similar_price:
        assert c.image_path and Path(c.image_path).is_file()


def test_price_matches_direct_model_call(service):
    """Cùng bộ thông số: giá qua Backend = giá gọi trực tiếp mô hình."""
    r = service.analyze(FORM)
    assert r.price.predicted_price == pytest.approx(predict_price(FORM), abs=0.01)


def test_last_timings_cover_every_stage(service):
    service.analyze(FORM)
    assert set(service.last_timings) == set(app_mod.STAGES)
    assert service.last_timings["total"] >= service.last_timings["predict"]


# ---------------------------------------------------------------- 2. nhập thiếu / nhập sai
@pytest.mark.parametrize("change, fragment", [
    ({"manufacturer": ""}, "Hãng"),
    ({"odometer": None}, "Chưa nhập"),
    ({"year": "abc"}, "phải là số"),
    ({"year": 1985}, "phải từ"),
    ({"odometer": 999_999}, "phải từ"),
    ({"budget_max_usd": 500}, "phải từ"),
    ({"fuel": "nuclear"}, "không hợp lệ"),
    ({"model_base": "camry"}, "không thuộc hãng"),
])
def test_invalid_input_returns_clear_errors_without_crashing(service, change, fragment):
    r = service.analyze({**FORM, **change})
    _ok(r)
    assert not r.success and r.errors and r.price is None
    assert r.top_matches == [] and r.similar_price == []
    assert any(fragment in e for e in r.errors)


def test_all_fields_missing_lists_every_required_field(service):
    r = service.analyze({})
    assert not r.success and len(r.errors) >= 9


@pytest.mark.parametrize("bad", [None, "ford f150", 123, ["ford"]])
def test_non_dict_input_is_rejected(service, bad):
    r = service.analyze(bad)
    assert not r.success and r.errors == [app_mod.MSG_BAD_FORM]


def test_extra_and_messy_fields_are_tolerated(service):
    r = service.analyze({**FORM, "manufacturer": "  FORD ", "year": "2018", "odometer": "60000",
                         "unexpected_field": "x"})
    assert r.success and r.vehicle_title == "Ford F150 2018"


# ---------------------------------------------------------------- 3. không tìm thấy xe
def test_no_car_within_budget_gives_warning_not_error(service):
    r = service.analyze({**FORM, "budget_max_usd": 5000})
    assert r.success and r.top_matches == [] and r.price is not None
    assert any("Không có xe nào" in w for w in r.warnings)
    assert any("cao hơn ngân sách" in w for w in r.warnings)


def test_no_similar_price_car_gives_warning(images):
    cheap = _catalog().assign(price=lambda d: 1000 + d.index * 10)       # mọi xe rẻ hơn rất nhiều
    r = AppService(recommender=Recommender(cheap), image_service=images).analyze(FORM)
    assert r.success and r.similar_price == []
    assert any("±30%" in w for w in r.warnings)


# ---------------------------------------------------------------- 4. lỗi nạp mô hình / catalog
def test_missing_model_file_is_reported_and_recommendations_still_work(images, tmp_path):
    svc = AppService(model_path=tmp_path / "missing.joblib", recommender=Recommender(_catalog()),
                     image_service=images)
    r = svc.analyze(FORM)
    _ok(r)
    assert not r.success and r.price is None
    assert any("Không tìm thấy file mô hình" in e for e in r.errors)
    assert r.top_matches and r.similar_price == []
    assert app_mod.MSG_NO_PRICE_FOR_ALTERNATIVES in r.warnings


def test_corrupt_model_file_is_reported(images, tmp_path):
    bad = tmp_path / "corrupt.joblib"
    bad.write_bytes(b"not a model")
    r = AppService(model_path=bad, recommender=Recommender(_catalog()), image_service=images).analyze(FORM)
    assert not r.success and app_mod.MSG_MODEL_ERROR in r.errors and r.top_matches


def test_missing_catalog_is_reported_and_price_still_works(images):
    def missing():
        raise FileNotFoundError("recommendation_catalog.pkl")
    r = AppService(recommender_factory=missing, image_service=images).analyze(FORM)
    _ok(r)
    assert not r.success and app_mod.MSG_CATALOG_MISSING in r.errors
    assert r.price is not None and r.top_matches == [] and r.similar_price == []


def test_catalog_load_is_retried_after_a_failure(images):
    calls = []
    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise FileNotFoundError("chưa có")
        return Recommender(_catalog())
    svc = AppService(recommender_factory=flaky, image_service=images)
    assert not svc.analyze(FORM).success
    assert svc.analyze(FORM).success and len(calls) == 2


def test_unexpected_recommender_error_is_contained(images, monkeypatch):
    engine = Recommender(_catalog())
    monkeypatch.setattr(engine, "recommend", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = AppService(recommender=engine, image_service=images).analyze(FORM)
    assert not r.success and app_mod.MSG_RECOMMEND_ERROR in r.errors and r.price is not None


def test_unexpected_error_anywhere_never_escapes(service, monkeypatch):
    monkeypatch.setattr(service, "_analyze", lambda *a, **k: 1 / 0)
    r = service.analyze(FORM)
    assert not r.success and r.errors and r.elapsed_ms is not None


# ---------------------------------------------------------------- 5. thiếu ảnh
def test_missing_or_broken_images_fall_back_to_placeholder(service, images):
    r = service.analyze({**FORM, "budget_max_usd": 150000})
    cards = {c.id: c for c in r.top_matches + r.similar_price}
    for card in cards.values():
        assert Path(card.image_path).is_file()
    if 1001 in cards:                                            # ảnh catalog bị hỏng -> ảnh thay thế
        assert images.is_placeholder(cards[1001].image_path)


def test_image_service_failure_does_not_break_result(service, monkeypatch):
    monkeypatch.setattr(service.images, "with_images", lambda cards: 1 / 0)
    r = service.analyze(FORM)
    assert r.success and r.top_matches


# ---------------------------------------------------------------- 6. không nạp lại mô hình
def test_model_and_catalog_are_loaded_once(images):
    load_pipeline.cache_clear()
    built = []
    def factory():
        built.append(1)
        return Recommender(_catalog())
    svc = AppService(recommender_factory=factory, image_service=images)
    assert svc.warm_up() == []
    for _ in range(5):
        assert svc.analyze(FORM).success
    info = load_pipeline.cache_info()
    assert info.misses == 1 and info.hits >= 5
    assert len(built) == 1


def test_warm_up_reports_missing_resources(images, tmp_path):
    def missing():
        raise FileNotFoundError
    errs = AppService(model_path=tmp_path / "x.joblib", recommender_factory=missing,
                      image_service=images).warm_up()
    assert len(errs) == 2


def test_module_level_analyze_uses_one_shared_service():
    assert app_mod.get_app_service() is app_mod.get_app_service()


# ---------------------------------------------------------------- 7. với dữ liệu thật (nếu có catalog)
@pytest.mark.skipif(not CATALOG_PKL.is_file(), reason="chưa build recommendation_catalog.pkl")
def test_real_catalog_end_to_end():
    r = app_mod.analyze(FORM)
    _ok(r)
    assert r.success, r.errors
    assert len(r.top_matches) == TOP_K and len(r.similar_price) == MAX_ALTERNATIVES
    assert all(c.price <= FORM["budget_max_usd"] for c in r.top_matches)
    assert all(Path(c.image_path).is_file() for c in r.top_matches + r.similar_price)
