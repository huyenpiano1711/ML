
from pathlib import Path
from copy import deepcopy
import shutil
import xml.etree.ElementTree as ET

UI = Path(r"D:\AutoWise\desktop_app\ui\autowise.ui")
BACKUP = UI.with_name("autowise_before_improve.ui")

if not UI.exists():
    raise FileNotFoundError(f"Không tìm thấy file: {UI}")

shutil.copy2(UI, BACKUP)
tree = ET.parse(UI)
root = tree.getroot()


def find_widget(name):
    w = root.find(f".//widget[@name='{name}']")
    if w is None:
        raise ValueError(f"Thiếu widget: {name}")
    return w


def set_prop(obj, name, value, kind="number"):
    p = obj.find(f"./property[@name='{name}']")
    if p is None:
        p = ET.SubElement(obj, "property", name=name)
    for child in list(p):
        p.remove(child)
    ET.SubElement(p, kind).text = str(value)


def margins(lay, left, top, right, bottom):
    for name, val in zip(
        ("leftMargin", "topMargin", "rightMargin", "bottomMargin"),
        (left, top, right, bottom)
    ):
        set_prop(lay, name, val)


STYLE = """
QMainWindow, QWidget {
    background-color: #F7F8FA;
    color: #111827;
    font-family: "Segoe UI";
    font-size: 13px;
}
QFrame#header {
    background: #111827;
    border: none;
}
QLabel#logo {
    color: white;
    background: transparent;
    font-size: 21px;
    font-weight: 700;
}
QLabel#stepIndicator {
    color: #FDA4AF;
    background: transparent;
    font-size: 12px;
    font-weight: 700;
}
QLabel[heading="true"] {
    font-size: 23px;
    font-weight: 700;
    color: #111827;
}
QLabel[section="true"] {
    font-size: 16px;
    font-weight: 700;
    color: #111827;
}
QLabel[muted="true"] {
    color: #64748B;
}
QFrame[card="true"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
}
QLineEdit, QComboBox, QSpinBox {
    background: white;
    color: #111827;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    min-height: 29px;
    padding: 6px 9px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #C91E32;
}
QPushButton {
    background: #C91E32;
    color: white;
    border: none;
    border-radius: 7px;
    padding: 9px 14px;
    min-height: 22px;
    font-weight: 700;
}
QPushButton:hover {
    background: #A7192B;
}
QPushButton[secondary="true"] {
    background: #EEF2F6;
    color: #334155;
    border: 1px solid #E2E8F0;
}
QPushButton[outline="true"] {
    background: white;
    color: #B91C30;
    border: 1px solid #E8A2AD;
    padding: 6px 12px;
}
QPushButton[outline="true"]:hover {
    background: #FFF1F2;
}
QGroupBox {
    font-weight: 700;
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    margin-top: 16px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
}
QScrollArea {
    border: none;
    background: #F7F8FA;
}
"""

window = find_widget("AutoWiseWindow")
set_prop(window, "styleSheet", STYLE, "string")

# ================================
# HEADER
# ================================

header = find_widget("header")
header_layout = header.find("./layout")

margins(header_layout, 24, 14, 24, 14)

set_prop(header, "minimumHeight", 64)
set_prop(header, "maximumHeight", 76)

# Đưa chỉ báo bước về phía bên phải.
spacer_item = ET.Element("item")
spacer = ET.SubElement(
    spacer_item, "spacer", name="headerSpacer"
)
set_prop(spacer, "orientation", "Qt::Horizontal", "enum")
set_prop(spacer, "sizeType", "Expanding", "enum")
p = ET.SubElement(spacer, "property", name="sizeHint")
size = ET.SubElement(p, "size")
ET.SubElement(size, "width").text = "40"
ET.SubElement(size, "height").text = "20"

# Header hiện có logo và stepIndicator.
# Chỉ thêm spacer nếu chưa tồn tại.
if header_layout.find("./item/spacer[@name='headerSpacer']") is None:
    header_layout.insert(1, spacer_item)


# ================================
# TRANG 1: CĂN GIỮA NỘI DUNG
# ================================

page = find_widget("pageUser")
page_layout = page.find("./layout")

original_items = list(page_layout.findall("./item"))

for item in original_items:
    page_layout.remove(item)

margins(page_layout, 20, 20, 20, 20)
set_prop(page_layout, "spacing", 0)


def vertical_spacer(name):
    item = ET.Element("item")
    s = ET.SubElement(item, "spacer", name=name)
    set_prop(s, "orientation", "Qt::Vertical", "enum")
    set_prop(s, "sizeType", "Expanding", "enum")
    p = ET.SubElement(s, "property", name="sizeHint")
    sz = ET.SubElement(p, "size")
    ET.SubElement(sz, "width").text = "20"
    ET.SubElement(sz, "height").text = "30"
    return item


page_layout.append(vertical_spacer("userTopSpacer"))

content_item = ET.SubElement(
    page_layout, "item",
    alignment="Qt::AlignHCenter"
)
content = ET.SubElement(
    content_item, "widget",
    **{"class": "QWidget", "name": "userContent"}
)
set_prop(content, "maximumWidth", 720)
set_prop(content, "minimumWidth", 450)

content_layout = ET.SubElement(
    content, "layout",
    **{"class": "QVBoxLayout", "name": "userContentLayout"}
)
margins(content_layout, 8, 8, 8, 8)
set_prop(content_layout, "spacing", 10)

