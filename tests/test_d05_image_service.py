"""Tests for D05 image_service: tìm ảnh theo catalog, kiểm tra lỗi và ảnh thay thế."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from backend.schemas.result_schema import CarCard
from backend.services import image_service as ims
from backend.services.image_service import ImageService

REL = "assets/car_images_unique"


def _jpg(path: Path, color=(200, 30, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (60, 40), color).save(path, format="JPEG")
    return path


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Repo giả: 3 ảnh hợp lệ, 1 ảnh hỏng, 1 file rỗng, 1 ảnh .gif, 1 file ngoài thư mục ảnh."""
    img = tmp_path / REL
    _jpg(img / "ford_f150_2015.jpg")
    _jpg(img / "ford_f150_2010.jpg")
    _jpg(img / "toyota_camry_2018.jpg")
    (img / "honda_civic_2016.jpg").write_bytes(b"\xff\xd8\xff\xe0 not really a jpeg")
    (img / "honda_accord_2014.jpg").write_bytes(b"")
    Image.new("RGB", (10, 10)).save(img / "bmw_x5_2017.gif", format="GIF")
    _jpg(tmp_path / "secret" / "outside.jpg")
    return tmp_path


@pytest.fixture()
def service(repo: Path) -> ImageService:
    return ImageService(project_dir=repo)


def _card(**kw) -> CarCard:
    base = dict(id=1, manufacturer="ford", model_base="f150", year=2015, price=20_000,
                odometer=80_000, type="pickup", condition="good", fuel="gas",
                transmission="automatic", image_path=f"{REL}/ford_f150_2015.jpg", score=0.9)
    base.update(kw)
    return CarCard(**base)


# ---------------------------------------------------------------- ảnh hợp lệ
def test_valid_catalog_path_returns_absolute_path(service, repo):
    r = service.resolve(f"{REL}/ford_f150_2015.jpg")
    assert not r.is_placeholder and r.source == ims.SOURCE_CATALOG and r.reason == ims.OK
    assert Path(r.path).is_absolute() and Path(r.path) == (repo / REL / "ford_f150_2015.jpg").resolve()
    assert r.label == ims.ILLUSTRATION_LABEL


def test_windows_style_separators_are_accepted(service):
    assert not service.resolve("assets\\car_images_unique\\toyota_camry_2018.jpg").is_placeholder


# ---------------------------------------------------------------- các trường hợp lỗi -> ảnh thay thế
@pytest.mark.parametrize("image_path, reason", [
    (None, ims.MISSING_PATH),
    (float("nan"), ims.MISSING_PATH),
    ("   ", ims.MISSING_PATH),
    (f"{REL}/kia_soul_2012.jpg", ims.NOT_FOUND),
    (f"{REL}/honda_civic_2016.jpg", ims.CORRUPT_IMAGE),
    (f"{REL}/honda_accord_2014.jpg", ims.EMPTY_FILE),
    (f"{REL}/bmw_x5_2017.gif", ims.UNSUPPORTED_FORMAT),
    (f"{REL}/../../secret/outside.jpg", ims.OUTSIDE_IMAGE_DIR),
    (f"{REL}", ims.UNSUPPORTED_FORMAT),
])
def test_bad_paths_fall_back_to_placeholder(service, image_path, reason):
    r = service.resolve(image_path)
    assert r.is_placeholder and r.source == ims.SOURCE_PLACEHOLDER and r.reason == reason
    assert Path(r.path).is_file() and service.is_placeholder(r.path)
    assert r.label == ims.PLACEHOLDER_LABEL


def test_absolute_path_outside_image_dir_is_rejected(service, repo):
    r = service.resolve(str(repo / "secret" / "outside.jpg"))
    assert r.is_placeholder and r.reason == ims.OUTSIDE_IMAGE_DIR


def test_oversized_file_is_rejected(repo):
    svc = ImageService(project_dir=repo, max_file_mb=0.000001)
    assert svc.resolve(f"{REL}/ford_f150_2015.jpg").reason == ims.TOO_LARGE


