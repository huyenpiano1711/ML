"""Automated tests for the E02 controllers (no window is opened: the widgets are fakes)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from backend.schemas.vehicle_input import FEATURES, MODELS_BY_MAKE, OPTIONAL_FIELDS, REQUIRED_FIELDS, VehicleInput
from desktop_app.controllers import PAGE_VEHICLE
from desktop_app.controllers.vehicle_controller import (
    ENGLISH_LABELS,
    FIELD_NAMES,
    VehicleController,
    modelOptions,
    translateError,
)

PROJECT_DIR = Path(__file__).resolve().parents[1]
COMBO_FIELDS = ["manufacturer", "model_base", "type", "condition", "fuel", "transmission"]
ADVANCED_FIELDS = ["title_status", "state"]          # drive, cylinders, paint color are no longer on the form


class FakeCombo:
    def __init__(self):
        self.items = [("Select…", None)]
        self.index = 0
        self.enabled = True

    def clear(self):
        self.items, self.index = [], 0

    def addItem(self, text, data):
        self.items.append((text, data))

    def setEnabled(self, enabled):
        self.enabled = enabled

    def setMaxVisibleItems(self, count):
        pass

    def setCurrentIndex(self, index):
        self.index = index

    def currentData(self):
        return self.items[self.index][1]

    def select(self, value):
        """Pick a value, adding it first (the fake has no option list)."""
        if value not in [data for _, data in self.items]:
            self.addItem(str(value), value)
        self.index = [data for _, data in self.items].index(value)


class FakeSpinBox:
    def __init__(self, value):
        self.current = value

    def value(self):
        return self.current

    def setValue(self, value):
        self.current = value


class FakeLineEdit:
    def __init__(self, text=""):
        self.content = text
        self.focused = False

    def text(self):
        return self.content

    def setFocus(self):
        self.focused = True


class FakeLabel:
    def __init__(self):
        self.content = ""

    def setText(self, text):
        self.content = text


class FakeUi:
    """The parts of AutoWiseMainWindowEx the controllers use."""

    def __init__(self, full_name="", user=None):
        self.user = user
        self.full_name = full_name
        self.labelHeaderUser = FakeLabel()
        self.labelVehicleTitle = FakeLabel()
        self.required = {name: FakeCombo() for name in COMBO_FIELDS}
        self.optional = {name: FakeCombo() for name in ADVANCED_FIELDS}
        self.comboBoxManufacturer = self.required["manufacturer"]
        self.comboBoxModel = self.required["model_base"]
        self.spinBoxYear = FakeSpinBox(2015)
        self.spinBoxOdometer = FakeSpinBox(50_000)
        self.spinBoxBudget = FakeSpinBox(25_000)
        self.warnings = []
        self.pages = []

    def requiredCombos(self):
        return self.required

    def optionalCombos(self):
        return self.optional

    def userName(self):
        return self.full_name.strip()

    def showWarning(self, title, text):
        self.warnings.append((title, text))

    def goToPage(self, index):
        self.pages.append(index)


def _filled_ui() -> FakeUi:
    ui = FakeUi(full_name="Duy Le")
    values = {"manufacturer": "ford", "model_base": "f150", "type": "pickup",
              "condition": "good", "fuel": "gas", "transmission": "automatic"}
    for name, value in values.items():
        ui.required[name].select(value)
    return ui


def _shown_errors(ui: FakeUi) -> list[str]:
    assert len(ui.warnings) == 1
    return ui.warnings[0][1].split("\n")


# --------------------------------------------------------------------- Screen 2: buttons
def test_reset_clears_form_and_shows_vehicle_page():
    ui = _filled_ui()
    ui.optional["title_status"].select("rebuilt")
    VehicleController(ui).reset()

    for combo in list(ui.required.values()) + list(ui.optional.values()):
        assert combo.index == 0
    assert ui.spinBoxYear.value() == FEATURES["year"]["default"]
    assert ui.spinBoxOdometer.value() == FEATURES["odometer"]["default"]
    assert ui.spinBoxBudget.value() == FEATURES["budget_max_usd"]["default"]
    assert ui.pages == [PAGE_VEHICLE]


# --------------------------------------------------------------------- Screen 2: make -> models
def test_model_options_are_the_models_of_the_make():
    values = [value for _, value in modelOptions("ford")]

    assert values == sorted(MODELS_BY_MAKE["ford"])
    assert modelOptions("no such make") == []


def test_every_make_on_the_form_has_models():
    assert all(modelOptions(make) for make in FEATURES["manufacturer"]["ui_options"])


def test_refresh_models_follows_the_selected_make():
    ui = FakeUi()
    controller = VehicleController(ui)

    controller.refreshModels()
    assert not ui.comboBoxModel.enabled
    assert ui.comboBoxModel.currentData() is None

    ui.comboBoxManufacturer.select("ford")
    controller.refreshModels()
    assert ui.comboBoxModel.enabled
    assert ui.comboBoxModel.currentData() is None
    assert [data for _, data in ui.comboBoxModel.items[1:]] == sorted(MODELS_BY_MAKE["ford"])

    ui.comboBoxManufacturer.select("toyota")
    controller.refreshModels()
    assert [data for _, data in ui.comboBoxModel.items[1:]] == sorted(MODELS_BY_MAKE["toyota"])


# --------------------------------------------------------------------- Screen 2: validation
def test_valid_form_gives_vehicle_input_without_warning():
    ui = _filled_ui()
    ui.optional["title_status"].select("rebuilt")
    vehicle = VehicleController(ui).validatedInput()

    assert ui.warnings == []
    assert isinstance(vehicle, VehicleInput)
    assert vehicle.manufacturer == "ford"
    assert (vehicle.year, vehicle.odometer, vehicle.budget_max_usd) == (2015, 50_000, 25_000)
    assert vehicle.title_status == "rebuilt"
    assert (vehicle.drive, vehicle.cylinders, vehicle.paint_color) == (None, None, None)
    assert vehicle.user_name == "Duy Le"


def test_empty_form_asks_only_for_make_and_model():
    ui = FakeUi()
    assert VehicleController(ui).validatedInput() is None

    assert _shown_errors(ui) == ["• Make is required.", "• Model is required."]


def test_body_type_condition_fuel_transmission_are_optional():
    ui = FakeUi(full_name="Duy Le")
    ui.required["manufacturer"].select("ford")
    ui.required["model_base"].select("f150")
    vehicle = VehicleController(ui).validatedInput()

    assert ui.warnings == [] and vehicle is not None
    assert (vehicle.type, vehicle.condition, vehicle.fuel, vehicle.transmission) == (None, None, None, None)
    row = vehicle.to_model_row()
    assert all(row[name] == "unknown" for name in ("type", "condition", "fuel", "transmission"))


@pytest.mark.parametrize("box, value, expected", [
    ("spinBoxYear", 1980, "• Year must be between 1990 and 2022."),
    ("spinBoxOdometer", 500_000, "• Mileage must be between 0 and 400,000."),
    ("spinBoxBudget", 10, "• Budget must be between 1,000 and 150,000."),
])
def test_out_of_range_number_shows_its_own_error(box, value, expected):
    ui = _filled_ui()
    getattr(ui, box).setValue(value)

    assert VehicleController(ui).validatedInput() is None
    assert _shown_errors(ui) == [expected]


def test_several_errors_are_all_shown():
    ui = _filled_ui()
    ui.spinBoxYear.setValue(1980)
    ui.spinBoxBudget.setValue(10)
    ui.required["model_base"].select(None)

    assert VehicleController(ui).validatedInput() is None
    assert _shown_errors(ui) == ["• Model is required.",
                                 "• Year must be between 1990 and 2022.",
                                 "• Budget must be between 1,000 and 150,000."]


def test_model_of_another_make_is_rejected():
    ui = _filled_ui()
    ui.required["model_base"].select("camry")

    assert VehicleController(ui).validatedInput() is None
    assert _shown_errors(ui) == ["• Model 'camry' does not belong to make 'ford'."]


# --------------------------------------------------------------------- translation
def test_every_validate_message_is_translated():
    """Fails if D01 rewords a message in validate(), so the patterns can be updated."""
    label = FEATURES["year"]["ui_label"]
    errors = VehicleInput.from_dict({"manufacturer": "ford", "model_base": "camry", "year": 1980, "type": "boat",
                                     "odometer": "abc"}).validate()

    assert [translateError(error) for error in errors] == [
        "Budget is required.",
        "Year must be between 1990 and 2022.",
        "Mileage must be a number.",
        "Body type has an invalid value: 'boat'.",
        "Model 'camry' does not belong to make 'ford'.",
    ]
    assert f"'{label}' phải từ 1990 đến 2022." in errors


def test_every_form_field_has_an_english_name():
    assert set(FIELD_NAMES) == set(REQUIRED_FIELDS + OPTIONAL_FIELDS)
    assert set(ENGLISH_LABELS) == {FEATURES[name]["ui_label"] for name in FIELD_NAMES}


def test_unknown_message_is_kept_unchanged():
    assert translateError("Lỗi khác.") == "Lỗi khác."


# --------------------------------------------------------------------- no GUI dependency
def test_controllers_do_not_import_pyqt():
    code = ("import sys; import desktop_app.controllers.vehicle_controller, desktop_app.controllers.results_controller; "
            "sys.exit('PyQt6' in sys.modules)")
    assert subprocess.run([sys.executable, "-c", code], cwd=PROJECT_DIR).returncode == 0
