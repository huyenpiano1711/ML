"""Input rules added after the test sheet: account, names, mileage, card details, environment at start-up."""
from __future__ import annotations

import pytest

from desktop_app.connectors.connector import Connector
from desktop_app.controllers import PAGE_VEHICLE
from desktop_app.controllers.results_controller import FIX_ENVIRONMENT, STARTUP_TITLE, ResultsController, environmentProblems
from desktop_app.controllers.user_controller import UserController
from desktop_app.controllers.vehicle_controller import MAX_MILES_NEW, MAX_MILES_PER_YEAR, VehicleController, mileageMessages
from desktop_app.dal.user_dao import MAX_NAME_LENGTH, UserDao, nameError, passwordError
from desktop_app.widgets.vehicle_card import known, labelOf
from tests.test_e02_controllers import FakeUi as FormUi, _filled_ui, _shown_errors
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


@pytest.mark.parametrize("full_name, display_name", [("12345", ""), ("!!!", ""), ("Duy Le", "@@@")])
def test_start_rejects_names_that_are_not_names(full_name, display_name):
    ui = FormUi(full_name=full_name, display_name=display_name)
    UserController(ui).start()
    assert ui.pages == [] and ui.warnings and ui.warnings[0][0] == "Please check your name"


def test_start_accepts_vietnamese_name():
    ui = FormUi(full_name="Nguyễn Thị Như Huyền")
    UserController(ui).start()
    assert ui.pages == [PAGE_VEHICLE] and ui.warnings == []


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
