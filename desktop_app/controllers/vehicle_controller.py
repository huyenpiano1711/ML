"""
vehicle_controller.py - Screen 2 (pageVehicle): BACK, reset, make -> model list, form validation.
`ui` is the AutoWiseMainWindowEx that owns the widgets.

The rules stay in VehicleInput.validate() (Vietnamese messages, owned by D01); this file only
translates its messages, because the interface is in English.
"""
import re

from backend.schemas.vehicle_input import VehicleInput, FEATURES, MODELS_BY_MAKE
from desktop_app.controllers import PAGE_WELCOME, PAGE_VEHICLE

FIELD_NAMES = {"manufacturer": "Make", "model_base": "Model", "year": "Year", "type": "Body type",
               "odometer": "Mileage", "condition": "Condition", "fuel": "Fuel",
               "transmission": "Transmission", "budget_max_usd": "Budget",
               "drive": "Drive", "cylinders": "Cylinders", "paint_color": "Paint color",
               "title_status": "Title status", "state": "U.S. state"}

# ui_label in feature_schema.json (used in the messages of validate()) -> English name
ENGLISH_LABELS = {FEATURES[name]["ui_label"]: english for name, english in FIELD_NAMES.items()}

# Message patterns of VehicleInput.validate(). tests/test_e02_controllers.py fails if they drift apart.
MISSING = re.compile(r"Chưa nhập '(.+)'\.")
NOT_A_NUMBER = re.compile(r"'(.+)' phải là số\.")
OUT_OF_RANGE = re.compile(r"'(.+)' phải từ (\S+) đến (\S+)\.")
INVALID_VALUE = re.compile(r"'(.+)' không hợp lệ: (.+)\.")
WRONG_MAKE = re.compile(r"Dòng xe (.+) không thuộc hãng (.+)\.")


def translateError(error):
    """English version of one validate() message; an unknown message is returned unchanged."""
    if match := MISSING.fullmatch(error):
        return f"{ENGLISH_LABELS[match[1]]} is required."
    if match := NOT_A_NUMBER.fullmatch(error):
        return f"{ENGLISH_LABELS[match[1]]} must be a number."
    if match := OUT_OF_RANGE.fullmatch(error):
        low, high = match[2].replace(".", ","), match[3].replace(".", ",")      # 400.000 -> 400,000
        return f"{ENGLISH_LABELS[match[1]]} must be between {low} and {high}."
    if match := INVALID_VALUE.fullmatch(error):
        return f"{ENGLISH_LABELS[match[1]]} has an invalid value: {match[2]}."
    if match := WRONG_MAKE.fullmatch(error):
        return f"Model {match[1]} does not belong to make {match[2]}."
    return error


def modelOptions(make):
    """(display text, value) of every model of a make, from MODELS_BY_MAKE."""
    return [(model.upper() if len(model) <= 4 else model.title(), model)
            for model in sorted(MODELS_BY_MAKE.get(make, []))]


class VehicleController:
    def __init__(self, ui):
        self.ui = ui

    def goBack(self):
        self.ui.goToPage(PAGE_WELCOME)

    def reset(self):
        """Clear the form and show Screen 2. Any button can use it: button.clicked.connect(controller.reset)"""
        for combo in list(self.ui.requiredCombos().values()) + list(self.ui.optionalCombos().values()):
            combo.setCurrentIndex(0)
        self.ui.spinBoxYear.setValue(FEATURES["year"]["default"])
        self.ui.spinBoxOdometer.setValue(FEATURES["odometer"]["default"])
        self.ui.spinBoxBudget.setValue(int(FEATURES["budget_max_usd"]["default"]))
        self.ui.goToPage(PAGE_VEHICLE)

    def refreshModels(self):
        make = self.ui.comboBoxManufacturer.currentData()
        self.ui.comboBoxModel.clear()
        if make is None:
            self.ui.comboBoxModel.addItem("Select a make first…", None)
            self.ui.comboBoxModel.setEnabled(False)
            return
        self.ui.comboBoxModel.setEnabled(True)
        self.ui.comboBoxModel.addItem("Select model…", None)
        for text, model in modelOptions(make):
            self.ui.comboBoxModel.addItem(text, model)
        self.ui.comboBoxModel.setMaxVisibleItems(14)

    def collectInput(self):
        data = {name: combo.currentData() for name, combo in self.ui.requiredCombos().items()}
        data.update({name: combo.currentData() for name, combo in self.ui.optionalCombos().items()})
        data["year"] = self.ui.spinBoxYear.value()
        data["odometer"] = self.ui.spinBoxOdometer.value()
        data["budget_max_usd"] = self.ui.spinBoxBudget.value()
        data["user_name"] = self.ui.userName()
        return VehicleInput.from_dict(data)

    def validatedInput(self):
        """The VehicleInput to send to the Backend, or None after showing every error."""
        vehicle = self.collectInput()
        errors = vehicle.validate()
        if errors:
            self.ui.showWarning("Please check your information",
                                "\n".join(f"• {translateError(error)}" for error in errors))
            return None
        return vehicle
