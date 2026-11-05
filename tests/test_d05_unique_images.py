"""D05 - không trùng ảnh trong một trang kết quả."""
from pathlib import Path

import pytest
from PIL import Image

from backend.schemas.result_schema import CarCard
from backend.services.image_service import ImageService


def card(make="honda", model="fit", year=2017, n=1, image_path=None):
    return CarCard(id=n, manufacturer=make, model_base=model, year=year, price=15000, odometer=50000,
                   type="hatchback", condition="good", fuel="gas", transmission="automatic",
                   image_path=image_path)


@pytest.fixture
def service(tmp_path):
    images = tmp_path / "assets" / "car_images_unique"
    images.mkdir(parents=True)
    for name in ("honda_fit_2015.jpg", "honda_fit_2016.jpg", "honda_fit_2018.jpg", "honda_fit_2019.jpg",
                 "honda_civic_2016.jpg"):
        Image.new("RGB", (40, 30), "red").save(images / name, "JPEG")
    return ImageService(project_dir=tmp_path)


def names(cards):
    return [Path(c.image_path).name for c in cards]


def test_cards_of_one_page_get_different_photos(service):
    cards = [card(year=2016, n=1), card(year=2017, n=2), card(year=2016, n=3)]
    # old behaviour: every card takes its nearest year -> 3 x 2016
    assert names(service.with_images(cards)) == ["honda_fit_2016.jpg"] * 3
    # new: the next nearest free year
    assert names(service.with_unique_images(cards)) == ["honda_fit_2016.jpg", "honda_fit_2018.jpg",
                                                         "honda_fit_2015.jpg"]


def test_photo_is_reused_only_when_the_model_has_no_other(service):
    cards = [card("honda", "civic", 2016, n) for n in range(1, 4)]
    assert names(service.with_unique_images(cards)) == ["honda_civic_2016.jpg"] * 3


def test_model_without_photo_gets_placeholder(service):
    out = service.with_unique_images([card("tesla", "model 3", 2019)])
    assert service.is_placeholder(out[0].image_path)


def test_catalog_image_path_has_priority(service):
    out = service.with_unique_images([card(year=2016, image_path="assets/car_images_unique/honda_fit_2019.jpg"),
                                      card(year=2019, n=2)])
    assert names(out) == ["honda_fit_2019.jpg", "honda_fit_2018.jpg"]


def test_other_fields_are_unchanged(service):
    original = card(year=2016)
    out = service.with_unique_images([original])[0]
    assert (out.id, out.price, out.year) == (original.id, original.price, original.year)
    assert original.image_path is None                     # input card not modified


def test_family_photos_are_used_before_reusing_one(tmp_path):
    images = tmp_path / "assets" / "car_images_unique"
    images.mkdir(parents=True)
    for name in ("lexus_rx300_2000.jpg", "lexus_rx_2002.jpg", "lexus_rx_2010.jpg"):
        Image.new("RGB", (40, 30), "red").save(images / name, "JPEG")
    service = ImageService(project_dir=tmp_path)
    cards = [card("lexus", "rx300", 2001, n) for n in range(1, 5)]
    assert names(service.with_unique_images(cards)) == [
        "lexus_rx300_2000.jpg", "lexus_rx_2002.jpg", "lexus_rx_2010.jpg", "lexus_rx300_2000.jpg"]
    # a model with no digit has no "family"
    assert service.candidates("honda", "fit", 2016, family=True) == []
