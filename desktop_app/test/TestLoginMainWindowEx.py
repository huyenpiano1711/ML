import sys
from pathlib import Path

# Run directly from PyCharm / VS Code: add D:\AutoWise to sys.path
PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PyQt6.QtWidgets import QApplication, QMainWindow

from desktop_app.UI.LoginMainWindowEx import LoginMainWindowEx

app = QApplication(sys.argv)
myui = LoginMainWindowEx()
myui.setupUi(QMainWindow())
myui.showWindow()
sys.exit(app.exec())
