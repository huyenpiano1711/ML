"""
vin_mapping.py - Quy đổi thông tin giải mã VIN (NHTSA) về đúng bộ giá trị của dataset Craigslist.

Bảng quy đổi được kiểm tra bằng cách so với các tin vừa có VIN vừa có thông tin người bán tự khai
(xem reports/vin_agreement.csv sau khi chạy 08_fill_specs.py).
"""
import numpy as np
import pandas as pd

# NHTSA DriveType -> drive. '4x2' (2 cầu) KHÔNG đủ để biết cầu trước hay cầu sau
# (trong dữ liệu: 10.812 tin fwd, 4.564 tin rwd) -> để giá trị đặc biệt '2wd' rồi xử lý theo dòng xe.
DRIVE_MAP = {
    "4WD/4-Wheel Drive/4x4": "4wd", "AWD/All-Wheel Drive": "4wd",   # Craigslist gộp AWD vào 4wd
    "FWD/Front-Wheel Drive": "fwd", "RWD/Rear-Wheel Drive": "rwd",
    "4x2": "2wd", "6x4": "rwd", "6x2": "rwd",
}

TYPE_MAP = {
    "Sport Utility Vehicle [SUV]/Multipurpose Vehicle [MPV]": "suv",
    "Crossover Utility Vehicle [CUV]": "suv",
    "Sedan/Saloon": "sedan", "Pickup": "pickup", "Hatchback/Liftback/Notchback": "hatchback",
    "Coupe": "coupe", "Minivan": "mini-van", "Convertible/Cabriolet": "convertible",
    "Cargo Van": "van", "Van": "van", "Wagon": "wagon", "Roadster": "convertible",
}

VALID_CYL = {3, 4, 5, 6, 8, 10, 12}


def map_drive(s):
    return s.map(DRIVE_MAP)


def map_type(s):
    out = s.map(TYPE_MAP)
    out[s.str.startswith("Incomplete", na=False)] = "truck"       # xe tải sát-xi (chassis cab)
    return out


def map_cylinders(s):
    n = pd.to_numeric(s, errors="coerce")
    return n.map(lambda x: f"{int(x)} cylinders" if x in VALID_CYL else np.nan)


def map_fuel(primary, electrification):
    p, e = primary.fillna(""), electrification.fillna("")
    out = pd.Series(np.nan, index=p.index, dtype="object")
    out[p.isin(["Gasoline", "Flexible Fuel Vehicle (FFV)", "Ethanol (E85)"])] = "gas"
    out[p == "Diesel"] = "diesel"
    out[p.isin(["Compressed Natural Gas (CNG)", "Fuel Cell",
                "Liquefied Petroleum Gas (propane or LPG)"])] = "other"
    out[e.str.contains("HEV", regex=False) & ~e.str.contains("BEV", regex=False)] = "hybrid"
    out[(p == "Electric") | e.str.contains("BEV", regex=False)] = "electric"
    return out


def map_transmission(s):
    auto = ["Automatic", "Continuously Variable Transmission (CVT)", "Automated Manual Transmission (AMT)",
            "Dual-Clutch Transmission (DCT)", "Electronic Continuously Variable (e-CVT)"]
    out = pd.Series(np.nan, index=s.index, dtype="object")
    out[s.isin(auto)] = "automatic"
    out[s == "Manual/Standard"] = "manual"
    return out


def to_number(s):
    return pd.to_numeric(s, errors="coerce")
