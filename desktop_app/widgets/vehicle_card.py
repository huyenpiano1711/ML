"""
vehicle_card.py - One car card of Screen 3 (pageResults).
The cards are designed in the .ui (frameTopCar1, labelTopCar1Title, ...), so VehicleCard creates no
widget: it fills the existing ones. PyQt is only imported where a photo is loaded.
"""
import re


def money(x):
    return f"${x:,.0f}"


def labelOf(field_name, value):
    """Display text for a value from feature_schema.json (the value sent to the model stays unchanged)."""
    if value is None:
        return ""
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
    return f"{manufacturer.title()} {modelLabel(model)} {year}"


def isPlaceholder(image_path):
    """True when image_path is the placeholder of D05 (assets/placeholder_car.png) or empty.
    That image is light grey with a Vietnamese caption, so Screen 3 shows its own dark tile instead."""
    if not image_path:
        return True
    from pathlib import Path
    from backend.services.image_service import PLACEHOLDER_PATH
    try:
        return Path(image_path).resolve() == PLACEHOLDER_PATH.resolve()
    except OSError:
        return False


def bodyTypeText(card):
    """Text of the dark tile when there is no photo: the body type, e.g. SEDAN."""
    return (card.type if card.type and card.type != "unknown" else "car").upper()


def setCardImage(label, card):
    """Photo from card.image_path (D05). No real photo (placeholder or unreadable file) -> the body type
    as text on the dark tile designed in the .ui (role carImage)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap
    pix = QPixmap() if isPlaceholder(card.image_path) else QPixmap(card.image_path)
    if pix.isNull():
        label.setPixmap(QPixmap())
        label.setText(bodyTypeText(card))
        return
    label.setPixmap(pix.scaled(label.width(), label.maximumHeight(),
                               Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation))


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

    def show(self, card, rank=None, gap=None):
        self.frame.setVisible(True)
        self.labelTitle.setText(vehicleTitle(card.manufacturer, card.model_base, card.year))
        self.labelDetail.setText(f"{card.odometer:,.0f} mi · {labelOf('condition', card.condition)}")
        self.labelPrice.setText(money(card.price))
        if self.labelRank is not None:
            self.labelRank.setText(f"#{rank}")
        if self.labelMatch is not None:
            self.labelMatch.setText(f"{card.score * 100:.0f}% MATCH" if card.score is not None else "")
        if self.labelSpecs is not None:
            self.labelSpecs.setText(f"{labelOf('fuel', card.fuel)} · {labelOf('transmission', card.transmission)}")
        if self.labelGap is not None:
            self.labelGap.setText(f"{gap:+.1f}% VS. ESTIMATE" if gap is not None else "")

    def showImage(self, card):
        """Separate from show(): the photo is scaled to the label, so Screen 3 must be laid out first."""
        self.setImage(self.labelImage, card)

    def hide(self):
        self.frame.setVisible(False)
