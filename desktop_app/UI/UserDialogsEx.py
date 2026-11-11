"""
UserDialogsEx.py - Windows a signed-in user opens from the header of the car advisor:
    AccountDialogEx    profile (name, email) and password            AccountDialog.ui
    HistoryDialogEx    past analyses: open again, export PDF, delete HistoryDialog.ui
    FavoritesDialogEx  saved cars: details, remove, compare 2-3 cars  FavoritesDialog.ui
    CompareDialogEx    the cars side by side                          CompareDialog.ui
Each .ui was made with desktop_app/UI/design/make_ui.py and converted with pyuic6 (do NOT edit the *.py by hand).
"""
import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QDialog, QFileDialog, QLineEdit, QMessageBox, QTableWidgetItem, QWidget, QHBoxLayout

from desktop_app.UI.AccountDialog import Ui_AccountDialog
from desktop_app.UI.CompareDialog import Ui_CompareDialog
from desktop_app.UI.FavoritesDialog import Ui_FavoritesDialog
from desktop_app.UI.HistoryDialog import Ui_HistoryDialog
from desktop_app.dal.history_dao import FavoriteDao, SearchDao
from desktop_app.dal.user_dao import MAX_EMAIL_LENGTH, MAX_NAME_LENGTH, MAX_PASSWORD_LENGTH, UserDao
from desktop_app.utils.PdfUtil import analysisHtml, saveHtmlAsPdf
from desktop_app.utils.TableUtil import TableUtil
from desktop_app.utils.UIUtil import UIUtil
from desktop_app.widgets.vehicle_card import labelOf, makeLabel, modelLabel, money


def carName(manufacturer, model, year=""):
    return f"{makeLabel(manufacturer)} {modelLabel(model)} {year}".strip()


def showMessage(label, text, success=False):
    label.setProperty("role", "success" if success else "error")
    UIUtil.repolish(label)
    label.setText(text)
    label.setVisible(bool(text))


def exportSearchPdf(parent, user, record):
    """Ask where to save, then write the PDF of one saved analysis (a row of the searches table)."""
    vehicle = json.loads(record["input_json"])
    payload = json.loads(record["result_json"] or "{}")
    default = Path.home() / f"AutoWise_{vehicle['manufacturer']}_{vehicle['model_base']}_{record['id']}.pdf".replace(" ", "_")
    path, _ = QFileDialog.getSaveFileName(parent, "Export analysis as PDF", str(default), "PDF files (*.pdf)")
    if not path:
        return None
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    saveHtmlAsPdf(analysisHtml(user.full_name or user.username, vehicle, payload, record.get("created_at")), path)
    QMessageBox.information(parent, "PDF saved", f"The analysis was saved to:\n{path}")
    return path


# ------------------------------------------------------------------------------------------- account
class AccountDialogEx(Ui_AccountDialog):
    def __init__(self, user, onChanged=None):
        self.user = user
        self.onChanged = onChanged            # called with the updated User after the profile is saved

    def setupUi(self, Dialog):
        super().setupUi(Dialog)
        self.Dialog = Dialog
        UIUtil.setupWindow(Dialog)
        for box, limit in ((self.lineEditFullName, MAX_NAME_LENGTH), (self.lineEditEmail, MAX_EMAIL_LENGTH),
                           (self.lineEditOldPassword, MAX_PASSWORD_LENGTH), (self.lineEditNewPassword, MAX_PASSWORD_LENGTH),
                           (self.lineEditConfirmPassword, MAX_PASSWORD_LENGTH)):
            box.setMaxLength(limit)
        for label in (self.labelProfileMessage, self.labelPasswordMessage):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.hide()
        self.pushButtonSaveProfile.clicked.connect(self.saveProfile)
        self.pushButtonChangePassword.clicked.connect(self.changePassword)
        self.checkBoxShowPasswords.toggled.connect(self.togglePasswords)
        self.lineEditConfirmPassword.returnPressed.connect(self.changePassword)
        self.pushButtonAccountClose.clicked.connect(Dialog.accept)
        self.loadUser()

    def loadUser(self):
        self.user = UserDao.getUserById(self.user.id) or self.user
        self.labelUsernameValue.setText(self.user.username)
        self.labelRoleValue.setText("Administrator" if self.user.is_admin else "User")
        self.labelCreatedValue.setText(self.user.created_at or "")
        self.labelLastLoginValue.setText(self.user.last_login_at or "")
        self.lineEditFullName.setText(self.user.full_name or "")
        self.lineEditEmail.setText(self.user.email or "")

    def saveProfile(self):
        errors = UserDao.updateProfile(self.user.id, self.lineEditFullName.text(), self.lineEditEmail.text())
        if errors:
            showMessage(self.labelProfileMessage, "\n".join(errors))
            return
        self.loadUser()
        showMessage(self.labelProfileMessage, "Your profile was saved.", success=True)
        if self.onChanged:
            self.onChanged(self.user)

    def togglePasswords(self, show):
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        for box in (self.lineEditOldPassword, self.lineEditNewPassword, self.lineEditConfirmPassword):
            box.setEchoMode(mode)

    def changePassword(self):
        errors = UserDao.changePassword(self.user.id, self.lineEditOldPassword.text(), self.lineEditNewPassword.text(),
                                        self.lineEditConfirmPassword.text())
        if errors:
            showMessage(self.labelPasswordMessage, "\n".join(errors))
            return
        for box in (self.lineEditOldPassword, self.lineEditNewPassword, self.lineEditConfirmPassword):
            box.clear()
        showMessage(self.labelPasswordMessage, "Your password was changed. Use it next time you sign in.", success=True)


