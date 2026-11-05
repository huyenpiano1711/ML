"""Automated tests for E03 (no window is opened: the widgets and the Backend service are fakes)."""
from __future__ import annotations

import re
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from backend import app_service as app_mod
from backend.schemas.result_schema import MAX_ALTERNATIVES, TOP_K, AnalysisResult, CarCard, PriceResult
from backend.schemas.vehicle_input import MODELS_BY_MAKE, VehicleInput
from desktop_app.controllers import PAGE_RESULTS
from desktop_app.controllers.results_controller import (
    BUDGET,
    MSG_NOT_STARTED,
    SIMILAR,
    SIMILAR_EMPTY,
    SIMILAR_NOTE,
    SIMILAR_UNAVAILABLE,
    TOP,
    TOP_EMPTY,
    TOP_NOTE,
    TOP_UNAVAILABLE,
    ResultsController,
    describeMessage,
    priceGapPct,
    translateMessage,
)
from desktop_app.controllers.vehicle_controller import modelOptions
from desktop_app.widgets.vehicle_card import MODEL_LABELS, VehicleCard, modelLabel
from src.recommendation.recommend import Recommender

PROJECT_DIR = Path(__file__).resolve().parents[1]

VEHICLE = VehicleInput.from_dict({
    "user_name": "Duy", "manufacturer": "ford", "model_base": "f150", "year": 2015, "type": "pickup",
    "odometer": 60_000, "condition": "good", "fuel": "gas", "transmission": "automatic", "budget_max_usd": 25_000,
})
PRICE = PriceResult(predicted_price=20_000, price_low=18_000, price_high=22_000, model_name="TestModel")
OVER_BUDGET = app_mod.MSG_PRICE_OVER_BUDGET.format(price="28.832", budget="25.000")


def _card(n: int = 1, price: float = 19_000, score: float | None = 0.9, image_path: str | None = "car.jpg") -> CarCard:
    return CarCard(id=n, manufacturer="ford", model_base="f150", year=2014, price=price, odometer=70_000,
                   type="pickup", condition="good", fuel="gas", transmission="automatic",
                   image_path=image_path, score=score)


def _result(**changes) -> AnalysisResult:
    values = {"success": True, "vehicle_title": VEHICLE.title, "price": PRICE,
              "top_matches": [_card(n) for n in range(1, TOP_K + 1)],
              "similar_price": [_card(n, score=None) for n in range(10, 10 + MAX_ALTERNATIVES)]}
    return AnalysisResult(**{**values, **changes})


class FakeWidget:
    """Stands for a QLabel, QFrame or QWidget."""

    def __init__(self, text="sample text from the .ui"):
        self.content = text
        self.visible = True
        self.properties = {}

    def setText(self, text):
        self.content = text

    def setVisible(self, visible):
        self.visible = visible

    def setProperty(self, name, value):
        self.properties[name] = value


class FakeScrollBar:
    def __init__(self):
        self.position = 500

    def setValue(self, value):
        self.position = value


class FakeScrollArea:
    def __init__(self):
        self.bar = FakeScrollBar()

    def verticalScrollBar(self):
        return self.bar


