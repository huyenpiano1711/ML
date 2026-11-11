"""
results_controller.py - Screen 3 (pageResults): runs analyze() of app_service and shows its AnalysisResult.
`ui` is the AutoWiseMainWindowEx that owns the widgets.

The messages of app_service are in Vietnamese (owned by the Backend); this file only translates them,
because the interface is in English. A message it does not know is shown unchanged.
"""
import logging
import re
import threading
from importlib.metadata import PackageNotFoundError, version

from backend.schemas.result_schema import MAX_ALTERNATIVES, TOP_K, AnalysisResult
from desktop_app.controllers import PAGE_RESULTS
from desktop_app.controllers.vehicle_controller import translateError
from desktop_app.widgets.vehicle_card import VehicleCard, carDetails, known, labelOf, makeLabel, money, setCardImage, vehicleTitle

log = logging.getLogger("autowise.frontend")

TOP_NOTE = ("Cars within your budget that are most like the one you chose, same make first. "
            "Match % shows how close each car is to yours.")
SIMILAR_NOTE = "Up to 6 listings priced close to the estimated price of your car, so they may be over your budget."
TOP_EMPTY = "No car within your budget. Try a higher budget or fewer requirements."
TOP_UNAVAILABLE = "Car recommendations are unavailable right now."
SIMILAR_EMPTY = "No other listings near the estimated price."
SIMILAR_UNAVAILABLE = "Listings in the same price range are unavailable right now."
MSG_NOT_STARTED = "The analysis could not start. Please try again."
FIX_ENVIRONMENT = ("Start the app with the project's .venv (python -m pip install -r requirements.txt), "
                   "see README.md.")
STARTUP_TITLE = "AutoWise could not load everything"

# The part of Screen 3 a message is about
PRICE, BUDGET, TOP, SIMILAR, CATALOG = "price", "budget", "top", "similar", "catalog"


def usd(text):
    """28.832 -> $28,832"""
    return "$" + text.replace(".", ",")


