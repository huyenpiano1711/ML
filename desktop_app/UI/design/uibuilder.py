"""
uibuilder.py - Tiny helper that writes Qt Designer .ui files from Python (used once to create the new
windows; the .ui files can then be opened and edited in Qt Designer as usual, then converted with pyuic6).

    W("QPushButton", "pushButtonSave", text="SAVE", variant="ghost")
    L("QVBoxLayout", "verticalLayoutMain", [W(...), L(...), S("v")], margins=(24, 24, 24, 24), spacing=12)
    G("QGridLayout", "gridLayoutForm", [(W(...), row, col), (W(...), row, col, rowspan, colspan)])
"""
from xml.sax.saxutils import escape

STD_PROPS = {"text", "toolTip", "placeholderText", "title", "windowTitle", "minimumSize", "maximumSize",
             "sizePolicy", "alignment", "wordWrap", "cursor", "echoMode", "maxLength", "readOnly", "checked",
             "minimum", "maximum", "value", "singleStep", "decimals", "suffix", "prefix", "frameShape",
             "orientation", "currentIndex", "enabled", "flat", "editable", "selectionBehavior", "selectionMode",
             "alternatingRowColors", "sortingEnabled", "editTriggers", "textFormat", "widgetResizable",
             "horizontalScrollBarPolicy", "verticalScrollBarPolicy", "styleSheet", "geometry", "modal",
             "sizeGripEnabled", "openExternalLinks", "scaledContents", "frameShadow", "lineWidth",
             "showGrid", "wordWrapCol", "tabPosition", "documentMode", "textVisible", "format", "iconSize"}

ENUMS = {"alignment": "set", "echoMode": "enum", "frameShape": "enum", "orientation": "enum",
         "selectionBehavior": "enum", "selectionMode": "enum", "editTriggers": "set", "textFormat": "enum",
         "horizontalScrollBarPolicy": "enum", "verticalScrollBarPolicy": "enum", "frameShadow": "enum",
         "tabPosition": "enum"}


def _value(name, value):
    if name in ("minimumSize", "maximumSize", "iconSize"):
        return f"<size><width>{value[0]}</width><height>{value[1]}</height></size>"
    if name == "geometry":
        x, y, w, h = value
        return f"<rect><x>{x}</x><y>{y}</y><width>{w}</width><height>{h}</height></rect>"
    if name == "sizePolicy":
        h, v = value
        return (f'<sizepolicy hsizetype="{h}" vsizetype="{v}"><horstretch>0</horstretch>'
                f'<verstretch>0</verstretch></sizepolicy>')
    if name == "cursor":
        return f"<cursorShape>{value}</cursorShape>"
    if name in ENUMS:
        return f"<{ENUMS[name]}>{value}</{ENUMS[name]}>"
    if isinstance(value, bool):
        return f"<bool>{'true' if value else 'false'}</bool>"
    if isinstance(value, int):
        return f"<number>{value}</number>"
    if isinstance(value, float):
        return f"<double>{value}</double>"
    return f"<string>{escape(str(value))}</string>"


def props_xml(props, indent):
    out = []
    for name, value in props.items():
        if value is None:
            continue
        std = "" if name in STD_PROPS else ' stdset="0"'
        out.append(f'{indent}<property name="{name}"{std}>{_value(name, value)}</property>')
    return "\n".join(out)


class W:
    """A widget. layout= is the widget's own layout (L or G). items= for QComboBox; tabs= for QTabWidget;
    pages= for QStackedWidget (list of W)."""
    def __init__(self, cls, name, layout=None, items=None, tabs=None, pages=None, columns=None, attrs=None, **props):
        self.cls, self.name, self.layout, self.items = cls, name, layout, items or []
        self.tabs, self.pages, self.columns, self.attrs, self.props = tabs or [], pages or [], columns or [], attrs or {}, props

    def xml(self, indent=""):
        i2 = indent + " "
        parts = [f'{indent}<widget class="{self.cls}" name="{self.name}">']
        if self.props:
            parts.append(props_xml(self.props, i2))
        for text in self.items:
            parts.append(f'{i2}<item><property name="text"><string>{escape(text)}</string></property></item>')
        for text in self.columns:
            parts.append(f'{i2}<column><property name="text"><string>{escape(text)}</string></property></column>')
        for title, page in self.tabs:
            page_xml = page.xml(i2)
            parts.append(page_xml.replace(f'{i2}<widget class="{page.cls}" name="{page.name}">',
                                          f'{i2}<widget class="{page.cls}" name="{page.name}">\n{i2} <attribute name="title">'
                                          f'<string>{escape(title)}</string></attribute>', 1))
        for page in self.pages:
            parts.append(page.xml(i2))
        if self.layout is not None:
            parts.append(self.layout.xml(i2))
        parts.append(f"{indent}</widget>")
        return "\n".join(parts)