class FakeUi:
    """The parts of AutoWiseMainWindowEx the results controller uses. Any label/frame is created on request."""

    NO_SUCH_WIDGET = ("TopCar1Gap", "SimilarCar1Rank", "SimilarCar1Match", "SimilarCar1Specs")

    def __init__(self):
        self.scrollAreaResults = FakeScrollArea()
        self.warnings = []
        self.pages = []
        self.repolished = []
        for prefix, count in (("TopCar", TOP_K), ("SimilarCar", MAX_ALTERNATIVES)):
            for n in range(1, count + 1):
                setattr(self, f"frame{prefix}{n}", FakeWidget())
                parts = ["Image", "Title", "Detail", "Price"]
                parts += ["Rank", "Match", "Specs"] if prefix == "TopCar" else ["Gap"]
                for part in parts:
                    setattr(self, f"label{prefix}{n}{part}", FakeWidget())
        for name in ("labelResultsTitle", "labelSelectedVehicle", "labelPredictedPrice", "labelPriceRange",
                     "labelPriceNote", "labelBudgetValue", "labelBudgetVerdict", "labelBudgetNote", "labelTopNote",
                     "labelTopEmpty", "widgetTopMatches", "labelSimilarNote", "labelSimilarEmpty",
                     "widgetSimilarPrice"):
            setattr(self, name, FakeWidget())

    def userName(self):
        return "Duy"

    def goToPage(self, index):
        self.pages.append(index)

    def repolish(self, widget):
        self.repolished.append(widget)

    def settleLayout(self):
        self.pages.append("settled")

    def showWarning(self, title, text):
        self.warnings.append((title, text))


class FakeService:
    def __init__(self, result=None):
        self.result = result or _result()
        self.calls = []
        self.warmed = 0

    def analyze(self, form):
        self.calls.append(form)
        return self.result

    def warm_up(self):
        self.warmed += 1
        return []


def _setup(result=None):
    ui, service, images = FakeUi(), FakeService(result), []
    controller = ResultsController(ui, getService=lambda: service,
                                   setImage=lambda label, card: images.append((label, card.image_path)))
    return ui, controller, service, images


def _show(result):
    ui, controller, _, images = _setup(result)
    controller.show(VEHICLE, result)
    return ui, images


def _visible_cards(ui, prefix, count):
    return [n for n in range(1, count + 1) if getattr(ui, f"frame{prefix}{n}").visible]


# --------------------------------------------------------------------- connection to app_service
def test_analyze_sends_the_validated_form_to_the_service():
    ui, controller, service, _ = _setup()
    result = controller.analyze(VEHICLE)

    assert result is service.result
    assert service.calls == [VEHICLE.to_dict()]
    assert VehicleInput.from_dict(service.calls[0]).check() == VEHICLE


def test_default_service_is_app_service():
    from desktop_app.controllers.results_controller import defaultService
    assert defaultService() is app_mod.get_app_service()


def test_analyze_never_raises():
    def broken():
        raise ImportError("no backend")

    controller = ResultsController(FakeUi(), getService=broken, setImage=lambda label, card: None)
    result = controller.analyze(VEHICLE)

    assert not result.success
    assert result.errors == [MSG_NOT_STARTED]


def test_warm_up_runs_on_a_daemon_thread_without_blocking():
    release, done = threading.Event(), []

    class SlowService(FakeService):
        def warm_up(self):
            assert release.wait(timeout=10)
            done.append("warm_up")
            return ["some load error"]

        def analyze(self, form):
            done.append("analyze")
            return self.result

    service = SlowService()
    controller = ResultsController(FakeUi(), getService=lambda: service, setImage=lambda label, card: None)
    controller.warmUp()                                # returns although warm_up has not finished

    assert controller.warmThread.daemon
    assert controller.warmThread.is_alive() and done == []
    first = controller.warmThread
    controller.warmUp()
    assert controller.warmThread is first              # only one loading thread

    release.set()
    controller.analyze(VEHICLE)
    assert done == ["warm_up", "analyze"]              # a click during loading waits instead of loading twice


def test_failing_warm_up_is_not_fatal():
    def broken():
        raise RuntimeError("no backend")

    controller = ResultsController(FakeUi(), getService=broken, setImage=lambda label, card: None)
    controller.warmUp()
    controller.warmThread.join(timeout=10)

    assert not controller.warmThread.is_alive()


