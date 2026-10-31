
import sys
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

from PyQt6 import uic
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QComboBox
)

BASE = Path(__file__).resolve().parent
UI_FILE = BASE / "ui" / "autowise.ui"

# Có thể đặt CSV vào một trong hai đường dẫn.
CSV_CANDIDATES = [
    BASE.parent / "data" / "vehicles_with_images.csv",
    Path(r"D:\AutoWiseAI\data\vehicles_with_images.csv"),
]

STYLE = """
QMainWindow, QWidget {
    background-color: #F7F8FA;
    color: #111827;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QFrame#header {
    background-color: #111827;
}
QLabel#brand {
    background: transparent;
    color: white;
    font-size: 23px;
    font-weight: bold;
}
QLabel#stepLabel {
    background: transparent;
    color: #FCA5A5;
    font-weight: bold;
}
QLabel[role="title"] {
    font-size: 25px;
    font-weight: bold;
}
QLabel[role="section"] {
    font-size: 18px;
    font-weight: bold;
}
QLabel[role="muted"] {
    color: #6B7280;
}
QLabel#lblPredictedPrice {
    font-size: 25px;
    font-weight: bold;
    color: #C91E32;
}
QFrame[card="true"] {
    background-color: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: white;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px;
    min-height: 24px;
}
QPushButton {
    background-color: #C91E32;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: bold;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #A7192B;
}
QPushButton[secondary="true"] {
    background-color: #E5E7EB;
    color: #111827;
}
QScrollArea {
    border: none;
}
"""


# =====================================
# TẠO FILE .UI HỢP LỆ CHO QT DESIGNER
# =====================================

def prop(widget, name, value, kind="string"):
    p = ET.SubElement(widget, "property", name=name)
    ET.SubElement(p, kind).text = str(value)
    return p


def add_widget(parent_layout, widget_class, name,
               text=None, role=None, card=False):
    item = ET.SubElement(parent_layout, "item")
    widget = ET.SubElement(
        item, "widget",
        {"class": widget_class, "name": name}
    )

    if text is not None:
        prop(widget, "text", text)

    if role is not None:
        p = ET.SubElement(widget, "property", name="role")
        p.set("stdset", "0")
        ET.SubElement(p, "string").text = role

    if card:
        p = ET.SubElement(widget, "property", name="card")
        p.set("stdset", "0")
        ET.SubElement(p, "bool").text = "true"

    return widget


def add_layout(parent_widget, name, layout_class="QVBoxLayout"):
    return ET.SubElement(
        parent_widget, "layout",
        {"class": layout_class, "name": name}
    )


def nested_layout(parent, name, layout_class="QVBoxLayout"):
    item = ET.SubElement(parent, "item")
    return ET.SubElement(
        item, "layout",
        {"class": layout_class, "name": name}
    )


def add_field(form, row, label, widget_class, name):
    label_item = ET.SubElement(
        form, "item", row=str(row), column="0"
    )
    label_widget = ET.SubElement(
        label_item, "widget",
        {"class": "QLabel", "name": "label_" + name}
    )
    prop(label_widget, "text", label)

    input_item = ET.SubElement(
        form, "item", row=str(row), column="1"
    )
    input_widget = ET.SubElement(
        input_item, "widget",
        {"class": widget_class, "name": name}
    )

    return input_widget


