import sys
from pathlib import Path

# Open the main window directly (guest user, no sign-in) - handy while designing
PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PyQt6.QtWidgets import QApplication, QMainWindow

from desktop_app.UI.AutoWiseMainWindowEx import AutoWiseMainWindowEx

app = QApplication(sys.argv)
myui = AutoWiseMainWindowEx()
myui.setupUi(QMainWindow())
myui.showWindow()
sys.exit(app.exec())