# --------------------------------------------------------------------- price and budget
def test_full_result_is_shown_on_screen_3():
    ui, images = _show(_result())

    assert ui.pages == [PAGE_RESULTS, "settled"]
    assert ui.warnings == []
    assert ui.labelResultsTitle.content == "Results for Duy"
    assert ui.labelSelectedVehicle.content == "Ford F150 2015 · 60,000 mi · Good · Gasoline · Automatic"
    assert ui.labelPredictedPrice.content == "$20,000"
    assert ui.labelPriceRange.content == "Reference range: $18,000 – $22,000"
    assert "TestModel" in ui.labelPriceNote.content and "MAE" in ui.labelPriceNote.content
    assert ui.scrollAreaResults.bar.position == 0
    assert len(images) == TOP_K + MAX_ALTERNATIVES


def test_price_without_range_does_not_mention_it():
    ui, _ = _show(_result(price=PriceResult(predicted_price=20_000, model_name="TestModel")))

    assert ui.labelPredictedPrice.content == "$20,000"
    assert ui.labelPriceRange.content == ""
    assert "MAE" not in ui.labelPriceNote.content


def test_within_budget():
    ui, _ = _show(_result())

    assert ui.labelBudgetValue.content == "$25,000"
    assert ui.labelBudgetVerdict.content == "WITHIN BUDGET"
    assert ui.labelBudgetVerdict.properties["state"] == "ok"
    assert ui.labelBudgetNote.content == "You would have about $5,000 left over at the estimated price."
    assert ui.repolished == [ui.labelBudgetVerdict]


def test_over_budget_shows_the_warning_of_the_backend_once():
    price = PriceResult(predicted_price=28_832)
    ui, _ = _show(_result(price=price, warnings=[OVER_BUDGET]))

    assert ui.labelBudgetVerdict.content == "OVER BUDGET"
    assert ui.labelBudgetVerdict.properties["state"] == "over"
    assert ui.labelBudgetNote.content == "The estimated price ($28,832) is above your maximum budget ($25,000)."
    assert ui.warnings == []


# --------------------------------------------------------------------- cards
def test_top_card_shows_every_field():
    ui, images = _show(_result(top_matches=[_card(image_path="top.jpg")]))

    assert ui.labelTopCar1Rank.content == "#1"
    assert ui.labelTopCar1Match.content == "90% MATCH"
    assert ui.labelTopCar1Title.content == "Ford F150 2014"
    assert ui.labelTopCar1Detail.content == "70,000 mi · Good"
    assert ui.labelTopCar1Specs.content == "Gasoline · Automatic"
    assert ui.labelTopCar1Price.content == "$19,000"
    assert images[0] == (ui.labelTopCar1Image, "top.jpg")


def test_similar_card_shows_the_gap_to_the_estimate():
    ui, _ = _show(_result(similar_price=[_card(price=21_000, score=None), _card(2, price=19_500, score=None)]))

    assert ui.labelSimilarCar1Gap.content == "+5.0% VS. ESTIMATE"
    assert ui.labelSimilarCar2Gap.content == "-2.5% VS. ESTIMATE"
    assert ui.labelSimilarCar1Price.content == "$21,000"


def test_gap_uses_the_formula_of_the_recommender():
    frame = Recommender(_catalog()).similar_price(10_000).cars
    assert len(frame) > 0
    for price, gap in zip(frame["price"], frame["price_gap_pct"]):
        assert priceGapPct(price, 10_000) == pytest.approx(gap)


@pytest.mark.parametrize("top, similar", [(5, 6), (3, 2), (1, 6), (5, 1)])
def test_extra_cards_are_hidden(top, similar):
    ui, _ = _show(_result(top_matches=[_card(n) for n in range(top)],
                          similar_price=[_card(n, score=None) for n in range(similar)]))

    assert _visible_cards(ui, "TopCar", TOP_K) == list(range(1, top + 1))
    assert _visible_cards(ui, "SimilarCar", MAX_ALTERNATIVES) == list(range(1, similar + 1))
    assert ui.widgetTopMatches.visible and not ui.labelTopEmpty.visible
    assert ui.widgetSimilarPrice.visible and not ui.labelSimilarEmpty.visible