def create_ui():
    UI_FILE.parent.mkdir(parents=True, exist_ok=True)

    ui = ET.Element("ui", version="4.0")
    ET.SubElement(ui, "class").text = "AutoWiseWindow"

    window = ET.SubElement(
        ui, "widget",
        {"class": "QMainWindow", "name": "AutoWiseWindow"}
    )

    geometry = ET.SubElement(
        window, "property", name="geometry"
    )
    rect = ET.SubElement(geometry, "rect")
    for tag, value in [
        ("x", 0), ("y", 0),
        ("width", 1100), ("height", 800)
    ]:
        ET.SubElement(rect, tag).text = str(value)

    prop(window, "windowTitle", "AutoWise AI")
    prop(window, "styleSheet", STYLE)

    central = ET.SubElement(
        window, "widget",
        {"class": "QWidget", "name": "centralwidget"}
    )

    root = add_layout(central, "mainLayout")

    # ========= HEADER =========

    header = add_widget(root, "QFrame", "header")
    header_layout = add_layout(
        header, "headerLayout", "QHBoxLayout"
    )

    brand = add_widget(
        header_layout, "QLabel", "brand",
        "AUTOWISE AI"
    )

    step = add_widget(
        header_layout, "QLabel", "stepLabel",
        "BƯỚC 1/3"
    )

    # ========= STACKED WIDGET =========

    item = ET.SubElement(root, "item")
    stack = ET.SubElement(
        item, "widget",
        {"class": "QStackedWidget", "name": "stackedWidget"}
    )
    prop(stack, "currentIndex", 0, "number")

    # ========= PAGE 1 =========

    page1 = ET.SubElement(
        stack, "widget",
        {"class": "QWidget", "name": "pageUser"}
    )
    layout1 = add_layout(page1, "userLayout")

    card1 = add_widget(
        layout1, "QFrame", "userCard", card=True
    )
    c1 = add_layout(card1, "userCardLayout")

    add_widget(
        c1, "QLabel", "userTitle",
        "Chào mừng đến với AutoWise AI",
        role="title"
    )

    add_widget(
        c1, "QLabel", "userDescription",
        "Hãy bắt đầu hành trình tìm chiếc xe phù hợp.",
        role="muted"
    )

    add_widget(c1, "QLabel", "lblName", "Họ và tên *")

    name_input = add_widget(
        c1, "QLineEdit", "txtFullName"
    )
    prop(
        name_input, "placeholderText",
        "Nhập họ và tên của bạn"
    )

    add_widget(
        c1, "QLabel", "lblDisplay",
        "Tên hiển thị"
    )

    display_input = add_widget(
        c1, "QLineEdit", "txtDisplayName"
    )
    prop(
        display_input, "placeholderText",
        "Tên muốn AutoWise dùng để xưng hô"
    )

    add_widget(
        c1, "QLabel", "userNote",
        "Thông tin này chỉ dùng để cá nhân hóa giao diện.",
        role="muted"
    )

    add_widget(
        c1, "QPushButton", "btnStart",
        "BẮT ĐẦU TƯ VẤN"
    )

    # ========= PAGE 2 =========

    page2 = ET.SubElement(
        stack, "widget",
        {"class": "QWidget", "name": "pageVehicle"}
    )

    page2_layout = add_layout(page2, "vehicleOuterLayout")

    scroll2 = add_widget(
        page2_layout, "QScrollArea", "vehicleScroll"
    )
    prop(scroll2, "widgetResizable", "true", "bool")

    scroll_content = ET.SubElement(
        scroll2, "widget",
        {"class": "QWidget", "name": "vehicleScrollContent"}
    )

    vc = add_layout(scroll_content, "vehicleContentLayout")

    add_widget(
        vc, "QLabel", "vehicleTitle",
        "Thông tin chiếc xe mong muốn",
        role="title"
    )

    add_widget(
        vc, "QLabel", "vehicleDescription",
        "Nhập thông số xe và ngân sách để AutoWise phân tích.",
        role="muted"
    )

    card2 = add_widget(
        vc, "QFrame", "vehicleCard", card=True
    )
    c2 = add_layout(card2, "vehicleCardLayout")

    add_widget(
        c2, "QLabel", "sectionVehicle",
        "1. Thông tin xe", role="section"
    )

    form1 = nested_layout(
        c2, "vehicleForm", "QFormLayout"
    )

    add_field(
        form1, 0, "Hãng xe",
        "QComboBox", "cboManufacturer"
    )
    add_field(
        form1, 1, "Dòng xe",
        "QComboBox", "cboModel"
    )

    year = add_field(
        form1, 2, "Năm sản xuất",
        "QSpinBox", "spinYear"
    )
    prop(year, "minimum", 1900, "number")
    prop(year, "maximum", 2030, "number")
    prop(year, "value", 2018, "number")

    add_field(
        form1, 3, "Kiểu dáng",
        "QComboBox", "cboType"
    )

    add_widget(
        c2, "QLabel", "sectionSpecs",
        "2. Thông số kỹ thuật", role="section"
    )

    form2 = nested_layout(
        c2, "specsForm", "QFormLayout"
    )

    odometer = add_field(
        form2, 0, "Số miles đã đi",
        "QSpinBox", "spinOdometer"
    )
    prop(odometer, "maximum", 1000000, "number")
    prop(odometer, "value", 60000, "number")
    prop(odometer, "suffix", " miles")

    add_field(
        form2, 1, "Tình trạng xe",
        "QComboBox", "cboCondition"
    )
    add_field(
        form2, 2, "Loại nhiên liệu",
        "QComboBox", "cboFuel"
    )
    add_field(
        form2, 3, "Hộp số",
        "QComboBox", "cboTransmission"
    )

    add_widget(
        c2, "QLabel", "sectionBudget",
        "3. Ngân sách", role="section"
    )

    form3 = nested_layout(
        c2, "budgetForm", "QFormLayout"
    )

    budget = add_field(
        form3, 0, "Ngân sách tối đa (USD)",
        "QSpinBox", "spinBudget"
    )
    prop(budget, "maximum", 1000000, "number")
    prop(budget, "value", 20000, "number")
    prop(budget, "prefix", "$ ")

    add_widget(
        c2, "QLabel", "advancedTitle",
        "4. Tùy chọn nâng cao", role="section"
    )

    advanced = nested_layout(
        c2, "advancedForm", "QFormLayout"
    )

    advanced_fields = [
        ("Hệ dẫn động", "cboDrive"),
        ("Số xi-lanh", "cboCylinders"),
        ("Màu xe", "cboPaintColor"),
        ("Giấy tờ xe", "cboTitleStatus"),
        ("Bang tại Mỹ", "cboState"),
    ]

    for idx, (label, name) in enumerate(advanced_fields):
        add_field(advanced, idx, label, "QComboBox", name)

    buttons2 = nested_layout(
        c2, "vehicleButtons", "QHBoxLayout"
    )

    back = add_widget(
        buttons2, "QPushButton",
        "btnBackUser", "QUAY LẠI"
    )

    p = ET.SubElement(back, "property", name="secondary")
    p.set("stdset", "0")
    ET.SubElement(p, "bool").text = "true"

    add_widget(
        buttons2, "QPushButton",
        "btnAnalyze", "PHÂN TÍCH VÀ TÌM XE"
    )

    # ========= PAGE 3 =========

    page3 = ET.SubElement(
        stack, "widget",
        {"class": "QWidget", "name": "pageResults"}
    )
    p3_layout = add_layout(page3, "resultsOuterLayout")

    scroll3 = add_widget(
        p3_layout, "QScrollArea", "resultsScroll"
    )
    prop(scroll3, "widgetResizable", "true", "bool")

    results_content = ET.SubElement(
        scroll3, "widget",
        {"class": "QWidget", "name": "resultsContent"}
    )

    results = add_layout(
        results_content, "resultsLayout"
    )

    add_widget(
        results, "QLabel", "lblResultsTitle",
        "Kết quả AutoWise AI",
        role="title"
    )

    result_sections = [
        (
            "predictionCard",
            "1. GIÁ XE AI DỰ ĐOÁN",
            "lblPredictedPrice",
            "Chưa kết nối mô hình ML"
        ),
        (
            "recommendationCard",
            "2. TOP 5 XE PHÙ HỢP",
            "lblRecommendations",
            "Chưa kết nối thuật toán Recommendation"
        ),
        (
            "alternativesCard",
            "3. NHỮNG XE KHÁC CÙNG MỨC GIÁ",
            "lblAlternatives",
            "Chưa có kết quả so sánh"
        ),
    ]

    for card_name, heading, label_name, placeholder in result_sections:
        card = add_widget(
            results, "QFrame", card_name, card=True
        )
        card_layout = add_layout(
            card, card_name + "Layout"
        )

        add_widget(
            card_layout, "QLabel",
            card_name + "Heading",
            heading,
            role="section"
        )

        result_label = add_widget(
            card_layout, "QLabel",
            label_name,
            placeholder
        )
        prop(result_label, "wordWrap", "true", "bool")

    add_widget(
        results, "QLabel", "lblDisclaimer",
        "Kết quả chỉ mang tính tham khảo, "
        "dựa trên dữ liệu tin đăng xe cũ lịch sử tại Mỹ.",
        role="muted"
    )

    add_widget(
        results, "QPushButton",
        "btnBackVehicle", "CHỈNH SỬA THÔNG TIN"
    )

    ET.SubElement(ui, "resources")
    ET.SubElement(ui, "connections")

    tree = ET.ElementTree(ui)

    # Python tạo XML declaration ở byte đầu tiên.
    # Tránh lỗi: XML declaration not at start.
    tree.write(
        UI_FILE,
        encoding="utf-8",
        xml_declaration=True
    )

    # Kiểm tra file XML vừa tạo.
    ET.parse(UI_FILE)

    print(f"Đã tạo giao diện: {UI_FILE}")


