"""
make_ui.py - Writes the .ui files of the windows added for user accounts and the admin panel:
    AccountDialog.ui, HistoryDialog.ui, FavoritesDialog.ui, CompareDialog.ui, AdminMainWindow.ui
The style is the AutoWise identity: the style sheet of AutoWiseMainWindow.ui + a few extra rules
(tables, tabs, admin sidebar). After running it, convert as usual:
    python desktop_app/UI/design/make_ui.py
    pyuic6 desktop_app/UI/AdminMainWindow.ui -o desktop_app/UI/AdminMainWindow.py   (same for the others)
The .ui files can then be opened and changed in Qt Designer.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uibuilder import G, L, S, W, write_ui  # noqa: E402

UI_DIR = Path(__file__).resolve().parents[1]
MAIN_UI = (UI_DIR / "AutoWiseMainWindow.ui").read_text(encoding="utf-8")
BASE = re.search(r'<property name="styleSheet">\s*<string>(.*?)</string>', MAIN_UI, re.S).group(1)
BASE = BASE.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")

EXTRA = """
/* ---------- Added for accounts and the admin panel ---------- */
QDialog, QWidget#pageDashboard, QWidget#pageUsers, QWidget#pageModels, QWidget#pageData, QWidget#pageActivity,
QWidget#tabProfile, QWidget#tabPassword, QWidget#tabExplore, QWidget#tabSegments, QWidget#tabLogins, QWidget#tabAudit,
QWidget#scrollAreaDashboardContents, QWidget#scrollAreaModelsContents, QWidget#scrollAreaExploreContents,
QWidget#scrollAreaSegmentsContents { background-color: #F5F5F7; }
QDoubleSpinBox { background-color: #FAFAFB; border: 1px solid #D9D9DF; border-radius: 9px; padding: 9px 12px;
                 color: #18181B; min-height: 20px; }
QDoubleSpinBox:focus { border-color: #D7263D; background-color: #FFFFFF; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; border: none; }
QSpinBox[compact="true"], QDoubleSpinBox[compact="true"], QLineEdit[compact="true"], QComboBox[compact="true"] { padding: 7px 10px; }
QTableWidget { background-color: #FFFFFF; border: 1px solid #E4E4E9; border-radius: 12px; gridline-color: #F0F0F2;
               selection-background-color: #FDE8EB; selection-color: #18181B; alternate-background-color: #FAFAFB; }
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section { background-color: #FAFAFB; color: #6B6B74; font-size: 10px; font-weight: 700; letter-spacing: 1px;
                       padding: 9px 8px; border: none; border-bottom: 1px solid #E4E4E9; }
QTableCornerButton::section { background-color: #FAFAFB; border: none; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { background: transparent; color: #6B6B74; padding: 10px 18px; margin-right: 6px; border: none;
               border-bottom: 2px solid transparent; font-weight: 600; font-size: 12px; letter-spacing: 1px; }
QTabBar::tab:selected { color: #18181B; border-bottom: 2px solid #D7263D; }
QTabBar::tab:hover { color: #18181B; }
QProgressBar { border: none; background-color: #ECECEF; border-radius: 4px; max-height: 8px; min-height: 8px; }
QProgressBar::chunk { background-color: #D7263D; border-radius: 4px; }
QPlainTextEdit { background-color: #FFFFFF; border: 1px solid #E4E4E9; border-radius: 12px; padding: 10px; color: #27272A; }
QPushButton[variant="danger"] { background-color: #FFFFFF; border: 1px solid #FCA5A5; color: #B91C1C; }
QPushButton[variant="danger"]:hover { background-color: #FEF2F2; }
QPushButton[size="small"] { padding: 9px 16px; font-size: 11px; }
QLabel[role="value"] { color: #18181B; font-size: 13px; background: transparent; }
QLabel[role="kpiNote"] { color: #8A8A93; font-size: 11px; background: transparent; }
QLabel[role="badge"] { background-color: #FDE8EB; color: #C81E35; border-radius: 10px; padding: 3px 10px;
                       font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QFrame[kpi="true"] { background-color: #FFFFFF; border: 1px solid #E4E4E9; border-radius: 14px; }
QFrame[kpi="true"][accent="true"] { border: 1px solid #F5C2CA;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FFEEF1, stop:0.7 #FFFFFF, stop:1 #FFFFFF); }

/* ---------- Admin sidebar (dark, like the sign-in picture panel) ---------- */
QFrame#frameSidebar { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141416, stop:0.75 #1C1114, stop:1 #4A1420);
                      border: none; }
QFrame#frameSidebar QLabel { color: #FFFFFF; background: transparent; }
QFrame#frameSidebar QLabel#labelSideTagline, QFrame#frameSidebar QLabel[role="statLabel"] { color: #A1A1AA; }
QFrame#frameSidebar QLabel[role="eyebrow"] { color: #FF8A99; }
QLabel#labelSideBrand { font-family: "Playfair Display", "Georgia", serif; font-size: 20px; font-weight: 600; letter-spacing: 5px; }
QLabel#labelSideTagline { font-size: 9px; font-weight: 600; letter-spacing: 3px; }
QFrame#frameSidebar QLabel#labelSideMark { background-color: #D7263D; border-radius: 3px; }
QPushButton[variant="side"] { background-color: transparent; color: #A1A1AA; border: none; border-left: 3px solid transparent;
                              border-radius: 0px; padding: 13px 22px; text-align: left; font-size: 11px; letter-spacing: 2px; }
QPushButton[variant="side"]:hover { color: #FFFFFF; background-color: rgba(255, 255, 255, 0.05); }
QPushButton[variant="side"][active="true"] { color: #FFFFFF; background-color: rgba(215, 38, 61, 0.18); border-left: 3px solid #D7263D; }
QPushButton[variant="sideGhost"] { background-color: transparent; color: #E4E4E7; border: 1px solid #3F3F46; border-radius: 9px;
                                   padding: 11px 16px; font-size: 11px; letter-spacing: 2px; }
QPushButton[variant="sideGhost"]:hover { border-color: #D7263D; color: #FFFFFF; }
QFrame#frameSideUser { background-color: rgba(255, 255, 255, 0.06); border-radius: 12px; }
"""
STYLE = BASE + EXTRA


# ----------------------------------------------------------------------------------- small builders
def lab(name, text="", role=None, **kw):
    return W("QLabel", name, text=text, role=role, **kw)


def btn(name, text, variant=None, tip=None, **kw):
    return W("QPushButton", name, text=text, variant=variant, toolTip=tip, cursor="PointingHandCursor", **kw)


def edit(name, placeholder="", **kw):
    return W("QLineEdit", name, placeholderText=placeholder, **kw)


def header(prefix, eyebrow, title, lead=None, right=None):
    """Eyebrow + big title (+ lead) on the left, optional widgets on the right."""
    texts = [lab(f"label{prefix}Eyebrow", eyebrow, "eyebrow"), lab(f"label{prefix}Title", title, "title")]
    if lead:
        texts.append(lab(f"label{prefix}Lead", lead, "muted", wordWrap=True))
    left = L("QVBoxLayout", f"verticalLayout{prefix}Header", texts, spacing=4)
    items = [left, S("h")]
    items += right or []
    return L("QHBoxLayout", f"horizontalLayout{prefix}Header", items, spacing=10)


def table(name, columns, **kw):
    return W("QTableWidget", name, columns=columns, alternatingRowColors=True, editTriggers="QAbstractItemView::EditTrigger::NoEditTriggers",
             selectionBehavior="QAbstractItemView::SelectionBehavior::SelectRows",
             selectionMode="QAbstractItemView::SelectionMode::SingleSelection", showGrid=False, **kw)


def card(name, layout, **kw):
    return W("QFrame", name, layout=layout, card="true", **kw)


def field(prefix, label, widget):
    return L("QVBoxLayout", f"verticalLayout{prefix}", [lab(f"label{prefix}", label.upper(), "field"), widget], spacing=6)


def kpi(n, label, accent=False):
    lay = L("QVBoxLayout", f"verticalLayoutKpi{n}", [
        lab(f"labelKpi{n}Label", label, "statLabel"),
        lab(f"labelKpi{n}Value", "-", "statValue"),
        lab(f"labelKpi{n}Note", "", "kpiNote", wordWrap=True)], margins=(18, 16, 18, 16), spacing=4)
    return W("QFrame", f"frameKpi{n}", layout=lay, kpi="true", accent="true" if accent else None)


def chart_card(name, title, note=""):
    lay = L("QVBoxLayout", f"verticalLayout{name}", [
        lab(f"label{name}Title", title, "cardTitle"),
        lab(f"label{name}Note", note, "muted", wordWrap=True),
        W("QWidget", f"widget{name}Plot", minimumSize=(0, 250),
          layout=L("QVBoxLayout", f"verticalLayout{name}Plot", [], spacing=0))], margins=(20, 18, 20, 16), spacing=4)
    return card(f"frame{name}", lay)


def close_row(prefix, extra=None):
    return L("QHBoxLayout", f"horizontalLayout{prefix}Buttons", (extra or []) + [S("h"), btn(f"pushButton{prefix}Close", "CLOSE", "ghost")],
             spacing=10)


# ----------------------------------------------------------------------------------- user dialogs
def account_dialog():
    profile = W("QWidget", "tabProfile", layout=L("QVBoxLayout", "verticalLayoutProfile", [
        G("gridLayoutProfileInfo", [
            (lab("labelUsernameCaption", "USERNAME", "field"), 0, 0), (lab("labelUsernameValue", "", "value"), 0, 1),
            (lab("labelRoleCaption", "ROLE", "field"), 1, 0), (lab("labelRoleValue", "", "value"), 1, 1),
            (lab("labelCreatedCaption", "MEMBER SINCE", "field"), 2, 0), (lab("labelCreatedValue", "", "value"), 2, 1),
            (lab("labelLastLoginCaption", "LAST SIGN-IN", "field"), 3, 0), (lab("labelLastLoginValue", "", "value"), 3, 1),
        ], hspacing=24, vspacing=10),
        W("QFrame", "lineProfile", divider="true"),
        field("FullName", "Full name", edit("lineEditFullName", "Your full name")),
        field("Email", "Email (optional)", edit("lineEditEmail", "name@example.com")),
        lab("labelProfileMessage", "", "error", wordWrap=True),
        L("QHBoxLayout", "horizontalLayoutProfileSave", [S("h"), btn("pushButtonSaveProfile", "SAVE CHANGES")]),
        S("v")], margins=(4, 18, 4, 4), spacing=12))
    password = W("QWidget", "tabPassword", layout=L("QVBoxLayout", "verticalLayoutPassword", [
        field("OldPassword", "Current password", edit("lineEditOldPassword", "Current password", echoMode="QLineEdit::EchoMode::Password")),
        field("NewPassword", "New password", edit("lineEditNewPassword", "8+ characters, letters and numbers", echoMode="QLineEdit::EchoMode::Password")),
        field("ConfirmPassword", "Confirm new password", edit("lineEditConfirmPassword", "Type the new password again", echoMode="QLineEdit::EchoMode::Password")),
        W("QCheckBox", "checkBoxShowPasswords", text="Show passwords"),
        lab("labelPasswordMessage", "", "error", wordWrap=True),
        L("QHBoxLayout", "horizontalLayoutPasswordSave", [S("h"), btn("pushButtonChangePassword", "CHANGE PASSWORD")]),
        S("v")], margins=(4, 18, 4, 4), spacing=12))
    body = L("QVBoxLayout", "verticalLayoutAccount", [
        header("Account", "ACCOUNT", "Your profile", "Update your name and email, or change your password."),
        W("QTabWidget", "tabWidgetAccount", tabs=[("Profile", profile), ("Password", password)], currentIndex=0),
        close_row("Account")], margins=(32, 28, 32, 24), spacing=14)
    write_ui(UI_DIR / "AccountDialog.ui", "QDialog", "AccountDialog", "AutoWise - Account", (560, 640), STYLE, body)


def history_dialog():
    tools = L("QHBoxLayout", "horizontalLayoutHistoryTools", [
        (edit("lineEditHistorySearch", "Filter by make or model…", compact="true"), 1),
        btn("pushButtonHistoryOpen", "OPEN AGAIN", None, "Show this analysis again on the results page", size="small"),
        btn("pushButtonHistoryPdf", "EXPORT PDF", "ghost", "Save this analysis as a PDF file", size="small"),
        btn("pushButtonHistoryDelete", "DELETE", "danger", size="small"),
        btn("pushButtonHistoryClear", "CLEAR ALL", "danger", size="small")], spacing=8)
    body = L("QVBoxLayout", "verticalLayoutHistory", [
        header("History", "HISTORY", "Your past analyses", "Every analysis you run is saved here. Open one again or export it as a PDF."),
        tools,
        (table("tableWidgetHistory", ["ID", "Date", "Car", "Mileage", "Budget", "Estimated price", "Price range", "Matches"]), 1),
        lab("labelHistoryEmpty", "No analysis yet. Run one from the SEARCH page.", "muted"),
        close_row("History", [lab("labelHistoryCount", "", "muted")])], margins=(32, 28, 32, 24), spacing=14)
    write_ui(UI_DIR / "HistoryDialog.ui", "QDialog", "HistoryDialog", "AutoWise - History", (1040, 640), STYLE, body)


def favorites_dialog():
    tools = L("QHBoxLayout", "horizontalLayoutFavoritesTools", [
        lab("labelFavoritesHint", "Tick 2 or 3 cars, then press COMPARE.", "muted"), S("h"),
        btn("pushButtonFavoritesCompare", "COMPARE", None, "Compare the ticked cars side by side", size="small"),
        btn("pushButtonFavoritesDetails", "DETAILS", "ghost", size="small"),
        btn("pushButtonFavoritesRemove", "REMOVE", "danger", size="small")], spacing=8)
    body = L("QVBoxLayout", "verticalLayoutFavorites", [
        header("Favorites", "SAVED CARS", "Cars you saved", "Save a car from its details window on the results page."),
        tools,
        (table("tableWidgetFavorites", ["Compare", "Car", "Price", "Mileage", "Condition", "Fuel · Gearbox", "Title", "State", "Saved on"]), 1),
        lab("labelFavoritesEmpty", "You have not saved any car yet.", "muted"),
        close_row("Favorites", [lab("labelFavoritesCount", "", "muted")])], margins=(32, 28, 32, 24), spacing=14)
    write_ui(UI_DIR / "FavoritesDialog.ui", "QDialog", "FavoritesDialog", "AutoWise - Saved cars", (1080, 640), STYLE, body)


def compare_dialog():
    body = L("QVBoxLayout", "verticalLayoutCompare", [
        header("Compare", "COMPARE", "Side by side", "Green marks the best value of each row."),
        (table("tableWidgetCompare", []), 1),
        lab("labelCompareSummary", "", "muted", wordWrap=True),
        close_row("Compare")], margins=(32, 28, 32, 24), spacing=14)
    write_ui(UI_DIR / "CompareDialog.ui", "QDialog", "CompareDialog", "AutoWise - Compare cars", (900, 600), STYLE, body)


# ----------------------------------------------------------------------------------- admin window
def sidebar():
    brand = L("QHBoxLayout", "horizontalLayoutSideBrand", [
        lab("labelSideMark", "", minimumSize=(6, 26), maximumSize=(6, 26)),
        L("QVBoxLayout", "verticalLayoutSideBrand", [lab("labelSideBrand", "AUTOWISE"), lab("labelSideTagline", "ADMIN CONSOLE")], spacing=0)],
        spacing=12)
    nav = [btn(f"pushButtonSide{n}", t, "side") for n, t in
           (("Dashboard", "DASHBOARD"), ("Users", "USERS"), ("Models", "PRICE MODELS"), ("Data", "DATA && SEGMENTS"),
            ("Activity", "ACTIVITY LOG"))]
    user = W("QFrame", "frameSideUser", layout=L("QVBoxLayout", "verticalLayoutSideUser", [
        lab("labelSideUserCaption", "SIGNED IN AS", "statLabel"), lab("labelSideUserName", "", wordWrap=True),
        lab("labelSideUserRole", "ADMIN", "eyebrow")], margins=(14, 12, 14, 12), spacing=2))
    lay = L("QVBoxLayout", "verticalLayoutSidebar", [
        L("QVBoxLayout", "verticalLayoutSideTop", [brand], margins=(22, 26, 22, 22)),
        lab("labelSideMenu", "   MENU", "statLabel"),
        *nav, S("v"),
        L("QVBoxLayout", "verticalLayoutSideBottom", [user, btn("pushButtonOpenUserApp", "OPEN CAR ADVISOR", "sideGhost",
                                                              "Use the app as a user (price estimate and recommendations)"),
                                                      btn("pushButtonSideLogout", "SIGN OUT", "sideGhost")],
          margins=(18, 10, 18, 22), spacing=10)], spacing=2)
    return W("QFrame", "frameSidebar", layout=lay, minimumSize=(250, 0), maximumSize=(250, 16777215))


def scroll_page(name, inner_layout):
    contents = W("QWidget", f"scrollArea{name}Contents", layout=inner_layout)
    area = W("QScrollArea", f"scrollArea{name}", widgetResizable=True, frameShape="QFrame::Shape::NoFrame",
             horizontalScrollBarPolicy="Qt::ScrollBarPolicy::ScrollBarAlwaysOff", pages=[contents])
    return area


def page_dashboard():
    right = [lab("labelDashboardUpdated", "", "muted"), btn("pushButtonDashboardRefresh", "REFRESH", "ghost", size="small")]
    kpis = G("gridLayoutKpis", [(kpi(1, "USERS", True), 0, 0), (kpi(2, "ANALYSES", True), 0, 1), (kpi(3, "ACTIVE USERS · 7 DAYS"), 0, 2),
                                (kpi(4, "PRICE MODEL ERROR (MAE)"), 1, 0), (kpi(5, "CARS IN CATALOG"), 1, 1),
                                (kpi(6, "FAILED SIGN-INS · 7 DAYS"), 1, 2)], spacing=16)
    row1 = L("QHBoxLayout", "horizontalLayoutDashCharts1", [
        (chart_card("ChartSearches", "Analyses per day", "Last 14 days"), 3),
        (chart_card("ChartMakes", "Most searched makes", "Number of analyses and average estimated price"), 2)], spacing=16)
    row2 = L("QHBoxLayout", "horizontalLayoutDashCharts2", [
        (chart_card("ChartLogins", "Sign-ins", "Successful and failed sign-ins, last 14 days"), 3),
        (chart_card("ChartBudget", "Budget vs. estimated price", "Share of analyses where the car costs more than the budget"), 2)],
        spacing=16)
    inner = L("QVBoxLayout", "verticalLayoutDashboard", [
        header("Dashboard", "OVERVIEW", "Dashboard", "Live numbers from the app database and the active price model.", right),
        kpis, row1, row2, S("v")], margins=(36, 30, 36, 30), spacing=20)
    return W("QWidget", "pageDashboard", layout=L("QVBoxLayout", "verticalLayoutPageDashboard", [scroll_page("Dashboard", inner)]))


def page_users():
    filters = L("QHBoxLayout", "horizontalLayoutUserFilters", [
        (edit("lineEditUserSearch", "Search username, name or email…", compact="true"), 1),
        W("QComboBox", "comboBoxUserRole", items=["All roles", "User", "Admin"], compact="true", minimumSize=(140, 0)),
        W("QComboBox", "comboBoxUserStatus", items=["All status", "Active", "Banned", "Locked now"], compact="true", minimumSize=(150, 0)),
        btn("pushButtonUserRefresh", "REFRESH", "ghost", size="small")], spacing=8)
    actions = L("QHBoxLayout", "horizontalLayoutUserActions", [
        lab("labelUsersCount", "", "muted"), S("h"),
        btn("pushButtonUserHistory", "VIEW ANALYSES", "ghost", size="small"),
        btn("pushButtonUserUnlock", "UNLOCK", "ghost", "Clear the 5-minute lock after wrong passwords", size="small"),
        btn("pushButtonUserBan", "BAN / UNBAN", "ghost", size="small"),
        btn("pushButtonUserRole", "MAKE ADMIN / USER", "ghost", size="small"),
        btn("pushButtonUserResetPassword", "RESET PASSWORD", "ghost", size="small"),
        btn("pushButtonUserDelete", "DELETE", "danger", size="small")], spacing=8)
    lay = L("QVBoxLayout", "verticalLayoutUsers", [
        header("Users", "PEOPLE", "Users", "Manage accounts: ban, unlock, change role, reset a password."),
        filters,
        (table("tableWidgetUsers", ["ID", "Username", "Full name", "Email", "Role", "Status", "Created", "Last sign-in", "Analyses"]), 1),
        actions], margins=(36, 30, 36, 30), spacing=16)
    return W("QWidget", "pageUsers", layout=lay)


def page_models():
    params = G("gridLayoutParams", [(lab(f"labelParam{i}", f"PARAM {i}", "field"), i - 1, 0) for i in range(1, 6)]
               + [(W("QDoubleSpinBox", f"doubleSpinBoxParam{i}", compact="true", decimals=4, maximum=100000.0), i - 1, 1)
                  for i in range(1, 6)], hspacing=14, vspacing=8)
    train = L("QVBoxLayout", "verticalLayoutTrain", [
        lab("labelTrainTitle", "Train a new model", "cardTitle"),
        lab("labelTrainLead", "Trains on the train set and is scored on the validation set (the test set is never used here).",
            "muted", wordWrap=True),
        field("Algorithm", "Algorithm", W("QComboBox", "comboBoxAlgorithm", compact="true")),
        params,
        G("gridLayoutTrainOptions", [
            (lab("labelAugment", "MASK OPTIONAL FIELDS", "field"), 0, 0),
            (W("QDoubleSpinBox", "doubleSpinBoxAugment", compact="true", decimals=2, maximum=0.9, singleStep=0.05, value=0.5), 0, 1),
            (W("QCheckBox", "checkBoxLogTarget", text="Learn log(1 + price)", checked=True), 1, 0, 1, 2)], hspacing=14, vspacing=8),
        btn("pushButtonTrain", "TRAIN AND VALIDATE"),
        W("QProgressBar", "progressBarTrain", value=0, textVisible=False),
        lab("labelTrainStatus", "", "muted", wordWrap=True), S("v")], margins=(22, 20, 22, 20), spacing=10)
    metrics = G("gridLayoutTrainMetrics", [(kpi(7, "MAE · APP INPUT", True), 0, 0), (kpi(8, "MAE · ALL FIELDS"), 0, 1),
                                           (kpi(9, "R² (USD)"), 0, 2), (kpi(10, "PRICE RANGE COVERAGE"), 0, 3)], spacing=12)
    save = L("QHBoxLayout", "horizontalLayoutSaveModel", [
        (edit("lineEditModelNote", "Note for this version (optional)", compact="true"), 1),
        btn("pushButtonSaveModel", "SAVE VERSION", "ghost", size="small")], spacing=8)
    result = L("QVBoxLayout", "verticalLayoutTrainResult", [
        lab("labelResultTitle", "Validation result", "cardTitle"), metrics,
        W("QWidget", "widgetTrainPlot", minimumSize=(0, 300), layout=L("QVBoxLayout", "verticalLayoutTrainPlot", [])),
        save], margins=(22, 20, 22, 20), spacing=12)
    top = L("QHBoxLayout", "horizontalLayoutModelsTop", [(card("frameTrain", train, minimumSize=(330, 0), maximumSize=(380, 16777215)), 0),
                                                         (card("frameTrainResult", result), 1)], spacing=16)
    registry = L("QVBoxLayout", "verticalLayoutRegistry", [
        L("QHBoxLayout", "horizontalLayoutRegistryHead", [lab("labelRegistryTitle", "Saved versions", "cardTitle"), S("h"),
                                                          lab("labelActiveModel", "", "badge"),
                                                          btn("pushButtonRefreshModels", "REFRESH", "ghost", size="small"),
                                                          btn("pushButtonActivateModel", "USE THIS VERSION", None, size="small")], spacing=8),
        (table("tableWidgetModels", ["Version", "Algorithm", "Created", "By", "MAE app (val)", "MAE all (val)", "MAE app (test)",
                                     "R²", "Coverage", "Note"], minimumSize=(0, 220)), 1)], margins=(22, 20, 22, 20), spacing=10)
    inner = L("QVBoxLayout", "verticalLayoutModels", [
        header("Models", "MACHINE LEARNING", "Price models",
               "Retrain the price model, compare versions and choose the one the app uses."),
        top, card("frameRegistry", registry), S("v")], margins=(36, 30, 36, 30), spacing=18)
    return W("QWidget", "pageModels", layout=L("QVBoxLayout", "verticalLayoutPageModels", [scroll_page("Models", inner)]))


def page_data():
    filters = G("gridLayoutDataFilters", [
        (lab("labelDataMake", "MAKE", "field"), 0, 0), (W("QComboBox", "comboBoxDataMake", compact="true", minimumSize=(160, 0)), 1, 0),
        (lab("labelDataYear", "YEAR", "field"), 0, 1),
        (L("QHBoxLayout", "horizontalLayoutDataYear", [W("QSpinBox", "spinBoxYearFrom", compact="true", minimum=1990, maximum=2022, value=1990),
                                                       lab("labelDataYearTo", "–", "muted"),
                                                       W("QSpinBox", "spinBoxYearTo", compact="true", minimum=1990, maximum=2022, value=2022)], spacing=6), 1, 1),
        (lab("labelDataPrice", "PRICE (USD)", "field"), 0, 2),
        (L("QHBoxLayout", "horizontalLayoutDataPrice", [W("QSpinBox", "spinBoxPriceFrom", compact="true", minimum=0, maximum=150000, singleStep=1000, value=0),
                                                        lab("labelDataPriceTo", "–", "muted"),
                                                        W("QSpinBox", "spinBoxPriceTo", compact="true", minimum=0, maximum=150000, singleStep=1000, value=150000)], spacing=6), 1, 2),
        (lab("labelDataChart", "CHART", "field"), 0, 3),
        (W("QComboBox", "comboBoxDataChart", compact="true", minimumSize=(210, 0),
           items=["Median price by year", "Median price by make", "Price vs. mileage", "Price distribution", "Listings by state"]), 1, 3),
        (btn("pushButtonDataApply", "APPLY", size="small"), 1, 4)], hspacing=14, vspacing=6)
    kpis = L("QHBoxLayout", "horizontalLayoutDataKpis", [kpi(11, "LISTINGS"), kpi(12, "MEDIAN PRICE"), kpi(13, "MEDIAN MILEAGE"),
                                                          kpi(14, "MEDIAN AGE")], spacing=12)
    explore_inner = L("QVBoxLayout", "verticalLayoutExplore", [
        card("frameDataFilters", L("QVBoxLayout", "verticalLayoutDataFilters", [filters], margins=(20, 16, 20, 16))),
        kpis, chart_card("ChartData", "Chart", "Cleaned listings (vehicles_filled.pkl)"),
        lab("labelDataSample", "SAMPLE OF THE FILTERED LISTINGS (200 ROWS)", "field"),
        table("tableWidgetData", ["ID", "Make", "Model", "Year", "Price", "Mileage", "Condition", "Type", "Fuel", "State"],
              minimumSize=(0, 300))], margins=(4, 16, 4, 4), spacing=16)
    explore = W("QWidget", "tabExplore", layout=L("QVBoxLayout", "verticalLayoutTabExplore", [scroll_page("Explore", explore_inner)]))

    feats = L("QHBoxLayout", "horizontalLayoutSegFeatures", [
        W("QCheckBox", "checkBoxFeatPrice", text="Price", checked=True), W("QCheckBox", "checkBoxFeatAge", text="Car age", checked=True),
        W("QCheckBox", "checkBoxFeatOdometer", text="Mileage", checked=True),
        W("QCheckBox", "checkBoxFeatCondition", text="Condition", checked=False), S("h")], spacing=18)
    controls = G("gridLayoutSegControls", [
        (lab("labelSegFeatures", "FEATURES (MIN-MAX SCALED)", "field"), 0, 0, 1, 4), (feats, 1, 0, 1, 4),
        (lab("labelKMax", "TRY K FROM 2 TO", "field"), 2, 0), (W("QSpinBox", "spinBoxKMax", compact="true", minimum=3, maximum=12, value=10), 3, 0),
        (btn("pushButtonElbow", "ELBOW METHOD", "ghost", size="small"), 3, 1),
        (lab("labelK", "NUMBER OF SEGMENTS (K)", "field"), 2, 2), (W("QSpinBox", "spinBoxK", compact="true", minimum=2, maximum=12, value=4), 3, 2),
        (btn("pushButtonRunKMeans", "RUN K-MEANS", size="small"), 3, 3)], hspacing=14, vspacing=6)
    charts = L("QHBoxLayout", "horizontalLayoutSegCharts", [
        (chart_card("ChartElbow", "Elbow method", "Inertia (WCSS) and silhouette score for each K"), 1),
        (chart_card("ChartClusters", "Segments", "Each dot is a listing (sample of 4,000), coloured by segment"), 1)], spacing=16)
    seg_inner = L("QVBoxLayout", "verticalLayoutSegments", [
        card("frameSegControls", L("QVBoxLayout", "verticalLayoutSegControls", [controls], margins=(20, 16, 20, 16))),
        charts,
        lab("labelClusterTable", "SEGMENT PROFILE", "field"),
        table("tableWidgetClusters", ["Segment", "Listings", "Share", "Median price", "Median age", "Median mileage", "Top makes", "Name"],
              minimumSize=(0, 200)),
        W("QPlainTextEdit", "plainTextEditClusterComment", readOnly=True, minimumSize=(0, 120))], margins=(4, 16, 4, 4), spacing=16)
    segments = W("QWidget", "tabSegments", layout=L("QVBoxLayout", "verticalLayoutTabSegments", [scroll_page("Segments", seg_inner)]))
    lay = L("QVBoxLayout", "verticalLayoutData", [
        header("Data", "DATASET", "Data & segments", "Explore the cleaned Craigslist listings and group cars into market segments with K-Means."),
        (W("QTabWidget", "tabWidgetData", tabs=[("Explore", explore), ("Segments (K-Means)", segments)], currentIndex=0), 1)],
        margins=(36, 30, 36, 20), spacing=12)
    return W("QWidget", "pageData", layout=lay)


def page_activity():
    logins = W("QWidget", "tabLogins", layout=L("QVBoxLayout", "verticalLayoutTabLogins", [
        table("tableWidgetLogins", ["Time", "Username", "Result", "Reason"])], margins=(0, 14, 0, 0)))
    audit = W("QWidget", "tabAudit", layout=L("QVBoxLayout", "verticalLayoutTabAudit", [
        table("tableWidgetAudit", ["Time", "Admin", "Action", "Target", "Detail"])], margins=(0, 14, 0, 0)))
    lay = L("QVBoxLayout", "verticalLayoutActivity", [
        header("Activity", "SECURITY", "Activity log", "Sign-in attempts and admin actions, newest first.",
               [btn("pushButtonActivityRefresh", "REFRESH", "ghost", size="small")]),
        (W("QTabWidget", "tabWidgetActivity", tabs=[("Sign-in history", logins), ("Admin actions", audit)], currentIndex=0), 1)],
        margins=(36, 30, 36, 30), spacing=12)
    return W("QWidget", "pageActivity", layout=lay)


def admin_window():
    stack = W("QStackedWidget", "stackedWidgetAdmin", pages=[page_dashboard(), page_users(), page_models(), page_data(), page_activity()])
    central = W("QWidget", "centralwidget", layout=L("QHBoxLayout", "horizontalLayoutAdmin", [sidebar(), (stack, 1)], spacing=0))
    write_ui(UI_DIR / "AdminMainWindow.ui", "QMainWindow", "MainWindow", "AutoWise AI - Admin console", (1400, 880), STYLE,
             central=central)


if __name__ == "__main__":
    account_dialog()
    history_dialog()
    favorites_dialog()
    compare_dialog()
    admin_window()
    print("Wrote AccountDialog.ui, HistoryDialog.ui, FavoritesDialog.ui, CompareDialog.ui, AdminMainWindow.ui")