@pytest.mark.parametrize("model, label", [
    ("f250sd", "F250SD"),         # a word with a digit
    ("2500hd", "2500HD"),
    ("3 series", "3 Series"),
    ("model 3", "Model 3"),
    ("model s", "Model S"),       # a word of 3 characters or fewer
    ("mdx", "MDX"),
    ("cla-class", "CLA-Class"),   # a hyphen also ends a word
    ("c-class", "C-Class"),
    ("golf", "Golf"),             # any other word
    ("camry", "Camry"),
    ("super duty", "Super Duty"),
    ("4runner", "4Runner"),       # own spelling
    ("300series", "300 Series"),
    ("mazda2", "Mazda2"),
    ("mazda3", "Mazda3"),
    ("mazda5", "Mazda5"),
    ("mazda6", "Mazda6"),
    ("santa fe", "Santa Fe"),
    ("town car", "Town Car"),
    ("grand am", "Grand Am"),
    ("fit", "Fit"),
    ("rio", "Rio"),
    ("ion", "Ion"),
    ("sky", "Sky"),
    ("eos", "Eos"),
    ("vue", "Vue"),
    ("cmax", "C-Max"),
    ("fpace", "F-Pace"),
    ("stype", "S-Type"),
    ("xtype", "X-Type"),
    ("eseries", "E-Series"),
    ("egolf", "e-Golf"),
    ("lacrosse", "LaCrosse"),
    ("lesabre", "LeSabre"),
    ("deville", "DeVille"),
    ("ecosport", "EcoSport"),
    ("promaster", "ProMaster"),
    ("granturismo", "GranTurismo"),
    ("eurovan", "EuroVan"),
    ("chr", "C-HR"),
    ("crv", "CR-V"),
    ("hrv", "HR-V"),
    ("crz", "CR-Z"),
    ("frs", "FR-S"),
    ("i3", "i3"),
    ("xa", "xA"),
    ("xb", "xB"),
    ("xd", "xD"),
    ("tc", "tC"),
    ("fortwo", "fortwo"),
])
def test_model_label_rule(model, label):
    assert modelLabel(model) == label


def test_every_own_spelling_is_a_real_model():
    names = {model for models in MODELS_BY_MAKE.values() for model in models}
    assert set(MODEL_LABELS) <= names


def test_labels_only_change_case_and_separators():
    """Guards the table against typos: the label of each of the real names has the same letters."""
    letters = lambda text: re.sub(r"[ -]", "", text).lower()
    for models in MODELS_BY_MAKE.values():
        for model in models:
            assert letters(modelLabel(model)) == letters(model)


def test_card_and_selected_vehicle_use_the_model_label():
    vehicle = replace(VEHICLE, model_base="f250sd")
    result = _result(top_matches=[replace(_card(), model_base="f250sd")],
                     similar_price=[replace(_card(score=None), model_base="f350sd")])
    ui, controller, _, _ = _setup(result)
    controller.show(vehicle, result)

    assert ui.labelTopCar1Title.content == "Ford F250SD 2014"
    assert ui.labelSimilarCar1Title.content == "Ford F350SD 2014"
    assert ui.labelSelectedVehicle.content.startswith("Ford F250SD 2015 · ")


def test_model_list_and_cards_follow_the_same_rule():
    options = modelOptions("ford")

    assert ("F250SD", "f250sd") in options
    assert all(text == modelLabel(value) for text, value in options)


def test_card_without_score_has_no_match_badge():
    ui, _ = _show(_result(top_matches=[_card(score=None)]))
    assert ui.labelTopCar1Match.content == ""


def test_card_widget_names_are_built_like_the_ui():
    ui = FakeUi()
    card = VehicleCard(ui, "SimilarCar", 6, setImage=lambda label, c: None)

    assert card.frame is ui.frameSimilarCar6
    assert card.labelGap is ui.labelSimilarCar6Gap
    assert card.labelRank is None and card.labelMatch is None and card.labelSpecs is None


