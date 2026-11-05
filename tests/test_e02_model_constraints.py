"""Ràng buộc theo dòng xe (src/features/model_constraints.json) + ảnh bị gộp khi khử trùng (image_aliases.csv)."""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from backend.schemas.result_schema import CarCard
from backend.schemas.vehicle_input import FEATURES
from backend.services.image_service import ImageService, load_aliases
from desktop_app.controllers.vehicle_controller import constraintMessage
from src.features.model_constraints import CATEGORICAL, constraints_for, load_constraints, violations


def vehicle(**kw):
    base = dict(manufacturer="lexus", model_base="rx300", year=2001, type="suv", fuel="gas",
                transmission="automatic")
    base.update(kw)
    return SimpleNamespace(**base)


def test_every_model_has_a_valid_year_range_and_known_values():
    models = load_constraints()
    assert sum(len(v) for v in models.values()) > 2000
    for make, by_model in models.items():
        for model, c in by_model.items():
            assert FEATURES["year"]["min"] <= c["year"][0] <= c["year"][1] <= FEATURES["year"]["max"], (make, model)
            for name in CATEGORICAL:
                assert set(c[name]) <= set(FEATURES[name]["ui_options"]), (make, model, name)


def test_lexus_rx300_matches_the_real_car():
    c = constraints_for("lexus", "rx300")
    assert c["year"] == [1999, 2003]
    assert c["type"] == ["suv"] and c["fuel"] == ["gas"]


def test_real_car_has_no_violation():
    assert violations(vehicle()) == []
    assert violations(vehicle(manufacturer="ford", model_base="f150", year=2015, type="pickup")) == []


def test_impossible_car_is_reported():
    found = dict(violations(vehicle(year=2020, fuel="diesel")))
    assert found["year"] == (1999, 2003)
    assert found["fuel"] == ["gas"]


def test_unknown_model_is_not_constrained():
    assert constraints_for("lexus", "no-such-model") is None
    assert violations(vehicle(model_base="no-such-model", year=2022)) == []


def test_constraint_messages_are_english():
    car = vehicle()
    assert constraintMessage(car, "year", (1999, 2003)) == \
        "Lexus RX300 is only listed from 1999 to 2003 in the data. Please pick a year in that range."
    assert constraintMessage(car, "fuel", ["gas"]) == \
        "Fuel of Lexus RX300 in the data: Gasoline. Please pick one of them."


def test_aliases_bring_back_photos_removed_by_deduplication(tmp_path):
    images = tmp_path / "assets" / "car_images_unique"
    images.mkdir(parents=True)
    Image.new("RGB", (40, 30), "red").save(images / "lexus_rx_1999.jpg", "JPEG")
    (tmp_path / "assets" / "image_aliases.csv").write_text(
        "alias,file\nlexus_rx300_1999.jpg,lexus_rx_1999.jpg\nlexus_rx300_2001.jpg,missing.jpg\n", encoding="utf-8")
    service = ImageService(project_dir=tmp_path)
    card = CarCard(id=1, manufacturer="lexus", model_base="rx300", year=2001, price=5000, odometer=1,
                   type="suv", condition="good", fuel="gas", transmission="automatic")
    assert Path(service.with_unique_images([card])[0].image_path).name == "lexus_rx_1999.jpg"
    assert load_aliases(tmp_path / "nope.csv") == {}


def test_alias_file_of_the_repo_points_to_kept_files():
    aliases = load_aliases(Path(__file__).resolve().parents[1] / "assets" / "image_aliases.csv")
    assert len(aliases) > 1800
    assert aliases["lexus_rx300_1999.jpg"] == "lexus_rx_1999.jpg"