# ------------------------------------------------------------------------------------------- history
class HistoryDialogEx(Ui_HistoryDialog):
    def __init__(self, user, onOpen=None):
        self.user = user
        self.onOpen = onOpen                  # called with the search record to show it on the results page

    def setupUi(self, Dialog):
        super().setupUi(Dialog)
        self.Dialog = Dialog
        UIUtil.setupWindow(Dialog)
        self.lineEditHistorySearch.textChanged.connect(self.loadHistory)
        self.pushButtonHistoryOpen.clicked.connect(self.openSelected)
        self.tableWidgetHistory.doubleClicked.connect(self.openSelected)
        self.pushButtonHistoryPdf.clicked.connect(self.exportSelected)
        self.pushButtonHistoryDelete.clicked.connect(self.deleteSelected)
        self.pushButtonHistoryClear.clicked.connect(self.clearAll)
        self.pushButtonHistoryClose.clicked.connect(Dialog.accept)
        self.loadHistory()

    def loadHistory(self):
        df = SearchDao.listForUser(self.user.id, self.lineEditHistorySearch.text())
        rows = []
        for r in (df.itertuples() if df is not None else []):
            price = money(r.predicted_price) if r.predicted_price == r.predicted_price and r.predicted_price else "N/A"
            rng = (f"{money(r.price_low)} – {money(r.price_high)}" if r.price_low == r.price_low and r.price_low else "")
            rows.append([r.id, r.created_at, carName(r.manufacturer, r.model_base, r.year), f"{r.odometer:,.0f} mi",
                         money(r.budget_max_usd), price, rng, r.n_matches])
        TableUtil.fill(self.tableWidgetHistory, rows, align_right=(3, 4, 5, 7), stretch_col=2)
        empty = len(rows) == 0
        self.labelHistoryEmpty.setVisible(empty)
        self.labelHistoryCount.setText(f"{len(rows)} analys{'is' if len(rows) == 1 else 'es'}")
        for button in (self.pushButtonHistoryOpen, self.pushButtonHistoryPdf, self.pushButtonHistoryDelete,
                       self.pushButtonHistoryClear):
            button.setEnabled(not empty)

    def selectedRecord(self):
        key = TableUtil.selectedKey(self.tableWidgetHistory)
        if key is None:
            QMessageBox.information(self.Dialog, "History", "Please select an analysis first.")
            return None
        return SearchDao.get(int(key), self.user.id)

    def openSelected(self):
        record = self.selectedRecord()
        if record is not None and self.onOpen is not None:
            self.Dialog.accept()
            self.onOpen(record)

    def exportSelected(self):
        record = self.selectedRecord()
        if record is not None:
            exportSearchPdf(self.Dialog, self.user, record)

    def deleteSelected(self):
        record = self.selectedRecord()
        if record is None:
            return
        if QMessageBox.question(self.Dialog, "Delete analysis", "Delete this analysis from your history?") \
                == QMessageBox.StandardButton.Yes:
            SearchDao.delete(record["id"], self.user.id)
            self.loadHistory()

    def clearAll(self):
        if QMessageBox.question(self.Dialog, "Clear history", "Delete ALL your analyses? This cannot be undone.") \
                == QMessageBox.StandardButton.Yes:
            SearchDao.clear(self.user.id)
            self.loadHistory()


