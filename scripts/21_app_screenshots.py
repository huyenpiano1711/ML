"""
21_app_screenshots.py - Chạy thử toàn bộ ứng dụng không cần màn hình (offscreen) và chụp ảnh từng màn hình cho báo cáo.
Dùng CSDL tạm (không đụng tài khoản thật), không lưu phiên bản mô hình. Ảnh lưu vào docs/screenshots/.
Chạy:  python scripts/21_app_screenshots.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

from desktop_app.connectors.connector import Connector  # noqa: E402
DB = Path(tempfile.gettempdir()) / "autowise_screenshots.sqlite"
DB.unlink(missing_ok=True)
Connector.__init__.__defaults__ = (DB,)

from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox  # noqa: E402

app = QApplication(sys.argv)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: print("INFO:", a[1:3]))
QMessageBox.warning = staticmethod(lambda *a, **k: print("WARN:", a[1:3]))
QMessageBox.critical = staticmethod(lambda *a, **k: print("CRIT:", a[1:3]))


def shot(widget, name):
    for _ in range(3):
        app.processEvents()
    widget.grab().save(str(OUT / f"{name}.png"))
    print("shot", name)


from desktop_app.UI.LoginMainWindowEx import LoginMainWindowEx  # noqa: E402
from desktop_app.dal.user_dao import UserDao  # noqa: E402

login = LoginMainWindowEx()
lw = QMainWindow()
login.setupUi(lw)
lw.resize(1240, 830)
lw.show()
shot(lw, "01_dang_nhap")
login.showPage(1)
login.lineEditFullName.setText("Do Le Quynh Kha")
login.lineEditRegisterUserName.setText("khado")
login.lineEditEmail.setText("kha@")
login.lineEditRegisterPassword.setText("abc")
login.lineEditConfirmPassword.setText("abd")
login.processRegister()
shot(lw, "02_dang_ky_loi")
login.lineEditEmail.setText("kha@uel.edu.vn")
login.lineEditRegisterPassword.setText("autowise2026")
login.lineEditConfirmPassword.setText("autowise2026")
login.checkBoxAgree.setChecked(True)
login.processRegister()
for pwd in ("wrongpass1", "wrongpass2"):
    login.lineEditUserName.setText("khado")
    login.lineEditPassword.setText(pwd)
    login.processLogin()
shot(lw, "03_dang_nhap_sai")
login.lineEditPassword.setText("autowise2026")
login.processLogin()
ui = login.mainUi
mw = ui.MainWindow
mw.resize(1366, 900)
# fill the vehicle form like a user
make = ui.comboBoxManufacturer
make.setCurrentIndex(make.findData("toyota"))
app.processEvents()
ui.comboBoxModel.setCurrentIndex(ui.comboBoxModel.findData("camry"))
ui.spinBoxYear.setValue(2016)
ui.spinBoxOdometer.setValue(60000)
ui.spinBoxBudget.setValue(15000)
shot(mw, "04_nhap_thong_so")
vehicle = ui.vehicleController.validatedInput()
result = ui.resultsController.analyze(vehicle)
ui.saveSearch(vehicle, result)
ui.resultsController.show(vehicle, result)
for widgets, cards in ((ui.resultsController.topCards, result.top_matches), (ui.resultsController.similarCards, result.similar_price)):
    for widget, card in zip(widgets, cards):
        widget.showImage(card)
shot(mw, "05_ket_qua")
print("price", result.price, [c.price for c in result.top_matches])

from desktop_app.UI.CarDetailsDialogEx import CarDetailsDialogEx  # noqa: E402
from desktop_app.widgets.vehicle_card import carDetails  # noqa: E402
d = QDialog(mw)
x = CarDetailsDialogEx(ui.user)
x.setupUi(d)
x.showCar(result.top_matches[0], ui.resultsController.detailsOf(ui.resultsController.topCards[0]))
x.toggleSaved()
d.show()
shot(d, "06_chi_tiet_xe")
from desktop_app.dal.history_dao import FavoriteDao, SearchDao  # noqa: E402
for c in result.top_matches[1:3]:
    FavoriteDao.add(ui.user.id, c)
from desktop_app.UI import UserDialogsEx as U  # noqa: E402
for cls, args, name, size in [(U.FavoritesDialogEx, (ui.user, ui.showSavedCar), "07_xe_da_luu", (1080, 640)),
                              (U.HistoryDialogEx, (ui.user, None), "09_lich_su", (1040, 640)),
                              (U.AccountDialogEx, (ui.user, None), "10_tai_khoan", (560, 640))]:
    d = QDialog(mw)
    x = cls(*args)
    x.setupUi(d)
    d.resize(*size)
    d.show()
    shot(d, name)
    d.close()
favs = FavoriteDao.listForUser(ui.user.id).to_dict("records")
d = QDialog(mw)
x = U.CompareDialogEx(favs[:3])
x.setupUi(d)
d.resize(900, 620)
d.show()
shot(d, "08_so_sanh")
d.close()
from desktop_app.utils.PdfUtil import analysisHtml, saveHtmlAsPdf  # noqa: E402
rec = SearchDao.get(ui.lastSearchId, ui.user.id)
saveHtmlAsPdf(analysisHtml(ui.user.full_name, json.loads(rec["input_json"]), json.loads(rec["result_json"]), rec["created_at"]),
              OUT / "11_ket_qua_mau.pdf")
ui.processLogout()

login.lineEditUserName.setText("admin")
login.lineEditPassword.setText("Admin@2026")
login.processLogin()
adm = login.mainUi
aw = adm.MainWindow
aw.showNormal()
aw.resize(1440, 900)
shot(aw, "12_admin_dashboard")
adm.goToPage(1)
shot(aw, "13_admin_nguoi_dung")
adm.goToPage(2)
from desktop_app.UI.AdminMainWindowEx import TrainWorker  # noqa: E402
params = {b.property("param"): b.value() for _, b in adm.paramWidgets if b.isVisible()}
results = []
worker = TrainWorker("hgb", params, True, 0.5)
worker.finished.connect(results.append)
worker.failed.connect(print)
worker.run()
adm.trainFinished(results[0])
shot(aw, "14_admin_mo_hinh")
adm.goToPage(3)
shot(aw, "15_admin_du_lieu")
adm.tabWidgetData.setCurrentIndex(1)
adm._runElbow()
adm._runKMeans()
shot(aw, "16_admin_phan_khuc")
adm.goToPage(4)
shot(aw, "17_admin_nhat_ky")
print("done")
