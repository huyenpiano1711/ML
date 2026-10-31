
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "ui" / "autowise.ui"

NAVY = "#111827"
RED = "#C91E32"

STYLE = """
QMainWindow, QWidget {
    background: #F7F8FA;
    color: #111827;
    font-family: "Segoe UI";
    font-size: 13px;
}
QFrame#header {
    background: #111827;
}
QLabel#logo {
    background: transparent;
    color: white;
    font-size: 22px;
    font-weight: bold;
}
QLabel#stepIndicator {
    background: transparent;
    color: #FCA5A5;
    font-weight: bold;
}
QLabel[heading="true"] {
    font-size: 24px;
    font-weight: bold;
    color: #111827;
}
QLabel[section="true"] {
    font-size: 17px;
    font-weight: bold;
}
QLabel[muted="true"] {
    color: #6B7280;
}
QFrame[card="true"] {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
}
QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    background: white;
    min-height: 28px;
    padding: 7px;
}
QPushButton {
    background: #C91E32;
    color: white;
    border-radius: 8px;
    border: none;
    padding: 12px;
    font-weight: bold;
}
QPushButton:hover {
    background: #A91A2B;
}
QPushButton[secondary="true"] {
    background: #E5E7EB;
    color: #111827;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    margin-top: 15px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
}
QScrollArea {
    border: none;
}
"""


def property_(parent, name, value, kind="string", dynamic=False):
    attrs = {"name": name}
    if dynamic:
        attrs["stdset"] = "0"

    p = ET.SubElement(parent, "property", attrs)
    ET.SubElement(p, kind).text = str(value)
    return p


def layout(parent, name, kind="QVBoxLayout", margins=16, spacing=12):
    lay = ET.SubElement(
        parent, "layout",
        {"class": kind, "name": name}
    )
    if margins is not None:
        for side in ["left", "top", "right", "bottom"]:
            property_(lay, f"{side}Margin", margins, "number")
    if spacing is not None:
        property_(lay, "spacing", spacing, "number")
    return lay


def widget(parent_layout, cls, name, text=None, **kwargs):
    item = ET.SubElement(parent_layout, "item")
    w = ET.SubElement(
        item, "widget",
        {"class": cls, "name": name}
    )

    if text is not None:
        property_(w, "text", text)

    for k, v in kwargs.items():
        if k in ["card", "heading", "section", "muted", "secondary"]:
            property_(w, k, "true" if v else "false",
                      "bool", dynamic=True)
        elif isinstance(v, bool):
            property_(w, k, "true" if v else "false", "bool")
        elif isinstance(v, int):
            property_(w, k, v, "number")
        else:
            property_(w, k, v)

    return w


def nested(parent_layout, name, kind="QVBoxLayout"):
    item = ET.SubElement(parent_layout, "item")
    return ET.SubElement(
        item, "layout",
        {"class": kind, "name": name}
    )


def field(form, row, title, cls, name, **props):
    left = ET.SubElement(
        form, "item", {"row": str(row), "column": "0"}
    )
    lbl = ET.SubElement(
        left, "widget",
        {"class": "QLabel", "name": f"label_{name}"}
    )
    property_(lbl, "text", title)

    right = ET.SubElement(
        form, "item", {"row": str(row), "column": "1"}
    )
    inp = ET.SubElement(
        right, "widget",
        {"class": cls, "name": name}
    )

    for k, v in props.items():
        property_(
            inp, k, v,
            "number" if isinstance(v, int) else "string"
        )

    return inp


def card(parent, name, title):
    frame = widget(parent, "QFrame", name, card=True)
    content = layout(frame, name + "Layout", margins=24)
    widget(
        content, "QLabel",
        name + "Title", title, section=True
    )
    return content


def add_vehicle_placeholder(parent, prefix, title, subtitle):
    row = widget(parent, "QFrame", prefix + "Card", card=True)
    content = layout(row, prefix + "Layout", "QHBoxLayout", 12, 14)

    image = widget(
        content, "QLabel", prefix + "Image",
        "ẢNH XE"
    )
    property_(image, "minimumWidth", 125, "number")
    property_(image, "minimumHeight", 95, "number")
    property_(image, "alignment", "Qt::AlignCenter", "enum")
    property_(
        image, "styleSheet",
        "background:#F1F5F9; color:#64748B;"
        "border-radius:8px;"
    )

    info = nested(content, prefix + "Info")
    widget(info, "QLabel", prefix + "Name", title, section=True)
    widget(info, "QLabel", prefix + "Specs", subtitle, muted=True)
    widget(
        info, "QLabel", prefix + "Price",
        "Giá sẽ lấy từ dữ liệu CSV",
        muted=True
    )
    widget(
        info, "QPushButton",
        prefix + "DetailsButton",
        "Xem thông số"
    )


def make_page(stack, name):
    return ET.SubElement(
        stack, "widget", {"class": "QWidget", "name": name}
    )