# ------------------------------------------------------------------------------------------- saved cars
class FavoritesDialogEx(Ui_FavoritesDialog):
    MAX_COMPARE = 3

    def __init__(self, user, openDetails=None):
        self.user = user
        self.openDetails = openDetails        # callable(parent, card_dict) -> shows the car details window
        self.cars = []

    def setupUi(self, Dialog):
        super().setupUi(Dialog)
        self.Dialog = Dialog
        UIUtil.setupWindow(Dialog)
        self.pushButtonFavoritesCompare.clicked.connect(self.compare)
        self.pushButtonFavoritesRemove.clicked.connect(self.removeSelected)
        self.pushButtonFavoritesDetails.clicked.connect(self.showDetails)
        self.tableWidgetFavorites.doubleClicked.connect(self.showDetails)
        self.pushButtonFavoritesClose.clicked.connect(Dialog.accept)
        self.pushButtonFavoritesDetails.setVisible(self.openDetails is not None)
        self.loadCars()

    def loadCars(self):
        df = FavoriteDao.listForUser(self.user.id)
        self.cars = [] if df.empty else df.to_dict("records")
        rows = [[c["id"], carName(c["manufacturer"], c["model_base"], c["year"]), money(c["price"]), f"{c['odometer']:,.0f} mi",
                 labelOf("condition", c.get("condition")),
                 f"{labelOf('fuel', c.get('fuel'))} · {labelOf('transmission', c.get('transmission'))}",
                 labelOf("title_status", c.get("title_status") or "unknown"), (c.get("state") or "").upper(), c["saved_at"]]
                for c in self.cars]
        TableUtil.fill(self.tableWidgetFavorites, rows, align_right=(2, 3), stretch_col=1)
        self.tableWidgetFavorites.setSortingEnabled(False)            # the check boxes follow the row order
        for r in range(len(rows)):
            self.tableWidgetFavorites.item(r, 0).setText("")
            box = QCheckBox()
            holder = QWidget()
            lay = QHBoxLayout(holder)
            lay.setContentsMargins(14, 0, 0, 0)
            lay.addWidget(box)
            self.tableWidgetFavorites.setCellWidget(r, 0, holder)
        empty = not rows
        self.labelFavoritesEmpty.setVisible(empty)
        self.labelFavoritesCount.setText(f"{len(rows)} saved car{'s' if len(rows) != 1 else ''}")
        for button in (self.pushButtonFavoritesCompare, self.pushButtonFavoritesRemove, self.pushButtonFavoritesDetails):
            button.setEnabled(not empty)

    def ticked(self):
        out = []
        for r in range(self.tableWidgetFavorites.rowCount()):
            holder = self.tableWidgetFavorites.cellWidget(r, 0)
            box = holder.findChild(QCheckBox) if holder else None
            if box is not None and box.isChecked():
                key = self.tableWidgetFavorites.item(r, 0).data(Qt.ItemDataRole.UserRole)
                out.append(next(c for c in self.cars if c["id"] == key))
        return out

    def selectedCar(self):
        key = TableUtil.selectedKey(self.tableWidgetFavorites)
        if key is None:
            QMessageBox.information(self.Dialog, "Saved cars", "Please select a car first.")
            return None
        return next((c for c in self.cars if c["id"] == key), None)

    def compare(self):
        cars = self.ticked()
        if not 2 <= len(cars) <= self.MAX_COMPARE:
            QMessageBox.information(self.Dialog, "Compare cars", f"Please tick 2 or {self.MAX_COMPARE} cars to compare.")
            return
        openCompare(self.Dialog, cars)

    def removeSelected(self):
        cars = self.ticked() or ([c] if (c := self.selectedCar()) else [])
        if not cars:
            return
        if QMessageBox.question(self.Dialog, "Remove", f"Remove {len(cars)} car(s) from your saved cars?") \
                == QMessageBox.StandardButton.Yes:
            for car in cars:
                FavoriteDao.remove(self.user.id, car["id"])
            self.loadCars()

    def showDetails(self):
        car = self.selectedCar()
        if car is not None and self.openDetails is not None:
            self.openDetails(self.Dialog, car)