for item in original_items:
    content_layout.append(item)

title = find_widget("welcomeTitle")
set_prop(title, "maximumHeight", 45)

subtitle = find_widget("welcomeSubtitle")
set_prop(subtitle, "maximumHeight", 34)
set_prop(subtitle, "wordWrap", "true", "bool")

user_card = find_widget("userCard")
user_card_layout = user_card.find("./layout")
margins(user_card_layout, 22, 20, 22, 20)
set_prop(user_card_layout, "spacing", 9)

page_layout.append(vertical_spacer("userBottomSpacer"))


# ================================
# TRANG 2: FORM HAI CỘT
# ================================

def convert_form_to_grid(name):
    old = root.find(f".//layout[@name='{name}']")
    if old is None:
        return

    parent = None
    for node in root.iter():
        if old in list(node):
            parent = node
            break

    if parent is None:
        return

    fields = {}

    for item in old.findall("./item"):
        row = int(item.attrib.get("row", 0))
        col = int(item.attrib.get("column", 0))
        fields.setdefault(row, {})[col] = deepcopy(item)

    new = ET.Element(
        "layout",
        **{"class": "QGridLayout", "name": name}
    )

    set_prop(new, "horizontalSpacing", 20)
    set_prop(new, "verticalSpacing", 8)

    for index, row in enumerate(sorted(fields)):
        pair = fields[row]
        target_col = index % 2
        target_row = (index // 2) * 2

        if 0 in pair:
            label_item = pair[0]
            label_item.set("row", str(target_row))
            label_item.set("column", str(target_col))
            new.append(label_item)

        if 1 in pair:
            input_item = pair[1]
            input_item.set("row", str(target_row + 1))
            input_item.set("column", str(target_col))
            new.append(input_item)

    position = list(parent).index(old)
    parent.remove(old)
    parent.insert(position, new)


convert_form_to_grid("basicForm")
convert_form_to_grid("specsForm")
convert_form_to_grid("advancedForm")

for name in ("basicCard", "specsCard", "budgetCard"):
    w = find_widget(name)
    lay = w.find("./layout")
    margins(lay, 19, 17, 19, 17)
    set_prop(lay, "spacing", 10)

for name in ("vehicleContentLayout", "resultsContentLayout"):
    lay = root.find(f".//layout[@name='{name}']")
    if lay is not None:
        margins(lay, 25, 22, 25, 22)
        set_prop(lay, "spacing", 13)

# Năm và mileage dùng kích thước hiện có, không ép rộng bất thường.
# Chỉnh mô tả cho rõ đây là mileage tham khảo khi định giá.
find_widget("label_spinOdometer").find(
    "./property[@name='text']/string"
).text = "Số dặm đã đi (miles)"


# ================================
# TRANG 3: CẢI THIỆN THẺ XE
# ================================

for prefix in [
    "recommended1", "recommended2", "recommended3",
    "recommended4", "recommended5",
    "alternative1", "alternative2", "alternative3"
]:
    card = find_widget(prefix + "Card")
    set_prop(card, "minimumHeight", 137)
    set_prop(card, "maximumHeight", 158)

    lay = card.find("./layout")
    margins(lay, 12, 10, 12, 10)
    set_prop(lay, "spacing", 16)

    image = find_widget(prefix + "Image")
    set_prop(image, "minimumWidth", 205)
    set_prop(image, "maximumWidth", 205)
    set_prop(image, "minimumHeight", 112)
    set_prop(image, "maximumHeight", 112)
    set_prop(
        image, "styleSheet",
        "background:#F1F5F9; color:#64748B;"
        "border-radius:8px; font-size:12px;",
        "string"
    )

    name = find_widget(prefix + "Name")
    set_prop(
        name, "styleSheet",
        "font-size:15px;font-weight:700;color:#111827;",
        "string"
    )

    price = find_widget(prefix + "Price")
    set_prop(
        price, "styleSheet",
        "font-size:18px;font-weight:700;color:#C91E32;",
        "string"
    )

    button = find_widget(prefix + "DetailsButton")
    set_prop(button, "outline", "true", "bool")
    set_prop(button, "maximumWidth", 155)
    set_prop(button, "maximumHeight", 34)

    info = root.find(f".//layout[@name='{prefix}Info']")
    if info is not None:
        set_prop(info, "spacing", 4)

# Khối hiển thị giá dự đoán.
predicted = find_widget("lblPredictedPrice")
set_prop(
    predicted, "styleSheet",
    "font-size:30px;font-weight:700;color:#C91E32;",
    "string"
)

# Chỉnh ghi chú theo đúng nguồn dữ liệu.
note = find_widget("lblPredictionNote")
set_prop(
    note, "text",
    "Giá tham khảo dựa trên dữ liệu tin đăng xe cũ "
    "tại Mỹ năm 2021; không phải giá thị trường hiện tại.",
    "string"
)

# ================================
# LƯU VÀ KIỂM TRA XML
# ================================

ET.indent(tree, space="  ")
tree.write(
    UI,
    encoding="utf-8",
    xml_declaration=True
)

ET.parse(UI)

print("ĐÃ CHỈNH SỬA GIAO DIỆN THÀNH CÔNG")
print("File UI:", UI)
print("File backup:", BACKUP)
print("Đã giữ nguyên tên widget để kết nối PyQt6.")
