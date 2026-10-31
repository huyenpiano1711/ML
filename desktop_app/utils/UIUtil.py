"""
UIUtil.py - Shared helpers for every AutoWise window:
    - load the bundled fonts (Playfair Display + Inter) once per application
    - re-apply the style sheet so dynamic properties (role, variant, ...) take effect
    - resolve image paths ("../images/...") written in the .ui files to absolute paths,
      so icons work no matter which folder the app is started from.
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QObject, QRectF
from PyQt6.QtGui import QFontDatabase, QIcon, QPixmap, QPainter, QPainterPath, QLinearGradient, QColor
from PyQt6.QtWidgets import QPushButton, QLabel, QWidget

APP_DIR = Path(__file__).resolve().parents[1]          # D:\AutoWise\desktop_app
IMAGE_DIR = APP_DIR / "images"
FONT_DIR = APP_DIR / "fonts"


class UIUtil:
    fontsLoaded = False

    @staticmethod
    def loadFonts():
        if UIUtil.fontsLoaded:
            return
        for font in sorted(FONT_DIR.glob("*.ttf")):
            QFontDatabase.addApplicationFont(str(font))
        UIUtil.fontsLoaded = True

    @staticmethod
    def imagePath(name):
        return IMAGE_DIR / name

    @staticmethod
    def applyStyleSheet(widget: QWidget):
        """pyuic6 sets styleSheet before the dynamic properties, so set it again.
        Relative 'url(../images/x.png)' in the .ui style sheet becomes an absolute path."""
        style = widget.styleSheet().replace("url(../images/", f"url({IMAGE_DIR.as_posix()}/")
        widget.setStyleSheet(style)

    @staticmethod
    def applyImages(widget: QWidget):
        """Buttons with dynamic property 'iconName' and labels with 'imageName' (set in the .ui)."""
        for button in widget.findChildren(QPushButton):
            name = button.property("iconName")
            if name:
                button.setIcon(QIcon(str(IMAGE_DIR / f"ic_{name}.png")))
        for label in widget.findChildren(QLabel):
            name = label.property("imageName")
            if name:
                label.setPixmap(QPixmap(str(IMAGE_DIR / name)))

    @staticmethod
    def setupWindow(window: QWidget):
        UIUtil.loadFonts()
        UIUtil.applyStyleSheet(window)
        UIUtil.applyImages(window)

    @staticmethod
    def repolish(widget: QWidget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    @staticmethod
    def firstImage(*names):
        """First existing file in images/ (lets you drop in your own hero.jpg / login.jpg)."""
        for name in names:
            path = IMAGE_DIR / name
            if path.exists():
                return path
        return None


class ImageBackground(QObject):
    """Paints a cover-scaled, rounded, darkened image behind a QFrame (hero / login panel)."""

    def __init__(self, frame, image_path, radius=20, shade=(150, 90, 40)):
        super().__init__(frame)
        self.frame = frame
        self.radius = radius
        self.shade = shade
        self.source = QPixmap(str(image_path)) if image_path else QPixmap()
        self.label = QLabel(frame)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.lower()
        frame.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize and not self.source.isNull():
            self.render()
        return False

    def render(self):
        w, h = self.frame.width(), self.frame.height()
        canvas = QPixmap(w, h)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), self.radius, self.radius)
        p.setClipPath(path)
        scaled = self.source.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation)
        p.drawPixmap((w - scaled.width()) // 2, (h - scaled.height()) // 2, scaled)
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(11, 11, 13, self.shade[0]))
        grad.setColorAt(0.55, QColor(11, 11, 13, self.shade[1]))
        grad.setColorAt(1.0, QColor(11, 11, 13, self.shade[2]))
        p.fillRect(0, 0, w, h, grad)
        p.end()
        self.label.setGeometry(0, 0, w, h)
        self.label.setPixmap(canvas)