# --------------------------------------------------------------------- partial results
def test_model_error_still_shows_top_5():
    result = _result(success=False, price=None, similar_price=[],
                     errors=[app_mod.MSG_MODEL_ERROR], warnings=[app_mod.MSG_NO_PRICE_FOR_ALTERNATIVES])
    ui, _ = _show(result)

    assert ui.pages == [PAGE_RESULTS, "settled"]
    assert ui.labelPredictedPrice.content == "N/A"
    assert ui.labelPriceRange.content == ""
    assert ui.labelBudgetValue.content == "$25,000"
    assert ui.labelBudgetVerdict.content == "NOT AVAILABLE"
    assert ui.labelBudgetVerdict.properties["state"] == ""
    assert _visible_cards(ui, "TopCar", TOP_K) == [1, 2, 3, 4, 5]
    assert ui.labelSimilarEmpty.visible and ui.labelSimilarEmpty.content == SIMILAR_UNAVAILABLE
    assert "no estimated price" in ui.labelSimilarNote.content
    assert ui.warnings == [("Some results are unavailable",
                            "• The price model failed, so no price can be estimated for this car.")]


def test_catalog_error_still_shows_the_price():
    result = _result(success=False, top_matches=[], similar_price=[], errors=[app_mod.MSG_CATALOG_ERROR])
    ui, _ = _show(result)

    assert ui.pages == [PAGE_RESULTS, "settled"]
    assert ui.labelPredictedPrice.content == "$20,000"
    assert ui.labelTopEmpty.visible and ui.labelTopEmpty.content == TOP_UNAVAILABLE
    assert ui.labelSimilarEmpty.visible and ui.labelSimilarEmpty.content == SIMILAR_UNAVAILABLE
    assert not ui.widgetTopMatches.visible and not ui.widgetSimilarPrice.visible
    assert ui.warnings[0][1] == "• The car list could not be loaded."


def test_images_are_drawn_after_the_layout_and_before_the_error_dialog():
    order = []
    result = _result(success=False, price=None, top_matches=[_card()], similar_price=[_card(2, score=None)],
                     errors=[app_mod.MSG_MODEL_ERROR])
    ui = FakeUi()
    ui.goToPage = lambda index: order.append("page")
    ui.settleLayout = lambda: order.append("layout")
    ui.showWarning = lambda title, text: order.append("dialog")
    controller = ResultsController(ui, getService=FakeService, setImage=lambda label, card: order.append(label))
    controller.show(VEHICLE, result)

    assert order == ["page", "layout", ui.labelTopCar1Image, ui.labelSimilarCar1Image, "dialog"]


def test_nothing_to_show_stays_on_screen_2():
    result = AnalysisResult(success=False, errors=[app_mod.MSG_MODEL_ERROR, app_mod.MSG_CATALOG_ERROR],
                            warnings=[])
    ui, _ = _show(result)

    assert ui.pages == []
    assert ui.warnings == [("Could not analyze this car",
                            "• The price model failed, so no price can be estimated for this car.\n"
                            "• The car list could not be loaded.")]


def test_nothing_to_show_also_lists_the_warnings():
    no_car = "Không có xe nào trong dữ liệu có giá không vượt quá 1.000 USD. Hãy tăng ngân sách."
    result = AnalysisResult(success=False, errors=[app_mod.MSG_MODEL_ERROR], warnings=[no_car])
    ui, _ = _show(result)

    assert ui.pages == []
    assert "No car is priced at or under $1,000" in ui.warnings[0][1]


# --------------------------------------------------------------------- empty lists and warnings
def test_no_car_shows_the_empty_messages_without_a_dialog():
    ui, _ = _show(_result(top_matches=[], similar_price=[]))

    assert ui.labelTopEmpty.visible and ui.labelTopEmpty.content == TOP_EMPTY
    assert ui.labelSimilarEmpty.visible and ui.labelSimilarEmpty.content == SIMILAR_EMPTY
    assert not ui.widgetTopMatches.visible and not ui.widgetSimilarPrice.visible
    assert _visible_cards(ui, "TopCar", TOP_K) == []
    assert _visible_cards(ui, "SimilarCar", MAX_ALTERNATIVES) == []
    assert ui.labelTopNote.content == ""
    assert ui.warnings == []


