"""
vehicle_card.py - One car card of Screen 3 (pageResults).
The cards are designed in the .ui (frameTopCar1, labelTopCar1Title, ...), so VehicleCard creates no
widget: it fills the existing ones. PyQt is only imported where a photo is loaded.
"""
import re


def money(x):
    return f"${x:,.0f}"


# Makes whose usual spelling is not "first letter upper case" (gmc -> GMC, not Gmc)
MAKE_LABELS = {"gmc": "GMC", "bmw": "BMW", "ram": "RAM", "mini": "MINI", "fiat": "FIAT",
               "mercedes-benz": "Mercedes-Benz", "alfa-romeo": "Alfa Romeo", "land rover": "Land Rover"}


def makeLabel(manufacturer):
    """Display text of a make: GMC, BMW, Mercedes-Benz, Land Rover, Ford..."""
    make = str(manufacturer or "").strip().lower()
    return MAKE_LABELS.get(make) or " ".join(word.capitalize() for word in make.split())


def known(*parts):
    """Card details without the values the listing did not give ("Unknown" or empty)."""
    return [part for part in parts if part and part != "Unknown"]


def labelOf(field_name, value):
    """Display text for a value from feature_schema.json (the value sent to the model stays unchanged)."""
    if value is None:
        return ""
    if field_name == "manufacturer":
        return makeLabel(value)
    if value == "unknown":
        return "Unknown"
    special = {"suv": "SUV", "4wd": "4WD", "fwd": "FWD", "rwd": "RWD", "mini-van": "Minivan",
               "gas": "Gasoline", "like new": "Like new"}
    if value in special:
        return special[value]
    if field_name == "state":
        return value.upper()
    return str(value)[:1].upper() + str(value)[1:]


# Models with their own spelling, which the rule of modelLabel() cannot produce
MODEL_LABELS = {"4runner": "4Runner", "300series": "300 Series",
                "mazda2": "Mazda2", "mazda3": "Mazda3", "mazda5": "Mazda5", "mazda6": "Mazda6",
                "santa fe": "Santa Fe", "town car": "Town Car", "grand am": "Grand Am",
                "fit": "Fit", "rio": "Rio", "ion": "Ion", "sky": "Sky", "eos": "Eos", "vue": "Vue",
                "cmax": "C-Max", "fpace": "F-Pace", "stype": "S-Type", "xtype": "X-Type", "eseries": "E-Series",
                "egolf": "e-Golf", "lacrosse": "LaCrosse", "lesabre": "LeSabre", "deville": "DeVille",
                "ecosport": "EcoSport", "promaster": "ProMaster", "granturismo": "GranTurismo",
                "eurovan": "EuroVan", "chr": "C-HR", "crv": "CR-V", "hrv": "HR-V", "crz": "CR-Z", "frs": "FR-S",
                "i3": "i3", "xa": "xA", "xb": "xB", "xd": "xD", "tc": "tC", "fortwo": "fortwo"}


def wordLabel(word):
    return word.upper() if len(word) <= 3 or any(c.isdigit() for c in word) else word.capitalize()


def modelLabel(model):
    """Display text of a model, word by word (a space or a hyphen ends a word): upper case if the word
    is short or has a digit (F250SD, MDX, 3 Series, CLA-Class), otherwise a capital first letter (Super Duty)."""
    return MODEL_LABELS.get(model) or re.sub(r"[^ -]+", lambda word: wordLabel(word[0]), model)


def vehicleTitle(manufacturer, model, year):
    return f"{makeLabel(manufacturer)} {modelLabel(model)} {year}"


def isPlaceholder(image_path):
    """True when image_path is the placeholder of D05 (assets/placeholder_car.png) or empty: that image is
    light grey with a Vietnamese caption, so the card shows the dark tile of the .ui instead."""
    if not image_path:
        return True
    from pathlib import Path
    from backend.services.image_service import PLACEHOLDER_PATH
    try:
        return Path(image_path).resolve() == PLACEHOLDER_PATH.resolve()
    except OSError:
        return False


