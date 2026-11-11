"""Tài khoản, phân quyền, lịch sử, xe yêu thích và huấn luyện mô hình từ màn hình Admin (GĐ2-GĐ4)."""
from datetime import datetime, timedelta

import pytest

from desktop_app.connectors.connector import Connector
from desktop_app.dal.user_dao import (AUTH_BANNED, AUTH_LOCKED, AUTH_OK, AUTH_WRONG, DEFAULT_ADMIN, TIME_FORMAT, UserDao,
                                      passwordError)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(Connector.__init__, "__defaults__", (tmp_path / "test.sqlite",))
    UserDao.ensureDefaultAdmin()
    return tmp_path


def test_default_admin_is_created_once(db):
    admin = UserDao.getUser(DEFAULT_ADMIN[0])
    assert admin is not None and admin.is_admin
    assert UserDao.ensureDefaultAdmin() is None            # đã có admin -> không tạo thêm
    assert UserDao.authenticate(DEFAULT_ADMIN[0], DEFAULT_ADMIN[1]).ok


def test_password_never_stored_in_plain_text(db):
    us = UserDao.register("Kha Do", "khado", "kha@uel.edu.vn", "autowise2026")
    assert "autowise2026" not in us.password and "$" in us.password


def test_password_rules():
    assert passwordError("short1") is not None
    assert passwordError("onlyletters") is not None
    assert passwordError("has space 1") is not None
    assert passwordError("khado2026x", "khado") == "Password must not contain your username."
    assert passwordError("autowise2026") is None


def test_three_wrong_passwords_lock_the_account(db):
    UserDao.register("Kha Do", "khado", "", "autowise2026")
    first = UserDao.authenticate("khado", "wrong0001")
    assert first.status == AUTH_WRONG and "2 attempts left" in first.message
    UserDao.authenticate("khado", "wrong0002")
    third = UserDao.authenticate("khado", "wrong0003")
    assert third.status == AUTH_LOCKED
    # khóa lưu trong CSDL: mật khẩu đúng vẫn bị chặn đến khi hết 5 phút
    assert UserDao.authenticate("khado", "autowise2026").status == AUTH_LOCKED
    past = (datetime.now() - timedelta(minutes=1)).strftime(TIME_FORMAT)
    UserDao.execute("update users set locked_until=? where username='khado'", (past,))
    assert UserDao.authenticate("khado", "autowise2026").status == AUTH_OK


def test_success_resets_the_counter(db):
    UserDao.register("Kha Do", "khado", "", "autowise2026")
    UserDao.authenticate("khado", "wrong0001")
    UserDao.authenticate("khado", "wrong0002")
    assert UserDao.authenticate("khado", "autowise2026").ok
    assert UserDao.authenticate("khado", "wrong0003").status == AUTH_WRONG       # đếm lại từ đầu


def test_banned_account_cannot_sign_in_and_attempts_are_logged(db):
    admin = UserDao.getUser("admin")
    us = UserDao.register("Kha Do", "khado", "", "autowise2026")
    assert UserDao.setBanned(admin, us.id, True) is None
    assert UserDao.authenticate("khado", "autowise2026").status == AUTH_BANNED
    history = UserDao.query("select * from login_history where username='khado'")
    assert list(history["reason"]) == ["banned"]


def test_admin_guards(db):
    admin = UserDao.getUser("admin")
    assert UserDao.setBanned(admin, admin.id, True) == "You cannot do this to your own account."
    assert UserDao.deleteUser(admin, admin.id) is not None
    us = UserDao.register("Kha Do", "khado", "", "autowise2026")
    assert UserDao.setRole(admin, us.id, "admin") is None and UserDao.getUserById(us.id).is_admin
    pwd, error = UserDao.resetPassword(admin, us.id)
    assert error is None and UserDao.authenticate("khado", pwd).ok
    actions = UserDao.query("select action from audit_log")["action"].tolist()
    assert "set_role:admin" in actions and "reset_password" in actions


def test_profile_and_password_change(db):
    us = UserDao.register("Kha Do", "khado", "kha@uel.edu.vn", "autowise2026")
    other = UserDao.register("Duy Le", "duyle", "duy@uel.edu.vn", "autowise2026")
    assert UserDao.updateProfile(us.id, "Kha Do Le", "duy@uel.edu.vn") == ["This email is already used by another account."]
    assert UserDao.updateProfile(us.id, "Kha Do Le", "kha2@uel.edu.vn") == []
    assert UserDao.changePassword(us.id, "wrong", "newpass2026", "newpass2026") == ["Your current password is not correct."]
    assert UserDao.changePassword(us.id, "autowise2026", "newpass2026", "newpass2026") == []
    assert UserDao.authenticate("khado", "newpass2026").ok and other is not None


def test_history_favorites_and_stats(db):
    from backend.schemas.result_schema import AnalysisResult, CarCard, PriceResult
    from backend.schemas.vehicle_input import VehicleInput
    from desktop_app.dal.history_dao import FavoriteDao, SearchDao, StatsDao
    us = UserDao.register("Kha Do", "khado", "", "autowise2026")
    vehicle = VehicleInput.from_dict({"manufacturer": "toyota", "model_base": "camry", "year": 2016, "odometer": 60000,
                                      "budget_max_usd": 15000})
    card = CarCard(id=1, manufacturer="toyota", model_base="camry", year=2015, price=13000, odometer=70000, type="sedan",
                   condition="good", fuel="gas", transmission="automatic")
    result = AnalysisResult(success=True, price=PriceResult(16500, 14000, 19000), top_matches=[card])
    sid = SearchDao.save(us.id, vehicle, result)
    assert SearchDao.get(sid, us.id)["n_matches"] == 1
    assert SearchDao.get(sid, us.id + 999) is None                 # không xem được lịch sử của người khác
    assert FavoriteDao.add(us.id, card) and not FavoriteDao.add(us.id, card)
    assert len(FavoriteDao.listForUser(us.id)) == 1
    k = StatsDao.kpis()
    assert k["searches"] == 1 and k["favorites"] == 1 and StatsDao.overBudgetShare() == 1.0


def test_model_trainer_interval_and_params():
    import numpy as np
    from src.prediction import model_trainer as mt
    with pytest.raises(ValueError):
        mt.clean_params("hgb", {"learning_rate": 5})
    rng = np.random.default_rng(0)
    pred = np.exp(rng.uniform(np.log(2000), np.log(80000), 3000))
    y = pred * np.exp(rng.normal(0, 0.2, 3000))
    table = mt.fit_interval(y, pred)
    low, high = mt.apply_interval(10000, table)
    assert low < 10000 < high
    cover, _ = mt.interval_coverage(y, pred, table)
    assert 75 <= cover <= 85