def test_model_error_with_catalog_ok_keeps_the_budget_message_for_top_5():
    """The list is really empty: the catalog worked, only the price model failed."""
    ui, _ = _show(_result(success=False, price=None, top_matches=[], similar_price=[_card(score=None)],
                          errors=[app_mod.MSG_MODEL_ERROR]))

    assert ui.labelTopEmpty.content == TOP_EMPTY


def test_warnings_go_next_to_their_list_without_a_dialog():
    top = "Chỉ tìm được 2 xe phù hợp trong ngân sách 5.000 USD (yêu cầu 5)."
    similar = "Đã mở rộng khoảng giá lên ±15% để đủ xe."
    ui, _ = _show(_result(warnings=[top, similar]))

    assert ui.labelTopNote.content == f"{TOP_NOTE} Only 2 of the 5 requested cars fit your $5,000 budget."
    assert ui.labelSimilarNote.content == f"{SIMILAR_NOTE} The price range was widened to ±15% to find enough cars."
    assert ui.warnings == []


def test_unknown_warning_is_shown_unchanged():
    ui, _ = _show(_result(warnings=["Một cảnh báo mới."]))
    assert ui.labelTopNote.content == f"{TOP_NOTE} Một cảnh báo mới."


def test_next_analysis_leaves_nothing_of_the_previous_one():
    ui, controller, _, _ = _setup()
    controller.show(VEHICLE, _result(success=False, price=None, top_matches=[], similar_price=[_card(score=None)],
                                     errors=[app_mod.MSG_CATALOG_ERROR], warnings=["Một cảnh báo mới."]))
    controller.show(VEHICLE, _result())

    assert ui.labelPredictedPrice.content == "$20,000"
    assert ui.labelBudgetVerdict.content == "WITHIN BUDGET"
    assert ui.labelTopNote.content == TOP_NOTE
    assert ui.labelSimilarNote.content == SIMILAR_NOTE
    assert ui.widgetTopMatches.visible and not ui.labelTopEmpty.visible
    assert _visible_cards(ui, "TopCar", TOP_K) == [1, 2, 3, 4, 5]


# --------------------------------------------------------------------- translation
def _row(n: int, price: int) -> dict:
    return {"id": n, "manufacturer": "ford", "model_base": f"model{n}", "make_model": f"ford model{n}",
            "year": 2015, "car_age": 6, "price": price, "odometer": 50_000, "type": "pickup", "condition": "good",
            "fuel": "gas", "transmission": "automatic", "drive": "4wd", "image_path": None, "image_match": "none"}


def _catalog() -> pd.DataFrame:
    return pd.DataFrame([_row(n, 8_000 + 300 * n) for n in range(10)])


@pytest.mark.parametrize("message, english", [
    (app_mod.MSG_BAD_FORM, "The form data was sent in the wrong format."),
    (app_mod.MSG_MODEL_MISSING.format(path="final_pipeline.joblib"),
     "The price model file (final_pipeline.joblib) was not found, so no price can be estimated."),
    (app_mod.MSG_MODEL_ERROR, "The price model failed, so no price can be estimated for this car."),
    (app_mod.MSG_CATALOG_MISSING,
     "The car list (recommendation_catalog.pkl) is missing. Run: python -m src.recommendation.build_catalog"),
    (app_mod.MSG_CATALOG_ERROR, "The car list could not be loaded."),
    (app_mod.MSG_RECOMMEND_ERROR, "The recommendation feature failed, so no matching cars could be found."),
    (app_mod.MSG_ALTERNATIVE_ERROR, "Finding cars in the same price range failed."),
    (app_mod.MSG_NO_PRICE_FOR_ALTERNATIVES,
     "There is no estimated price, so cars in the same price range cannot be found."),
    (OVER_BUDGET, "The estimated price ($28,832) is above your maximum budget ($25,000)."),
])
def test_app_service_messages_are_translated(message, english):
    """Reads the constants of app_service.py, so it fails if the Backend rewords one of them."""
    assert translateMessage(message) == english


