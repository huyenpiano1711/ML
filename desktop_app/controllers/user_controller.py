"""
user_controller.py - Screen 1 (pageWelcome): the START button and the full name check.
`ui` is the AutoWiseMainWindowEx that owns the widgets.
"""
from desktop_app.controllers import PAGE_VEHICLE


class UserController:
    def __init__(self, ui):
        self.ui = ui

    def userName(self):
        """Display name if given, otherwise the full name."""
        return self.ui.lineEditDisplayName.text().strip() or self.ui.lineEditFullName.text().strip()

    def start(self):
        """Screen 1 -> Screen 2: full name is required (personalisation only, nothing is stored)."""
        if not self.ui.lineEditFullName.text().strip():
            self.ui.showWarning("Missing information", "Please enter your full name to start.")
            self.ui.lineEditFullName.setFocus()
            return
        name = self.userName()
        if self.ui.user is None:
            self.ui.labelHeaderUser.setText(f"Hi, {name}")
        self.ui.labelVehicleTitle.setText(f"{name}, which car do you have in mind?")
        self.ui.goToPage(PAGE_VEHICLE)