def setCardImage(label, card):
    """Photo from card.image_path (D05); placeholder or unreadable file -> the body type as text."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap
    pix = QPixmap() if isPlaceholder(card.image_path) else QPixmap(card.image_path)
    if pix.isNull():
        label.setPixmap(QPixmap())
        label.setText((card.type if card.type and card.type != "unknown" else "car").upper())
        return
    width, height = label.width(), label.maximumHeight()
    pix = pix.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                     Qt.TransformationMode.SmoothTransformation)
    # cut the middle to exactly the label's size: a wider photo must not make its card wider than the others
    label.setPixmap(pix.copy((pix.width() - width) // 2, (pix.height() - height) // 2, width, height))


NOT_LISTED = "Not listed"
WARNING = "Warning"                  # row of carDetails() shown as a red box by the details window
LOW_PRICE_RATIO = 0.7          # asking price under 70% of what the model estimates for that listing -> warn
# Title status of a listing, in plain words (feature_schema.json: title_status)
TITLE_TEXT = {"clean": "Clean",
              "rebuilt": "Rebuilt - repaired after major damage",
              "salvage": "Salvage - badly damaged, written off by insurance",
              "lien": "Lien - a loan is still owed on the car",
              "missing": "Missing - the seller has no title paper",
              "parts only": "Parts only - sold for parts"}


def titleWarning(card):
    """'Rebuilt title', 'Salvage title'... for a card; '' when the title is clean or not listed."""
    status = getattr(card, "title_status", None)
    if status in (None, "", "clean", "unknown"):
        return ""
    return f"{labelOf('title_status', status)} title"


def isLowPrice(card):
    """True when the asking price is far below what the price model estimates for this listing."""
    fair = getattr(card, "fair_price", None)
    return fair is not None and fair > 0 and card.price < LOW_PRICE_RATIO * fair


def carDetails(card, rank=None, gap=None, budget=None, estimate=None):
    """Everything known about one recommended car, for the details window opened by a click on its card.
    Returns (badge, title, price, rows) with rows = [(field, value), ...]; no PyQt here."""
    def listed(field_name, value):
        text = labelOf(field_name, value)
        return text if text and text != "Unknown" else NOT_LISTED

    if rank is not None:
        badge = f"#{rank} BEST MATCH" + (f" · {card.score * 100:.0f}% MATCH" if card.score is not None else "")
    elif gap is not None:
        badge = f"SAME PRICE RANGE · {gap:+.1f}% VS. ESTIMATE"
    else:
        badge = "RECOMMENDED CAR"
    rows = [("Make", makeLabel(card.manufacturer)),
            ("Model", modelLabel(card.model_base)),
            ("Year", str(card.year)),
            ("Mileage", f"{card.odometer:,.0f} mi"),
            ("Body type", listed("type", card.type)),
            ("Condition", listed("condition", card.condition)),
            ("Fuel", listed("fuel", card.fuel)),
            ("Transmission", listed("transmission", card.transmission)),
            ("Title status", TITLE_TEXT.get(getattr(card, "title_status", None) or "", NOT_LISTED)),
            ("Listed in", labelOf("state", card.state) + " (U.S. state)" if getattr(card, "state", None)
             and card.state != "unknown" else NOT_LISTED)]
    fair = getattr(card, "fair_price", None)
    if fair is not None:
        rows.append(("Usual price for this car", f"About {money(fair)}"))
    if isLowPrice(card):
        rows.insert(0, (WARNING, f"The asking price is {(1 - card.price / fair) * 100:.0f}% below the usual price "
                                 f"of such a car ({money(fair)}, AutoWise estimate for its year, mileage and title). "
                                 "Check the car's history and condition before buying."))
    elif titleWarning(card):
        rows.insert(0, (WARNING, f"{labelOf('title_status', card.title_status)} title: this car does not have a "
                                 "clean title, so it usually sells for less. Check its repair history before buying."))
    if card.score is not None:
        rows.append(("Match with your car", f"{card.score * 100:.0f}%"))
    if estimate is not None:
        diff = card.price - estimate
        side = "below" if diff < 0 else "above"
        rows.append(("Vs. the car you entered", f"{money(abs(diff))} {side} its estimate of {money(estimate)}"
                     if round(diff) else f"Same as its estimate of {money(estimate)}"))
    if budget is not None:
        diff = budget - card.price
        rows.append(("Vs. your budget", f"{money(diff)} under your budget" if diff >= 0
                     else f"{money(-diff)} over your budget"))
    rows.append(("Listing ID", str(card.id)))
    return badge, vehicleTitle(card.manufacturer, card.model_base, card.year), money(card.price), rows


class VehicleCard:
    def __init__(self, ui, prefix, n, setImage=setCardImage):
        self.setImage = setImage
        self.frame = getattr(ui, f"frame{prefix}{n}")
        self.labelImage = getattr(ui, f"label{prefix}{n}Image")
        self.labelTitle = getattr(ui, f"label{prefix}{n}Title")
        self.labelDetail = getattr(ui, f"label{prefix}{n}Detail")
        self.labelPrice = getattr(ui, f"label{prefix}{n}Price")
        # Top 5 cards only
        self.labelRank = getattr(ui, f"label{prefix}{n}Rank", None)
        self.labelMatch = getattr(ui, f"label{prefix}{n}Match", None)
        self.labelSpecs = getattr(ui, f"label{prefix}{n}Specs", None)
        # same-price cards only
        self.labelGap = getattr(ui, f"label{prefix}{n}Gap", None)
        # what the card shows now, for the details window (None = hidden card)
        self.card, self.rank, self.gap = None, None, None

    def show(self, card, rank=None, gap=None):
        self.card, self.rank, self.gap = card, rank, gap
        self.frame.setVisible(True)
        self.labelTitle.setText(vehicleTitle(card.manufacturer, card.model_base, card.year))
        self.labelDetail.setText(" · ".join(known(f"{card.odometer:,.0f} mi", labelOf("condition", card.condition),
                                                  titleWarning(card))))
        self.labelPrice.setText(money(card.price))
        if self.labelRank is not None:
            self.labelRank.setText(f"#{rank}")
        if self.labelMatch is not None:
            match = f"{card.score * 100:.0f}% MATCH" if card.score is not None else ""
            self.labelMatch.setText(" · ".join(known(match, "LOW PRICE" if isLowPrice(card) else "")))
        if self.labelSpecs is not None:
            self.labelSpecs.setText(" · ".join(known(labelOf("fuel", card.fuel), labelOf("transmission", card.transmission))))
        if self.labelGap is not None:
            text = f"{gap:+.1f}% VS. ESTIMATE" if gap is not None else ""
            self.labelGap.setText(" · ".join(known(text, "LOW PRICE" if isLowPrice(card) else "")))

    def showImage(self, card):
        """Separate from show(): the photo is scaled to the label, so Screen 3 must be laid out first."""
        self.setImage(self.labelImage, card)

    def hide(self):
        self.card, self.rank, self.gap = None, None, None
        self.frame.setVisible(False)