def test_unexpected_error_message_of_analyze_is_translated():
    """This sentence has no constant in app_service.py: it comes from a real failing analyze()."""
    class Broken(app_mod.AppService):
        def _analyze(self, form, timings):
            raise RuntimeError("boom")

    message = Broken().analyze({}).errors[0]
    assert translateMessage(message) == "An unexpected error occurred during the analysis. Please try again."


QUERY = {"budget_max_usd": 1_000, "preferences": {"manufacturer": "ford"}}


@pytest.mark.parametrize("make_warnings, english, section", [
    (lambda r: r.recommend(QUERY).warnings[0], "No car is priced at or under $1,000. Try a higher budget.", TOP),
    (lambda r: r.recommend(QUERY, strict=["manufacturer"]).warnings[0],
     "No car priced at or under $1,000 matches the required conditions.", TOP),
    (lambda r: r.recommend({**QUERY, "budget_max_usd": 8_400}).warnings[0],
     "Only 2 of the 5 requested cars fit your $8,400 budget.", TOP),
    (lambda r: r.similar_price(100_000).warnings[0], "No car is priced within ±30% of $100,000.", SIMILAR),
    (lambda r: r.similar_price(9_000, k=20).warnings[0], "Only 10 cars are priced close to $9,000.", SIMILAR),
    (lambda r: r.similar_price(9_000, k=20).warnings[1], "The price range was widened to ±30% to find enough cars.",
     SIMILAR),
])
def test_recommender_warnings_are_translated(make_warnings, english, section):
    """Runs the real Recommender on a small catalog, so it fails if recommend.py rewords a warning."""
    assert describeMessage(make_warnings(Recommender(_catalog()))) == (english, section)


def test_validate_messages_use_the_translation_of_e02():
    errors = VehicleInput.from_dict({"manufacturer": "ford"}).validate()
    assert translateMessage(errors[0]) == "Model is required."


def test_over_budget_message_goes_to_the_budget_card():
    assert describeMessage(OVER_BUDGET)[1] == BUDGET


def test_unknown_message_is_kept_unchanged():
    assert translateMessage("Một lỗi hoàn toàn mới.") == "Một lỗi hoàn toàn mới."


# --------------------------------------------------------------------- no GUI dependency
def test_results_code_needs_neither_pyqt_nor_the_loaded_backend_at_import():
    code = ("import sys; import desktop_app.controllers.results_controller; "
            "sys.exit('PyQt6' in sys.modules or 'backend.app_service' in sys.modules)")
    assert subprocess.run([sys.executable, "-c", code], cwd=PROJECT_DIR).returncode == 0


# ---------------------------------------------------------------- placeholder image (dark tile instead)
def test_placeholder_image_is_detected():
    from backend.services.image_service import PLACEHOLDER_PATH
    from desktop_app.widgets.vehicle_card import isPlaceholder
    assert isPlaceholder(None)
    assert isPlaceholder("")
    assert isPlaceholder(str(PLACEHOLDER_PATH))
    assert not isPlaceholder(str(PLACEHOLDER_PATH.parent / "car_images_unique" / "ford_f150_2015.jpg"))


def test_body_type_text_on_dark_tile():
    from types import SimpleNamespace
    from desktop_app.widgets.vehicle_card import bodyTypeText
    assert bodyTypeText(SimpleNamespace(type="sedan")) == "SEDAN"
    assert bodyTypeText(SimpleNamespace(type="unknown")) == "CAR"
    assert bodyTypeText(SimpleNamespace(type=None)) == "CAR"