# =====================================
# CHẠY GIAO DIỆN
# =====================================

class AutoWiseApp(QMainWindow):
    def __init__(self):
        super().__init__()

        uic.loadUi(str(UI_FILE), self)

        self.vehicle_data = []
        self.models_by_make = {}

        self.load_vehicle_options()

        self.btnStart.clicked.connect(
            self.open_vehicle_page
        )
        self.btnBackUser.clicked.connect(
            self.open_user_page
        )
        self.btnAnalyze.clicked.connect(
            self.show_results
        )
        self.btnBackVehicle.clicked.connect(
            self.open_vehicle_page
        )

        self.cboManufacturer.currentTextChanged.connect(
            self.refresh_models
        )

        self.open_user_page()

    def load_vehicle_options(self):
        csv_path = next(
            (p for p in CSV_CANDIDATES if p.exists()),
            None
        )

        fields = {
            "manufacturer": "cboManufacturer",
            "type": "cboType",
            "condition": "cboCondition",
            "fuel": "cboFuel",
            "transmission": "cboTransmission",
            "drive": "cboDrive",
            "cylinders": "cboCylinders",
            "paint_color": "cboPaintColor",
            "title_status": "cboTitleStatus",
            "state": "cboState",
        }

        values = {col: set() for col in fields}

        if csv_path:
            with open(
                csv_path,
                encoding="utf-8-sig",
                newline=""
            ) as file:
                reader = csv.DictReader(file)

                for row in reader:
                    for col in fields:
                        value = (row.get(col) or "").strip()
                        if value:
                            values[col].add(value)

                    make = (
                        row.get("manufacturer") or ""
                    ).strip()
                    model = (
                        row.get("model") or ""
                    ).strip()

                    if make and model:
                        self.models_by_make.setdefault(
                            make, set()
                        ).add(model)

            print(f"Đã tải dữ liệu: {csv_path}")
        else:
            print(
                "Chưa tìm thấy CSV. "
                "Giao diện vẫn có thể mở trong Qt Designer."
            )

        for col, widget_name in fields.items():
            combo = getattr(self, widget_name)
            combo.clear()
            combo.addItem("Không yêu cầu")
            combo.addItems(sorted(values[col]))

        self.refresh_models()

    def refresh_models(self):
        make = self.cboManufacturer.currentText()

        self.cboModel.clear()
        self.cboModel.addItem("Không yêu cầu")

        models = sorted(
            self.models_by_make.get(make, [])
        )

        self.cboModel.addItems(models)

    def open_user_page(self):
        self.stackedWidget.setCurrentIndex(0)
        self.stepLabel.setText("BƯỚC 1/3")

    def open_vehicle_page(self):
        if not self.txtFullName.text().strip():
            QMessageBox.warning(
                self,
                "Thiếu thông tin",
                "Vui lòng nhập họ và tên."
            )
            return

        self.stackedWidget.setCurrentIndex(1)
        self.stepLabel.setText("BƯỚC 2/3")

    def show_results(self):
        if self.cboManufacturer.currentIndex() <= 0:
            QMessageBox.warning(
                self,
                "Thiếu thông tin",
                "Vui lòng chọn hãng xe từ dữ liệu CSV."
            )
            return

        if self.cboModel.currentIndex() <= 0:
            QMessageBox.warning(
                self,
                "Thiếu thông tin",
                "Vui lòng chọn dòng xe."
            )
            return

        if self.spinBudget.value() <= 0:
            QMessageBox.warning(
                self,
                "Ngân sách không hợp lệ",
                "Vui lòng nhập ngân sách lớn hơn 0."
            )
            return

        name = (
            self.txtDisplayName.text().strip()
            or self.txtFullName.text().strip()
        )

        make = self.cboManufacturer.currentText()
        model = self.cboModel.currentText()
        year = self.spinYear.value()
        mileage = self.spinOdometer.value()

        self.lblResultsTitle.setText(
            f"Kết quả dành cho {name}"
        )

        self.lblPredictedPrice.setText(
            f"Xe: {make} {model} ({year})\n"
            f"Đã đi: {mileage:,} miles\n\n"
            "Giá dự đoán: Chưa kết nối model Regression"
        )

        self.lblRecommendations.setText(
            "Chưa kết nối mô hình gợi ý KNN/Cosine.\n"
            "Kết quả Top 5 sẽ xuất hiện tại đây."
        )

        self.lblAlternatives.setText(
            "Chưa chạy bộ lọc xe cùng mức giá.\n"
            "Các mẫu xe thay thế sẽ xuất hiện tại đây."
        )

        self.stackedWidget.setCurrentIndex(2)
        self.stepLabel.setText("BƯỚC 3/3")


if __name__ == "__main__":
    # Nếu file UI đang lỗi XML, tạo lại.
    # Muốn tạo lại thủ công: python main.py --rebuild-ui
    rebuild = "--rebuild-ui" in sys.argv

    if UI_FILE.exists() and not rebuild:
        try:
            ET.parse(UI_FILE)
        except ET.ParseError:
            rebuild = True

    if not UI_FILE.exists() or rebuild:
        create_ui()

    app = QApplication(sys.argv[:1])

    window = AutoWiseApp()
    window.resize(1100, 800)
    window.show()

    sys.exit(app.exec())
