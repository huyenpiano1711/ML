"""Input rules added after the test sheet: account, names, mileage, card details, environment at start-up."""
from __future__ import annotations

import pytest

from desktop_app.connectors.connector import Connector
from desktop_app.controllers.results_controller import FIX_ENVIRONMENT, STARTUP_TITLE, ResultsController, environmentProblems
from desktop_app.controllers.vehicle_controller import MAX_MILES_NEW, MAX_MILES_PER_YEAR, VehicleController, mileageMessages
from desktop_app.dal.user_dao import MAX_NAME_LENGTH, UserDao, nameError, passwordError
from desktop_app.widgets.vehicle_card import known, labelOf
from tests.test_e02_controllers import _filled_ui, _shown_errors
from tests.test_e03_results import FakeService, FakeUi as ResultsUi


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Accounts go to a temporary SQLite file, never to desktop_app/databases/autowise.sqlite."""
    monkeypatch.setattr(Connector.__init__, "__defaults__", (tmp_path / "test.sqlite",))
    return tmp_path


# --------------------------------------------------------------------- names
@pytest.mark.parametrize("name", ["Duy Le", "Nguyễn Thị Như Huyền", "Anne-Marie O'Neil", "J. R. Smith"])
def test_real_names_are_accepted(name):
    assert nameError(name) is None


@pytest.mark.parametrize("name", ["12345", "!!!", "@@@ ###", "Duy2", "<h1 style='color:red'>Duy</h1>", "A" * (MAX_NAME_LENGTH + 1)])
def test_names_without_letters_symbols_or_too_long_are_rejected(name):
    assert nameError(name) is not None


# --------------------------------------------------------------------- account
@pytest.mark.parametrize("pwd", ["aaaaaa", "123456", "abcdef", "abcdefgh", "12345678", "a1b2c3", "a1" * 40])
def test_weak_or_too_long_passwords_are_rejected(pwd):
    assert passwordError(pwd) is not None


def test_password_with_letters_and_numbers_is_accepted():
    assert passwordError("autowise2021") is None


def test_register_rejects_bad_name_and_weak_password(temp_db):
    errors = UserDao.validateRegister("12345", "duy_le", "", "aaaaaa", "aaaaaa")
    assert any("Full name" in error for error in errors)
    assert any("Password" in error for error in errors)


def test_one_email_cannot_register_two_accounts(temp_db):
    assert UserDao.validateRegister("Duy Le", "duy_le", "duy@uel.edu.vn", "autowise2021", "autowise2021") == []
    assert UserDao.register("Duy Le", "duy_le", "duy@uel.edu.vn", "autowise2021") is not None
    errors = UserDao.validateRegister("Duy Khac", "duy_khac", "DUY@uel.edu.vn", "autowise2021", "autowise2021")
    assert errors == ["This email is already used by another account."]


def test_too_long_email_is_rejected(temp_db):
    email = "a" * 95 + "@b.com"
    assert "Please enter a valid email address." in UserDao.validateRegister("Duy Le", "duy_le", email, "autowise2021", "autowise2021")


def test_login_is_locked_after_five_wrong_passwords(tmp_path):
    pytest.importorskip("PyQt6")
    from PyQt6.QtCore import QSettings
    from desktop_app.UI.LoginMainWindowEx import LOCK_SECONDS, MAX_FAILED_LOGINS, LoginMainWindowEx

    login = LoginMainWindowEx.__new__(LoginMainWindowEx)          # no window: only the lock logic
    login.settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    assert login.lockedMinutes("duy") == 0
    results = [login.recordFailedLogin("Duy") for _ in range(MAX_FAILED_LOGINS)]
    assert results == [False] * (MAX_FAILED_LOGINS - 1) + [True]
    assert login.lockedMinutes("duy") == LOCK_SECONDS // 60       # same username, any letter case
    login.clearFailedLogins("duy")
    assert login.lockedMinutes("duy") == 0


# --------------------------------------------------------------------- mileage
def _vehicle(year, odometer, condition="good"):
    ui = _filled_ui()
    ui.spinBoxYear.setValue(year)
    ui.spinBoxOdometer.setValue(odometer)
    ui.required["condition"].select(condition)
    return ui


def test_400000_miles_on_a_2021_car_is_rejected():
    ui = _vehicle(2021, 400_000)
    assert VehicleController(ui).validatedInput() is None
    assert any("too much for a 2021 car" in error for error in _shown_errors(ui))


def test_new_car_with_150000_miles_is_rejected():
    ui = _vehicle(2010, 150_000, "new")
    assert VehicleController(ui).validatedInput() is None
    assert any("A new car has at most" in error for error in _shown_errors(ui))


@pytest.mark.parametrize("year, odometer, condition", [(2015, 90_000, "good"), (2021, MAX_MILES_PER_YEAR, "excellent"),
                                                        (2020, 8_000, "new"), (2005, 400_000, "fair")])
def test_normal_mileage_is_accepted(year, odometer, condition):
    ui = _vehicle(year, odometer, condition)
    assert VehicleController(ui).validatedInput() is not None and ui.warnings == []


def test_mileage_limits_follow_the_model_car_age():
    vehicle = VehicleController(_vehicle(2019, 2 * MAX_MILES_PER_YEAR + 1)).collectInput()
    assert mileageMessages(vehicle)                            # 2021 - 2019 = 2 years
    assert MAX_MILES_NEW < MAX_MILES_PER_YEAR


# --------------------------------------------------------------------- cards and start-up
def test_card_details_leave_out_unknown_values():
    assert known("70,000 mi", labelOf("condition", "unknown")) == ["70,000 mi"]
    assert known(labelOf("fuel", "gas"), labelOf("transmission", "unknown")) == ["Gasoline"]


def test_wrong_library_versions_are_reported():
    fake = {"scikit-learn": "1.6.0", "numpy": "1.26.4", "pandas": "2.2.3"}.get
    problems = environmentProblems(getVersion=fake)
    assert len(problems) == 3 and "scikit-learn==1.9.1" in problems[0]
    assert environmentProblems(getVersion={"scikit-learn": "1.9.1", "numpy": "2.3.0", "pandas": "3.0.5"}.get) == []


def test_start_up_problems_are_shown_at_once(monkeypatch):
    import desktop_app.controllers.results_controller as rc

    class BrokenService(FakeService):
        def warm_up(self):
            return ["Mô hình dự đoán giá gặp lỗi, chưa thể dự đoán giá cho xe này."]

    posted = []
    ui = ResultsUi()
    ui.postBackendProblems = lambda title, text: posted.append((title, text))
    monkeypatch.setattr(rc, "environmentProblems", lambda: ["scikit-learn 1.6.0 is installed, but AutoWise needs scikit-learn==1.9.1."])
    controller = ResultsController(ui, getService=BrokenService, setImage=lambda label, card: None)
    controller.loadBackend()

    assert len(posted) == 1 and posted[0][0] == STARTUP_TITLE
    assert "scikit-learn==1.9.1" in posted[0][1] and FIX_ENVIRONMENT in posted[0][1]
    assert "The price model failed" in posted[0][1]


def test_nothing_is_shown_when_the_backend_loads(monkeypatch):
    import desktop_app.controllers.results_controller as rc

    posted = []
    ui = ResultsUi()
    ui.postBackendProblems = lambda title, text: posted.append((title, text))
    monkeypatch.setattr(rc, "environmentProblems", lambda: [])
    ResultsController(ui, getService=FakeService, setImage=lambda label, card: None).loadBackend()
    assert posted == []


# --------------------------------------------------------------------- optional choices, searchable make / model
def test_backend_works_with_only_the_required_fields():
    from backend.app_service import get_app_service

    result = get_app_service().analyze({"manufacturer": "toyota", "model_base": "camry", "year": 2015,
                                        "odometer": 90_000, "budget_max_usd": 15_000})
    assert result.success and result.price is not None and result.price.predicted_price > 0
    assert len(result.top_matches) == 5 and all(card.manufacturer == "toyota" for card in result.top_matches)


@pytest.fixture(scope="module")
def main_window():
    pytest.importorskip("PyQt6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from desktop_app.UI.AutoWiseMainWindowEx import AutoWiseMainWindowEx

    app = QApplication.instance() or QApplication([])
    ui = AutoWiseMainWindowEx(None, None)
    window = QMainWindow()
    ui.setupUi(window)
    app.processEvents()
    yield ui
    window.close()


def test_drive_cylinders_paint_color_are_not_on_the_form(main_window):
    for name in ("comboBoxDrive", "comboBoxCylinders", "comboBoxPaintColor"):
        assert not hasattr(main_window, name)
    assert set(main_window.optionalCombos()) == {"title_status", "state"}


def test_choice_fields_start_at_not_sure(main_window):
    for name in ("type", "condition", "fuel", "transmission"):
        combo = main_window.requiredCombos()[name]
        assert combo.itemText(0) == "Not sure" and combo.itemData(0) is None


@pytest.mark.parametrize("typed, expected", [("Toyota", "toyota"), ("toyota", "toyota"), ("toyo", "toyota"),
                                             ("mercedes", "mercedes-benz"), ("zzz", None), ("", None)])
def test_make_can_be_typed(main_window, typed, expected):
    combo = main_window.comboBoxManufacturer
    assert combo.isEditable()
    combo.setCurrentIndex(0)
    combo.lineEdit().setText(typed)
    main_window.matchTypedText(combo)
    assert combo.currentData() == expected


def test_model_can_be_typed_after_the_make(main_window):
    make, model = main_window.comboBoxManufacturer, main_window.comboBoxModel
    make.setCurrentIndex(make.findData("ford"))
    model.lineEdit().setText("F150")
    main_window.matchTypedText(model)
    assert model.isEditable() and model.currentData() == "f150"


def test_click_on_a_car_card_opens_its_details(main_window, monkeypatch):
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtWidgets import QApplication
    import desktop_app.UI.AutoWiseMainWindowEx as mw
    from tests.test_e03_results import VEHICLE, _result

    opened = []
    monkeypatch.setattr(mw, "openCarDetails", lambda parent, card, details: opened.append((card, details)))
    main_window.resultsController.show(VEHICLE, _result())
    frame = main_window.frameTopCar2
    assert frame.cursor().shape() == Qt.CursorShape.PointingHandCursor
    release = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(5, 5), QPointF(5, 5), Qt.MouseButton.LeftButton,
                          Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(frame, release)
    assert len(opened) == 1 and opened[0][0].id == 2 and opened[0][1][0].startswith("#2 BEST MATCH")


def test_details_window_shows_the_rows():
    pytest.importorskip("PyQt6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QDialog, QLabel
    from desktop_app.UI.CarDetailsDialogEx import CarDetailsDialogEx
    from desktop_app.widgets.vehicle_card import carDetails
    from tests.test_e03_results import _card

    app = QApplication.instance() or QApplication([])
    dialog = QDialog()
    ui = CarDetailsDialogEx()
    ui.setupUi(dialog)
    card = _card(7)
    ui.showCar(card, carDetails(card, rank=1, budget=25_000, estimate=20_000))
    texts = [label.text() for label in ui.frameDetails.findChildren(QLabel)]
    assert ui.labelTitle.text() == "Ford F150 2014" and ui.labelPrice.text() == "$19,000"
    assert "MILEAGE" in texts and "70,000 mi" in texts and "7" in texts
    dialog.close()


# --------------------------------------------------------------------- title status and unusually low prices
def test_catalog_keeps_title_status_and_state():
    import pandas as pd
    from src.config import PROCESSED_DIR
    catalog = pd.read_pickle(PROCESSED_DIR / "recommendation_catalog.pkl")
    assert {"title_status", "state"} <= set(catalog.columns)
    assert {"clean", "rebuilt", "salvage"} <= set(catalog["title_status"])


def test_backend_estimates_a_usual_price_for_every_recommended_car():
    from backend.app_service import get_app_service

    result = get_app_service().analyze({"manufacturer": "gmc", "model_base": "acadia", "year": 2018,
                                        "odometer": 60_000, "budget_max_usd": 20_000})
    cards = result.top_matches + result.similar_price
    assert all(card.title_status for card in cards)
    assert sum(card.fair_price is not None for card in cards) >= len(cards) - 1
    rebuilt = [card for card in cards if card.title_status == "rebuilt"]
    for card in rebuilt:              # the model prices a rebuilt car lower than the clean estimate of the page
        assert card.fair_price < result.price.predicted_price


def test_predict_prices_skips_a_bad_row_only():
    from src.prediction.predict import predict_prices
    good = {"manufacturer": "toyota", "model_base": "camry", "year": 2015, "odometer": 90_000, "budget_max_usd": 10_000}
    prices = predict_prices([good, {**good, "model_base": "not-a-model"}, good])
    assert prices[0] and prices[2] and prices[1] is None and prices[0] == prices[2]


def test_card_shows_title_and_low_price():
    from desktop_app.widgets.vehicle_card import carDetails, isLowPrice, titleWarning
    from tests.test_e03_results import _card

    card = _card(1, price=14_900)
    card.title_status, card.state, card.fair_price = "rebuilt", "tx", 18_458
    assert titleWarning(card) == "Rebuilt title" and not isLowPrice(card)
    rows = dict(carDetails(card, rank=1)[3])
    assert rows["Title status"].startswith("Rebuilt") and rows["Listed in"] == "TX (U.S. state)"
    assert rows["Usual price for this car"].startswith("About $18,458")
    assert "clean title" in rows["Warning"]

    card.title_status, card.fair_price = "clean", 27_000
    assert titleWarning(card) == "" and isLowPrice(card)
    assert "45% below the usual price" in dict(carDetails(card, rank=1)[3])["Warning"]

    card.title_status, card.state, card.fair_price = None, None, None        # old catalog: nothing extra
    rows = dict(carDetails(card, rank=1)[3])
    assert rows["Title status"] == "Not listed" and "Warning" not in rows and "Usual price for this car" not in rows


def test_card_labels_carry_the_warnings():
    from tests.test_e03_results import _card, _setup, _result, VEHICLE

    card = _card(1, price=14_900)
    card.title_status, card.fair_price = "rebuilt", 30_000
    ui, controller, _, _ = _setup(_result(top_matches=[card]))
    controller.show(VEHICLE, _result(top_matches=[card]))
    assert ui.labelTopCar1Detail.content == "70,000 mi · Good · Rebuilt title"
    assert ui.labelTopCar1Match.content == "90% MATCH · LOW PRICE"


# --------------------------------------------------------------------- no welcome page
def test_app_opens_on_the_vehicle_form_with_two_steps(main_window):
    from desktop_app.controllers import PAGE_VEHICLE
    for name in ("pageWelcome", "lineEditFullName", "lineEditDisplayName", "pushButtonStart",
                 "pushButtonBackWelcome", "labelStep3"):
        assert not hasattr(main_window, name)
    pages = main_window.stackedWidgetMain
    assert pages.count() == 2 and pages.widget(PAGE_VEHICLE) is main_window.pageVehicle
    assert (main_window.labelStep1.text(), main_window.labelStep2.text()) == ("01  VEHICLE", "02  RESULTS")
    assert main_window.labelVehicleTitle.text() == "Which car do you have in mind?"      # no account in this test


def test_greeting_uses_the_name_of_the_account():
    pytest.importorskip("PyQt6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from desktop_app.UI.AutoWiseMainWindowEx import AutoWiseMainWindowEx
    from desktop_app.models.user import User

    app = QApplication.instance() or QApplication([])
    ui = AutoWiseMainWindowEx(User(full_name="Phuong Anh", username="phuonganh"), None)
    window = QMainWindow()
    ui.setupUi(window)
    assert ui.labelHeaderUser.text() == "Signed in as Phuong Anh"
    assert ui.labelVehicleTitle.text() == "Phuong Anh, which car do you have in mind?"
    assert ui.userName() == "Phuong Anh"
    assert ui.stackedWidgetMain.currentWidget() is ui.pageVehicle          # straight to the form after sign-in
    window.close()


def test_typing_part_of_a_model_fills_in_the_rest(main_window):
    make, model = main_window.comboBoxManufacturer, main_window.comboBoxModel
    make.setCurrentIndex(make.findData("toyota"))
    box = model.lineEdit()
    box.setProperty("typedLength", 0)
    box.setText("cam")
    main_window.completeTypedText(model, "cam")
    assert box.text() == "Camry" and box.selectedText() == "ry"          # "ry" is the grey suggestion
    assert model.currentData() == "camry"                                # chosen at once, summary follows
    assert "Camry" in main_window.labelSummaryTitle.text()
    box.setText("Cam")
    main_window.completeTypedText(model, "Cam")                          # Backspace: nothing filled in again
    assert box.text() == "Cam" and model.currentData() == "camry"
    main_window.matchTypedText(model)                                    # leaving the box shows the full name
    assert model.currentData() == "camry" and box.text() == "Camry"
    box.setText("Camzz")
    main_window.completeTypedText(model, "Camzz")                        # starts no name: nothing chosen
    assert model.currentData() is None and box.text() == "Camzz"


def test_hint_text_is_grey(main_window):
    from PyQt6.QtGui import QPalette
    from desktop_app.UI.AutoWiseMainWindowEx import HINT_COLOR
    for combo in (main_window.comboBoxManufacturer, main_window.comboBoxModel):
        color = combo.lineEdit().palette().color(QPalette.ColorRole.PlaceholderText)
        assert color.name() == HINT_COLOR.lower()


def test_wide_photo_does_not_make_its_card_wider(main_window, tmp_path):
    from PyQt6.QtGui import QColor, QImage
    from PyQt6.QtWidgets import QSizePolicy
    from desktop_app.widgets.vehicle_card import setCardImage
    from tests.test_e03_results import _card

    path = tmp_path / "wide.png"
    image = QImage(1200, 300, QImage.Format.Format_RGB32)
    image.fill(QColor("#335577"))
    image.save(str(path))
    card = _card(1)
    card.image_path = str(path)
    label = main_window.labelTopCar1Image
    setCardImage(label, card)
    assert label.pixmap().width() == label.width() and label.pixmap().height() == label.maximumHeight()
    for widget in main_window.resultsController.topCards:
        assert widget.labelImage.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
        assert main_window.horizontalLayoutTopMatches.stretch(
            main_window.horizontalLayoutTopMatches.indexOf(widget.frame)) == 1


def test_advanced_options_are_always_shown(main_window):
    assert not hasattr(main_window, "pushButtonToggleAdvanced")
    assert not main_window.widgetAdvancedFields.isHidden()
    assert main_window.labelAdvancedCardTitle.text() == "Advanced options (optional)"
    for combo in main_window.optionalCombos().values():
        assert combo.itemText(0) == "Not sure" and combo.itemData(0) is None
