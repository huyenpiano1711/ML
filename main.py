"""
main.py - Start AutoWise AI. Run from the project folder:   python main.py

The app always opens on the sign-in window: nothing can be used without an account.
    - user  -> the car advisor (price estimate, Top 5 matches, history, saved cars, PDF)
    - admin -> the admin console (dashboard, users, price models, data & segments, activity log)
First run: the database desktop_app/databases/autowise.sqlite is created with the default admin account
(username admin / password Admin@2026 - change it in ACCOUNT after the first sign-in).
"""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from desktop_app.UI.LoginMainWindowEx import LoginMainWindowEx  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AutoWise AI")
    login = LoginMainWindowEx()
    login.setupUi(QMainWindow())
    login.showWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