class S:
    """Spacer: 'h' or 'v'."""
    def __init__(self, direction="v", size=20, name=None, policy="Expanding"):
        self.direction, self.size, self.policy = direction, size, policy
        S.count = getattr(S, "count", 0) + 1
        self.name = name or f"spacer{S.count}"

    def xml(self, indent=""):
        o = "Qt::Orientation::Horizontal" if self.direction == "h" else "Qt::Orientation::Vertical"
        w, h = (self.size, 20) if self.direction == "h" else (20, self.size)
        pol = (f'{indent} <property name="sizeType"><enum>QSizePolicy::Policy::{self.policy}</enum></property>\n'
               if self.policy != "Expanding" else "")
        return (f'{indent}<spacer name="{self.name}">\n{indent} <property name="orientation"><enum>{o}</enum></property>\n'
                f'{pol}{indent} <property name="sizeHint" stdset="0"><size><width>{w}</width><height>{h}</height></size></property>\n'
                f"{indent}</spacer>")


class L:
    """Box layout. items: W, L, G or S; (item, stretch) is allowed for the stretch of that item."""
    def __init__(self, cls, name, items, margins=(0, 0, 0, 0), spacing=None):
        self.cls, self.name, self.items, self.margins, self.spacing = cls, name, items, margins, spacing

    def _head(self, indent):
        parts = [f'{indent}<layout class="{self.cls}" name="{self.name}">']
        if self.spacing is not None:
            parts.append(f'{indent} <property name="spacing"><number>{self.spacing}</number></property>')
        for side, v in zip(("left", "top", "right", "bottom"), self.margins):
            parts.append(f'{indent} <property name="{side}Margin"><number>{v}</number></property>')
        return parts

    def xml(self, indent=""):
        parts = self._head(indent)
        stretches = []
        for item in self.items:
            stretch = 0
            if isinstance(item, tuple):
                item, stretch = item
            stretches.append(str(stretch))
            parts.append(f"{indent} <item>\n{item.xml(indent + '  ')}\n{indent} </item>")
        if any(s != "0" for s in stretches) and self.cls in ("QVBoxLayout", "QHBoxLayout"):
            parts[0] = parts[0][:-1] + f' stretch="{",".join(stretches)}">'
        parts.append(f"{indent}</layout>")
        return "\n".join(parts)


class G(L):
    """Grid layout: items are (item, row, col) or (item, row, col, rowspan, colspan)."""
    def __init__(self, name, items, margins=(0, 0, 0, 0), spacing=None, hspacing=None, vspacing=None):
        super().__init__("QGridLayout", name, items, margins, spacing)
        self.hspacing, self.vspacing = hspacing, vspacing

    def xml(self, indent=""):
        parts = self._head(indent)
        if self.hspacing is not None:
            parts.append(f'{indent} <property name="horizontalSpacing"><number>{self.hspacing}</number></property>')
        if self.vspacing is not None:
            parts.append(f'{indent} <property name="verticalSpacing"><number>{self.vspacing}</number></property>')
        for entry in self.items:
            item, row, col, *span = entry
            rs, cs = span if span else (1, 1)
            attrs = f' row="{row}" column="{col}"' + (f' rowspan="{rs}" colspan="{cs}"' if span else "")
            parts.append(f"{indent} <item{attrs}>\n{item.xml(indent + '  ')}\n{indent} </item>")
        parts.append(f"{indent}</layout>")
        return "\n".join(parts)


def write_ui(path, top_cls, top_name, title, size, style, body_layout=None, central=None):
    """QMainWindow: central= W('QWidget','centralwidget', layout=...). QDialog/QWidget: body_layout= L(...)."""
    head = (f'<?xml version="1.0" encoding="UTF-8"?>\n<ui version="4.0">\n <class>{top_name}</class>\n'
            f' <widget class="{top_cls}" name="{top_name}">\n'
            f'  <property name="geometry"><rect><x>0</x><y>0</y><width>{size[0]}</width><height>{size[1]}</height></rect></property>\n'
            f'  <property name="windowTitle"><string>{escape(title)}</string></property>\n'
            f'  <property name="styleSheet"><string>{escape(style)}</string></property>\n')
    body = central.xml("  ") if central is not None else body_layout.xml("  ")
    xml = head + body + "\n </widget>\n <resources/>\n <connections/>\n</ui>\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(xml)