# ------------------------------------------------------------------------------------------- compare
COMPARE_ROWS = [  # (label, function(car) -> text, sort value or None, smaller is better?)
    ("Price", lambda c: money(c["price"]), lambda c: c["price"], True),
    ("Year", lambda c: str(c["year"]), lambda c: c["year"], False),
    ("Mileage", lambda c: f"{c['odometer']:,.0f} mi", lambda c: c["odometer"], True),
    ("Miles per year", lambda c: f"{c['odometer'] / max(2021 - c['year'], 1):,.0f}", lambda c: c["odometer"] / max(2021 - c["year"], 1), True),
    ("Condition", lambda c: labelOf("condition", c.get("condition")), None, None),
    ("Body type", lambda c: labelOf("type", c.get("type")), None, None),
    ("Fuel", lambda c: labelOf("fuel", c.get("fuel")), None, None),
    ("Gearbox", lambda c: labelOf("transmission", c.get("transmission")), None, None),
    ("Title status", lambda c: labelOf("title_status", c.get("title_status") or "unknown"), None, None),
    ("State", lambda c: (c.get("state") or "").upper(), None, None),
    ("Model estimate", lambda c: money(c["fair_price"]) if c.get("fair_price") else "-", None, None),
    ("Price vs. estimate", lambda c: f"{(c['price'] / c['fair_price'] - 1) * 100:+.0f}%" if c.get("fair_price") else "-",
     lambda c: c["price"] / c["fair_price"] if c.get("fair_price") else None, True),
    ("Listing ID", lambda c: str(c["id"]), None, None),
]


class CompareDialogEx(Ui_CompareDialog):
    def __init__(self, cars):
        self.cars = cars

    def setupUi(self, Dialog):
        super().setupUi(Dialog)
        self.Dialog = Dialog
        UIUtil.setupWindow(Dialog)
        self.pushButtonCompareClose.clicked.connect(Dialog.accept)
        self.showCars()

    def showCars(self):
        table = self.tableWidgetCompare
        table.setColumnCount(len(self.cars))
        table.setRowCount(len(COMPARE_ROWS))
        table.setHorizontalHeaderLabels([carName(c["manufacturer"], c["model_base"], c["year"]) for c in self.cars])
        table.setVerticalHeaderLabels([row[0] for row in COMPARE_ROWS])
        wins = {i: 0 for i in range(len(self.cars))}
        for r, (_, text, key, smaller) in enumerate(COMPARE_ROWS):
            for c, car in enumerate(self.cars):
                table.setItem(r, c, QTableWidgetItem(text(car)))
            if key is not None:
                values = [key(car) for car in self.cars]
                valid = [v for v in values if v is not None]
                if len(valid) >= 2 and len(set(valid)) > 1:
                    best = min(valid) if smaller else max(valid)
                    for c, v in enumerate(values):
                        if v == best:
                            TableUtil.colorCell(table, r, c, fg="#15803D", bg="#F0FDF4", bold=True)
                            wins[c] += 1
        table.verticalHeader().setVisible(True)
        table.horizontalHeader().setStretchLastSection(False)
        from PyQt6.QtWidgets import QHeaderView
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        leader = max(wins, key=wins.get)
        self.labelCompareSummary.setText(
            f"{carName(self.cars[leader]['manufacturer'], self.cars[leader]['model_base'], self.cars[leader]['year'])} "
            f"has the best value on {wins[leader]} of the measurable rows (price, year, mileage, miles per year, price vs. "
            "estimate). Check the condition and title status before deciding.")


def openCompare(parent, cars):
    dialog = QDialog(parent)
    ui = CompareDialogEx(cars)
    ui.setupUi(dialog)
    dialog.exec()


def openDialog(parent, ui_class, *args):
    dialog = QDialog(parent)
    ui = ui_class(*args)
    ui.setupUi(dialog)
    dialog.exec()
    return ui