# ---------------------------------------------------------------- tìm lại theo hãng-dòng-năm
def test_lookup_exact_year_when_catalog_path_missing(service):
    r = service.resolve_vehicle("Ford", "F150", 2015, None)
    assert not r.is_placeholder and r.source == ims.SOURCE_LOOKUP_EXACT
    assert r.path.endswith("ford_f150_2015.jpg") and r.reason == ims.MISSING_PATH


def test_lookup_nearest_year_ties_go_to_older_year(service):
    r = service.resolve_vehicle("ford", "f150", 2012, None)      # 2010 và 2015: gần 2010 hơn
    assert r.source == ims.SOURCE_LOOKUP_NEAREST and r.path.endswith("ford_f150_2010.jpg")
    r = service.resolve_vehicle("ford", "f150", 2020, None)
    assert r.path.endswith("ford_f150_2015.jpg")


def test_lookup_replaces_broken_catalog_path(service):
    r = service.resolve_vehicle("toyota", "camry", 2018, f"{REL}/toyota_camry_2018_missing.jpg")
    assert not r.is_placeholder and r.reason == ims.NOT_FOUND and r.source == ims.SOURCE_LOOKUP_EXACT


def test_unknown_model_or_bad_year_gives_placeholder(service):
    assert service.resolve_vehicle("tesla", "model 3", 2020, None).is_placeholder
    assert service.resolve_vehicle("ford", "f150", "abc", None).is_placeholder
    assert service.resolve_vehicle("honda", "civic", 2016, None).is_placeholder   # ảnh duy nhất bị hỏng


# ---------------------------------------------------------------- thẻ xe
def test_with_images_keeps_other_fields_and_always_sets_path(service):
    cards = [_card(), _card(id=2, manufacturer="kia", model_base="soul", year=2012, image_path=None)]
    out = service.with_images(cards)
    assert [c.id for c in out] == [1, 2] and out[0].score == 0.9 and out[1].price == 20_000
    assert all(c.image_path and Path(c.image_path).is_file() for c in out)
    assert service.is_placeholder(out[1].image_path) and not service.is_placeholder(out[0].image_path)
    assert cards[1].image_path is None                       # thẻ gốc không bị sửa


def test_card_from_catalog_row_with_nan_image(service):
    card = CarCard.from_row({"id": 3, "manufacturer": "toyota", "model_base": "camry", "year": 2018,
                             "price": 15_000, "odometer": 50_000, "type": "sedan",
                             "condition": "good", "fuel": "gas", "transmission": "automatic",
                             "image_path": float("nan")})
    r = service.resolve_card(card)
    assert not r.is_placeholder and r.path.endswith("toyota_camry_2018.jpg")


# ---------------------------------------------------------------- ảnh thay thế
def test_placeholder_is_recreated_when_deleted_or_corrupt(service, repo):
    p = Path(service.placeholder_path())
    assert p.is_file() and Image.open(p).size == ims.PLACEHOLDER_SIZE
    p.unlink()
    service.clear_cache()
    assert Path(service.resolve(None).path).is_file()
    p.write_bytes(b"broken")
    service.clear_cache()
    service.resolve(None)
    with Image.open(p) as im:
        im.verify()


def test_repo_placeholder_is_a_valid_png():
    p = ims.PLACEHOLDER_PATH
    assert p.is_file(), "thiếu assets/placeholder_car.png"
    with Image.open(p) as im:
        assert im.format == "PNG" and im.size == ims.PLACEHOLDER_SIZE


# ---------------------------------------------------------------- bộ đệm
def test_each_file_is_verified_once_until_it_changes(service, repo, monkeypatch):
    calls = []
    real = ImageService._verify
    monkeypatch.setattr(ImageService, "_verify", staticmethod(lambda p: calls.append(p) or real(p)))
    path = f"{REL}/ford_f150_2015.jpg"
    for _ in range(5):
        assert not service.resolve(path).is_placeholder
    assert len(calls) == 1
    target = repo / REL / "ford_f150_2015.jpg"
    target.write_bytes(b"")                                  # file bị ghi đè thành rỗng
    os.utime(target, ns=(1, 1))
    assert service.resolve(path).reason == ims.EMPTY_FILE


def test_get_image_service_is_a_singleton():
    assert ims.get_image_service() is ims.get_image_service()
