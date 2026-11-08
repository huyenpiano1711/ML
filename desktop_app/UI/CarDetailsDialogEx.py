"""
CarDetailsDialogEx.py - Window opened by a click on a car card of Screen 3 (Top 5 or same price range).
It shows everything AutoWise knows about that car: photo, price and every field of the listing.
The rows come from vehicle_card.carDetails() (through ResultsController.detailsOf).
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel

from desktop_app.UI.CarDetailsDialog import Ui_CarDetailsDialog
from desktop_app.utils.UIUtil import UIUtil
from desktop_app.widgets.vehicle_card import WARNING, setCardImage


class CarDetailsDialogEx(Ui_CarDetailsDialog):
    def setupUi(self, Dialog):
        super().setupUi(Dialog)
        self.Dialog = Dialog
        UIUtil.loadFonts()
        self.pushButtonClose.clicked.connect(Dialog.accept)

    def showCar(self, card, details):
        """card: the CarCard (for the photo); details: (badge, title, price, rows) of carDetails()."""
        badge, title, price, rows = details
        self.Dialog.setWindowTitle(f"Car details - {title}")
        self.labelBadge.setText(badge)
        self.labelTitle.setText(title)
        self.labelPrice.setText(price)
        warnings = [value for field, value in rows if field == WARNING]
        self.labelWarning.setText(" ".join(warnings))
        self.labelWarning.setVisible(bool(warnings))
        for row, (field, value) in enumerate(item for item in rows if item[0] != WARNING):
            name = QLabel(field.upper())
            name.setProperty("role", "field")
            text = QLabel(value)
            text.setProperty("role", "value")
            text.setTextFormat(Qt.TextFormat.PlainText)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)   # listing ID can be copied
            self.gridLayoutDetails.addWidget(name, row, 0)
            self.gridLayoutDetails.addWidget(text, row, 1)
        self.gridLayoutDetails.setColumnStretch(1, 1)
        self.Dialog.adjustSize()
        setCardImage(self.labelImage, card)


def openCarDetails(parent, card, details):
    dialog = QDialog(parent)
    ui = CarDetailsDialogEx()
    ui.setupUi(dialog)
    ui.showCar(card, details)
    dialog.exec()