# Messages of app_service.py and recommend.py. tests/test_e03_results.py fails if they drift apart.
MESSAGES = [
    (r"Dữ liệu gửi từ giao diện không đúng định dạng \(cần một dict các ô nhập\)\.", None,
     lambda m: "The form data was sent in the wrong format."),
    (r"Không tìm thấy file mô hình dự đoán giá \((.+)\)\. Chưa thể dự đoán giá\.", PRICE,
     lambda m: f"The price model file ({m[1]}) was not found, so no price can be estimated."),
    (r"Mô hình dự đoán giá gặp lỗi, chưa thể dự đoán giá cho xe này\.", PRICE,
     lambda m: "The price model failed, so no price can be estimated for this car. " + FIX_ENVIRONMENT),
    (r"Chưa có danh sách xe để gợi ý \(recommendation_catalog\.pkl\)\. "
     r"Chạy: python -m src\.recommendation\.build_catalog", CATALOG,
     lambda m: "The car list (recommendation_catalog.pkl) is missing. "
               "Run: python -m src.recommendation.build_catalog"),
    (r"Không nạp được danh sách xe để gợi ý\.", CATALOG,
     lambda m: "The car list could not be loaded. " + FIX_ENVIRONMENT),
    (r"Chức năng gợi ý xe gặp lỗi, chưa thể tìm xe phù hợp\.", TOP,
     lambda m: "The recommendation feature failed, so no matching cars could be found."),
    (r"Chức năng tìm xe cùng mức giá gặp lỗi\.", SIMILAR,
     lambda m: "Finding cars in the same price range failed."),
    (r"Đã xảy ra lỗi không mong muốn khi phân tích\. Vui lòng thử lại\.", None,
     lambda m: "An unexpected error occurred during the analysis. Please try again."),
    (r"Chưa có giá dự đoán nên không tìm được xe cùng mức giá\.", SIMILAR,
     lambda m: "There is no estimated price, so cars in the same price range cannot be found."),
    (r"Giá dự đoán của xe bạn nhập \((\S+) USD\) cao hơn ngân sách tối đa \((\S+) USD\)\.", BUDGET,
     lambda m: f"The estimated price ({usd(m[1])}) is above your maximum budget ({usd(m[2])})."),
    (r"Không có xe nào trong dữ liệu có giá không vượt quá (\S+) USD và khớp các điều kiện bắt buộc\.", TOP,
     lambda m: f"No car priced at or under {usd(m[1])} matches the required conditions."),
    (r"Không có xe nào trong dữ liệu có giá không vượt quá (\S+) USD\. Hãy tăng ngân sách\.", TOP,
     lambda m: f"No car is priced at or under {usd(m[1])}. Try a higher budget."),
    (r"Chỉ tìm được (\d+) xe phù hợp trong ngân sách (\S+) USD \(yêu cầu (\d+)\)\.", TOP,
     lambda m: f"Only {m[1]} of the {m[3]} requested cars fit your {usd(m[2])} budget."),
    (r"Không có xe nào có giá trong ±(\d+)% của (\S+) USD\.", SIMILAR,
     lambda m: f"No car is priced within ±{m[1]}% of {usd(m[2])}."),
    (r"Chỉ tìm được (\d+) xe có giá gần (\S+) USD\.", SIMILAR,
     lambda m: f"Only {m[1]} cars are priced close to {usd(m[2])}."),
    (r"Đã mở rộng khoảng giá lên ±(\d+)% để đủ xe\.", SIMILAR,
     lambda m: f"The price range was widened to ±{m[1]}% to find enough cars."),
    # backend/services/recommendation_service.py: the make is a required condition (C02)
    (r"Không có xe (.+) nào có giá không vượt quá (\S+) USD\. Đang gợi ý xe hãng khác gần nhu cầu nhất\.", TOP,
     lambda m: f"No {makeLabel(m[1])} is priced at or under {usd(m[2])}, so the closest cars "
               "from other makes are shown."),
    (r"Chỉ có (\d+) xe (.+) có giá không vượt quá (\S+) USD\. Các xe còn lại là hãng khác gần nhu cầu nhất\.", TOP,
     lambda m: f"Only {m[1]} {makeLabel(m[2])} {'car is' if m[1] == '1' else 'cars are'} priced at or under "
               f"{usd(m[3])}; the other places show the closest cars from other makes."),
]
MESSAGES = [(re.compile(pattern), section, english) for pattern, section, english in MESSAGES]


def describeMessage(message):
    """(English text, part of Screen 3 or None) of one message of app_service."""
    for pattern, section, english in MESSAGES:
        if match := pattern.fullmatch(message):
            return english(match), section
    return translateError(message), None


def translateMessage(message):
    return describeMessage(message)[0]


def priceGapPct(price, predicted_price):
    """Same formula as Recommender.similar_price(): the Backend does not send this value on CarCard."""
    return round((price - predicted_price) / predicted_price * 100, 1)


# Versions the saved files need: models/price_prediction/final_pipeline.joblib was saved with
# scikit-learn 1.9.1 (numpy 2 pickles), recommendation_catalog.pkl with the pandas string dtype of pandas >= 2.3.
REQUIRED_VERSIONS = {"scikit-learn": ("==", (1, 9, 1)), "numpy": (">=", (2, 0)), "pandas": (">=", (2, 3))}


def versionTuple(text):
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def environmentProblems(getVersion=version):
    """English messages for missing or wrong library versions (checked before loading the Backend)."""
    problems = []
    for package, (op, needed) in REQUIRED_VERSIONS.items():
        wanted = ".".join(map(str, needed))
        try:
            found = getVersion(package)
        except PackageNotFoundError:
            problems.append(f"{package} is not installed (needs {op}{wanted}).")
            continue
        have = versionTuple(found)[:len(needed)]
        if (op == "==" and have != needed) or (op == ">=" and have < needed):
            problems.append(f"{package} {found} is installed, but AutoWise needs {package}{op}{wanted}.")
    return problems


def defaultService():
    """Imported here because the Backend takes seconds to load (see warmUp)."""
    from backend.app_service import get_app_service
    return get_app_service()