def create():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    ui = ET.Element("ui", {"version": "4.0"})
    ET.SubElement(ui, "class").text = "AutoWiseWindow"

    window = ET.SubElement(
        ui, "widget",
        {"class": "QMainWindow", "name": "AutoWiseWindow"}
    )

    geom = ET.SubElement(
        window, "property", {"name": "geometry"}
    )
    rect = ET.SubElement(geom, "rect")
    for key, value in [
        ("x", 0), ("y", 0),
        ("width", 1150), ("height", 820)
    ]:
        ET.SubElement(rect, key).text = str(value)

    property_(window, "windowTitle", "AutoWise AI")
    property_(window, "styleSheet", STYLE)

    central = ET.SubElement(
        window, "widget",
        {"class": "QWidget", "name": "centralwidget"}
    )

    root = layout(central, "mainLayout", margins=0, spacing=0)

    # ===== HEADER =====
    header = widget(root, "QFrame", "header")
    head = layout(header, "headerLayout", "QHBoxLayout", 24)

    widget(head, "QLabel", "logo", "AUTOWISE AI")
    widget(head, "QLabel", "stepIndicator", "BƯỚC 1 / 3")

    # ===== STACKED WIDGET =====
    item = ET.SubElement(root, "item")
    stack = ET.SubElement(
        item, "widget",
        {"class": "QStackedWidget", "name": "stackedWidget"}
    )
    property_(stack, "currentIndex", 0, "number")

    # ============================
    # PAGE 1 - USER INFORMATION
    # ============================
    p1 = make_page(stack, "pageUser")
    l1 = layout(p1, "userPageLayout", margins=65, spacing=22)

    widget(
        l1, "QLabel", "welcomeTitle",
        "Chào mừng đến với AutoWise AI",
        heading=True
    )

    widget(
        l1, "QLabel", "welcomeSubtitle",
        "Ứng dụng học máy hỗ trợ dự đoán giá "
        "và lựa chọn xe ô tô phù hợp.",
        muted=True
    )

    user_card = card(l1, "userCard", "Thông tin của bạn")

    widget(user_card, "QLabel", "fullNameLabel", "Họ và tên *")
    widget(
        user_card, "QLineEdit", "txtFullName",
        placeholderText="Nhập họ và tên"
    )

    widget(user_card, "QLabel", "displayNameLabel", "Tên hiển thị")
    widget(
        user_card, "QLineEdit", "txtDisplayName",
        placeholderText="Bạn muốn AutoWise gọi mình là gì?"
    )

    widget(
        user_card, "QLabel", "privacyNote",
        "Thông tin này chỉ để cá nhân hóa giao diện.",
        muted=True
    )

    widget(
        user_card, "QPushButton",
        "btnStart", "BẮT ĐẦU TƯ VẤN"
    )

    # ============================
    # PAGE 2 - VEHICLE FORM
    # ============================
    p2 = make_page(stack, "pageVehicle")
    page2 = layout(p2, "vehiclePageLayout", margins=18)

    scroll2 = widget(page2, "QScrollArea", "vehicleScroll")
    property_(scroll2, "widgetResizable", "true", "bool")

    content2 = ET.SubElement(
        scroll2, "widget",
        {"class": "QWidget", "name": "vehicleScrollContent"}
    )
    l2 = layout(content2, "vehicleContentLayout", margins=24)

    widget(
        l2, "QLabel", "vehicleTitle",
        "Thông tin chiếc xe mong muốn",
        heading=True
    )
    widget(
        l2, "QLabel", "vehicleSubtitle",
        "Điền thông tin xe và ngân sách để AutoWise phân tích.",
        muted=True
    )

    basic = card(l2, "basicCard", "1. Thông tin cơ bản")
    f1 = nested(basic, "basicForm", "QFormLayout")

    field(f1, 0, "Hãng xe", "QComboBox", "cboManufacturer")
    field(f1, 1, "Dòng xe", "QComboBox", "cboModel")
    field(
        f1, 2, "Năm sản xuất", "QSpinBox", "spinYear",
        minimum=1900, maximum=2030, value=2018
    )
    field(f1, 3, "Kiểu dáng", "QComboBox", "cboType")

    specs = card(l2, "specsCard", "2. Thông số kỹ thuật")
    f2 = nested(specs, "specsForm", "QFormLayout")

    field(
        f2, 0, "Số miles đã đi", "QSpinBox", "spinOdometer",
        maximum=1000000, value=60000, suffix=" miles"
    )
    field(f2, 1, "Tình trạng xe", "QComboBox", "cboCondition")
    field(f2, 2, "Nhiên liệu", "QComboBox", "cboFuel")
    field(f2, 3, "Hộp số", "QComboBox", "cboTransmission")

    budget = card(l2, "budgetCard", "3. Ngân sách")
    bf = nested(budget, "budgetForm", "QFormLayout")
    field(
        bf, 0, "Ngân sách tối đa (USD)",
        "QSpinBox", "spinBudget",
        maximum=1000000, value=20000, prefix="$ "
    )

    # Advanced options
    item_advanced = ET.SubElement(l2, "item")
    advanced = ET.SubElement(
        item_advanced, "widget",
        {"class": "QGroupBox", "name": "advancedGroup"}
    )

    property_(
        advanced, "title",
        "Tùy chọn nâng cao (không bắt buộc)"
    )
    property_(advanced, "checkable", "true", "bool")
    property_(advanced, "checked", "false", "bool")

    af = layout(
        advanced, "advancedForm", "QFormLayout", 16, 12
    )

    for idx, (title, name) in enumerate([
        ("Hệ dẫn động", "cboDrive"),
        ("Số xi-lanh", "cboCylinders"),
        ("Màu xe", "cboPaintColor"),
        ("Tình trạng giấy tờ", "cboTitleStatus"),
        ("Bang tại Mỹ", "cboState"),
    ]):
        field(af, idx, title, "QComboBox", name)

    actions2 = nested(l2, "formButtons", "QHBoxLayout")
    widget(
        actions2, "QPushButton", "btnBackUser",
        "QUAY LẠI", secondary=True
    )
    widget(
        actions2, "QPushButton", "btnReset",
        "NHẬP LẠI", secondary=True
    )
    widget(
        actions2, "QPushButton", "btnAnalyze",
        "PHÂN TÍCH VÀ TÌM XE"
    )

    # ============================
    # PAGE 3 - AI RESULTS
    # ============================
    p3 = make_page(stack, "pageResults")
    page3 = layout(p3, "resultsPageLayout", margins=18)

    scroll3 = widget(page3, "QScrollArea", "resultsScroll")
    property_(scroll3, "widgetResizable", "true", "bool")

    content3 = ET.SubElement(
        scroll3, "widget",
        {"class": "QWidget", "name": "resultsScrollContent"}
    )
    l3 = layout(content3, "resultsContentLayout", margins=24)

    widget(
        l3, "QLabel", "lblResultsTitle",
        "Kết quả phân tích AutoWise AI",
        heading=True
    )

    # Predicted price
    prediction = card(l3, "predictionCard", "1. Giá xe AI dự đoán")
    widget(
        prediction, "QLabel", "lblSelectedVehicle",
        "Tên và thông số xe sẽ hiển thị tại đây."
    )

    price = widget(
        prediction, "QLabel", "lblPredictedPrice",
        "CHƯA CÓ KẾT QUẢ ML"
    )
    property_(
        price, "styleSheet",
        "font-size:28px;font-weight:bold;color:#C91E32;"
    )

    widget(
        prediction, "QLabel", "lblPredictionNote",
        "Giá tham khảo dựa trên dữ liệu tin đăng xe cũ lịch sử tại Mỹ.",
        muted=True, wordWrap=True
    )

    # Recommended cars
    rec = card(l3, "recommendCard", "2. Top 5 xe phù hợp")

    widget(
        rec, "QLabel", "lblRecommendNote",
        "Các thẻ dưới đây là mẫu bố cục. "
        "Nội dung thật sẽ lấy từ mô hình gợi ý và CSV.",
        muted=True, wordWrap=True
    )

    for i in range(1, 6):
        add_vehicle_placeholder(
            rec, f"recommended{i}",
            f"Xe đề xuất #{i}",
            "Hãng · Dòng xe · Năm · Mileage · Tình trạng"
        )

    # Alternative cars
    alt = card(
        l3, "alternativesCard",
        "3. Những xe khác cùng mức giá"
    )

    widget(
        alt, "QLabel", "lblAlternativeNote",
        "Những xe có giá niêm yết gần mức giá tham khảo.",
        muted=True
    )

    for i in range(1, 4):
        add_vehicle_placeholder(
            alt, f"alternative{i}",
            f"Lựa chọn thay thế #{i}",
            "Hãng · Dòng xe · Năm · Mileage"
        )

    widget(
        l3, "QPushButton", "btnBackVehicle",
        "CHỈNH SỬA THÔNG TIN", secondary=True
    )

    ET.SubElement(ui, "resources")
    ET.SubElement(ui, "connections")

    tree = ET.ElementTree(ui)
    ET.indent(tree, space="  ")

    # Xuất XML hợp lệ, không có dòng trống trước khai báo.
    tree.write(
        OUTPUT,
        encoding="utf-8",
        xml_declaration=True
    )

    # Kiểm tra cú pháp XML.
    ET.parse(OUTPUT)

    print("ĐÃ TẠO FILE UI THÀNH CÔNG:")
    print(OUTPUT)
    print("Có 3 trang, form xe, 5 thẻ đề xuất và 3 thẻ xe thay thế.")


if __name__ == "__main__":
    create()