def appMae():
    """Average error users get (MAE on the test set, app input path) from metrics.json, or None."""
    try:
        from backend.services.prediction_service import _test_mae
        return _test_mae()
    except Exception:                                   # noqa: BLE001
        return None


class ResultsController:
    def __init__(self, ui, getService=defaultService, setImage=setCardImage):
        self.ui = ui
        self.getService = getService
        self.warmThread = None
        self.startupProblems = []
        self.budget, self.estimate = None, None          # of the last analysis, for the details window
        self.topCards = [VehicleCard(ui, "TopCar", n, setImage) for n in range(1, TOP_K + 1)]
        self.similarCards = [VehicleCard(ui, "SimilarCar", n, setImage) for n in range(1, MAX_ALTERNATIVES + 1)]

    # ------------------------------------------------------------------ Backend
    def warmUp(self):
        """Load the model and catalog in the background: the window stays responsive while they load."""
        if self.warmThread is None:
            self.warmThread = threading.Thread(target=self.loadBackend, name="autowise-warm-up", daemon=True)
            self.warmThread.start()

    def loadBackend(self):
        """Runs in the warm-up thread: problems are logged and shown at once (not only after ANALYZE)."""
        problems = environmentProblems()
        if problems:
            problems.append(FIX_ENVIRONMENT)
        try:
            errors = self.getService().warm_up()
        except Exception:
            log.exception("Could not warm up the Backend")
            errors = [MSG_NOT_STARTED]
        for error in errors:
            log.warning(error)
        problems += [translateMessage(error) for error in errors]
        self.startupProblems = list(dict.fromkeys(problems))
        if self.startupProblems and hasattr(self.ui, "postBackendProblems"):
            # thread-safe: the window shows the dialog in the GUI thread
            self.ui.postBackendProblems(STARTUP_TITLE, "\n".join(f"• {text}" for text in self.startupProblems))

    def analyze(self, vehicle):
        """AnalysisResult for a validated VehicleInput. Never raises (an exception in a PyQt slot closes the app)."""
        if self.warmThread is not None:
            self.warmThread.join()                       # do not load the model a second time
        try:
            return self.getService().analyze(vehicle.to_dict())
        except Exception:
            log.exception("Could not start the analysis")
            return AnalysisResult.failure([MSG_NOT_STARTED])

    # ------------------------------------------------------------------ Screen 3
    def show(self, vehicle, result):
        """Show every part of the result that exists; errors go to a dialog, warnings stay on the page."""
        errors = [describeMessage(error) for error in result.errors]
        warnings = [describeMessage(warning) for warning in result.warnings]
        if result.price is None and not result.top_matches and not result.similar_price:
            self.ui.showWarning("Could not analyze this car", self.bullets(errors + warnings))
            return
        self.ui.labelResultsTitle.setText(f"Results for {self.ui.userName() or 'you'}")
        title = vehicleTitle(vehicle.manufacturer, vehicle.model_base, vehicle.year)
        self.ui.labelSelectedVehicle.setText(" · ".join(known(
            title, f"{vehicle.odometer:,.0f} mi", labelOf("type", vehicle.type), labelOf("condition", vehicle.condition),
            labelOf("fuel", vehicle.fuel), labelOf("transmission", vehicle.transmission))))   # fields left "Not sure" are skipped
        failed = {section for _, section in errors}
        self.budget = vehicle.budget_max_usd
        self.estimate = result.price.predicted_price if result.price is not None else None
        self.showPrice(result.price)
        self.showBudget(vehicle.budget_max_usd, result.price, self.notesFor(warnings, BUDGET))
        self.showTopMatches(result.top_matches, self.notesFor(warnings, TOP, None),
                            TOP_UNAVAILABLE if failed & {TOP, CATALOG} else TOP_EMPTY)
        self.showSimilarPrice(result.similar_price, result.price, self.notesFor(warnings, SIMILAR),
                              SIMILAR_UNAVAILABLE if failed & {SIMILAR, CATALOG} or result.price is None
                              else SIMILAR_EMPTY)
        self.ui.scrollAreaResults.verticalScrollBar().setValue(0)
        self.ui.goToPage(PAGE_RESULTS)
        self.ui.settleLayout()
        for widgets, cards in ((self.topCards, result.top_matches), (self.similarCards, result.similar_price)):
            for widget, card in zip(widgets, cards):
                widget.showImage(card)
        if errors:
            self.ui.showWarning("Some results are unavailable", self.bullets(errors))

    def bullets(self, messages):
        return "\n".join(f"• {text}" for text, _ in messages)

    def notesFor(self, warnings, *sections):
        return [text for text, section in warnings if section in sections]

    def showPrice(self, price):
        if price is None:
            self.ui.labelPredictedPrice.setText("N/A")
            self.ui.labelPriceRange.setText("")
            self.ui.labelPriceNote.setText("The price estimate is unavailable for this analysis.")
            return
        self.ui.labelPredictedPrice.setText(money(price.predicted_price))
        note = "Estimated asking price, learned from U.S. used-car listings of 2021 (not today's market price)."
        if price.price_low is not None and price.price_high is not None:
            self.ui.labelPriceRange.setText(f"8 in 10 similar listings: {money(price.price_low)} – {money(price.price_high)}")
            mae = appMae()
            note += (" The range is wider for expensive cars because their prices vary more."
                     + (f" Average error on unseen test cars: about {money(mae)}." if mae else ""))
        else:
            self.ui.labelPriceRange.setText("")
        self.ui.labelPriceNote.setText(note)

    def showBudget(self, budget, price, notes):
        """The budget, a verdict with the gap in dollars and what to do next. The over-budget warning of the
        Backend says the same as the verdict, so the page writes its own note instead of repeating it."""
        self.ui.labelBudgetValue.setText(money(budget))
        if price is None:
            verdict, state = "NOT AVAILABLE", ""
            note = " ".join(notes) or "There is no estimate to compare with your budget."
        elif budget >= price.predicted_price:
            verdict, state = "WITHIN BUDGET", "ok"
            note = f"You would have about {money(budget - price.predicted_price)} left over at the estimated price."
        else:
            verdict, state = f"OVER BY {money(price.predicted_price - budget)}", "over"
            note = "This car usually costs more than you plan to spend. The Top 5 below are cars within your budget."
        self.ui.labelBudgetVerdict.setText(verdict)
        self.ui.labelBudgetVerdict.setProperty("state", state)
        self.ui.labelBudgetNote.setText(note)
        self.ui.repolish(self.ui.labelBudgetVerdict)

    def detailsOf(self, widget):
        """(badge, title, price, rows) of the car a card shows, or None for a hidden card."""
        if widget.card is None:
            return None
        return carDetails(widget.card, widget.rank, widget.gap, self.budget, self.estimate)

    def showTopMatches(self, cards, notes, emptyText):
        self.ui.labelTopNote.setText(" ".join(([TOP_NOTE] if cards else []) + notes))
        for n, widget in enumerate(self.topCards):
            if n < len(cards):
                widget.show(cards[n], rank=n + 1)
            else:
                widget.hide()
        self.ui.labelTopEmpty.setText(emptyText)
        self.ui.widgetTopMatches.setVisible(len(cards) > 0)
        self.ui.labelTopEmpty.setVisible(len(cards) == 0)

    def showSimilarPrice(self, cards, price, notes, emptyText):
        self.ui.labelSimilarNote.setText(" ".join(([SIMILAR_NOTE] if cards else []) + notes))
        for n, widget in enumerate(self.similarCards):
            if n < len(cards):
                gap = priceGapPct(cards[n].price, price.predicted_price) if price is not None else None
                widget.show(cards[n], gap=gap)
            else:
                widget.hide()
        self.ui.labelSimilarEmpty.setText(emptyText)
        self.ui.widgetSimilarPrice.setVisible(len(cards) > 0)
        self.ui.labelSimilarEmpty.setVisible(len(cards) == 0)
