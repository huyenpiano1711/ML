"""
15_image_service_check.py - D05: KIỂM TRA image_service TRÊN DỮ LIỆU THẬT

  1. Kiểm tra toàn bộ ảnh trong assets/car_images_unique: bao nhiêu ảnh mở được, bao nhiêu lỗi.
  2. Độ phủ ảnh của catalog (recommendation_catalog.pkl): bao nhiêu xe có ảnh minh họa,
     lấy từ đâu (catalog / tìm lại theo hãng-dòng-năm) và bao nhiêu xe phải dùng ảnh thay thế.
     Chạy hai trường hợp: catalog có image_path (C01 build khi có thư mục ảnh) và catalog
     không có image_path (C01 build khi máy chưa có ảnh) để kiểm tra bước tìm lại.
  3. Thời gian xử lý một thẻ xe: lần đầu (phải đọc ảnh) và các lần sau (dùng bộ đệm).

Chạy: python scripts/15_image_service_check.py
Kết quả: reports/integration/image_service_check.json, image_service_check.csv
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

from backend.schemas.result_schema import CarCard
from backend.services.image_service import ImageService
from src import config

CATALOG_PKL = config.PROCESSED_DIR / "recommendation_catalog.pkl"
OUT = config.REPORT_DIR / "integration"
SAMPLE = 2000


def coverage(svc: ImageService, cat: pd.DataFrame, label: str) -> dict:
    """Áp image_service cho mọi xe (mỗi tổ hợp hãng-dòng-năm-ảnh chỉ tính một lần)."""
    keys = ["manufacturer", "model_base", "year", "image_path"]
    combos = cat[keys].astype(object).where(cat[keys].notna(), None).drop_duplicates()
    res = [svc.resolve_vehicle(r.manufacturer, r.model_base, r.year, r.image_path)
           for r in combos.itertuples(index=False)]
    combos["source"] = [r.source for r in res]
    combos["reason"] = [r.reason for r in res]
    rows = cat[keys].astype(object).where(cat[keys].notna(), None).merge(combos, on=keys, how="left")
    n = len(rows)
    src = rows["source"].value_counts()
    return {"truong_hop": label, "so_xe": n,
            **{f"pct_{k}": round(src.get(k, 0) / n * 100, 2) for k in
               ["catalog", "lookup_exact", "lookup_nearest_year", "placeholder"]},
            "pct_co_anh_minh_hoa": round((rows["source"] != "placeholder").mean() * 100, 2),
            "ly_do_anh_catalog_khong_dung": {k: int(v) for k, v in rows["reason"].value_counts().items()}}


def latency(svc: ImageService, cat: pd.DataFrame) -> dict:
    rng = np.random.default_rng(config.RANDOM_STATE)
    sample = cat.iloc[rng.choice(len(cat), size=min(SAMPLE, len(cat)), replace=False)]
    cards = [CarCard.from_row(r) for _, r in sample.iterrows()]
    svc.clear_cache()
    out = {}
    for name in ("lan_dau_ms", "lan_sau_ms"):
        t = []
        for c in cards:
            t0 = time.perf_counter()
            svc.resolve_card(c)
            t.append((time.perf_counter() - t0) * 1000)
        out[name] = {"trung_binh": round(float(np.mean(t)), 3), "p95": round(float(np.percentile(t, 95)), 3),
                     "max": round(float(np.max(t)), 3)}
    t0 = time.perf_counter()
    svc.with_images(cards[:11])                       # 1 lần hiển thị: Top 5 + 6 xe cùng mức giá
    out["mot_trang_ket_qua_11_xe_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    out["so_the_do"] = len(cards)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    svc = ImageService()
    report = {"thu_muc_anh": str(svc.image_dir.relative_to(svc.project_dir)),
              "anh_thay_the": str(svc.placeholder.relative_to(svc.project_dir))}

    # 1. Toàn bộ ảnh
    files = sorted(p for p in svc.image_dir.iterdir() if p.is_file()) if svc.image_dir.is_dir() else []
    t0 = time.perf_counter()
    reasons = pd.Series([svc.check_file(p.resolve()) for p in files], dtype="object")
    report["kiem_tra_anh"] = {"so_file": len(files), "ket_qua": {k: int(v) for k, v in reasons.value_counts().items()},
                              "thoi_gian_s": round(time.perf_counter() - t0, 1)}
    print("1.", report["kiem_tra_anh"])

    # 2. Độ phủ
    cat = pd.read_pickle(CATALOG_PKL)
    rows = [coverage(svc, cat, "catalog có image_path"),
            coverage(svc, cat.assign(image_path=None), "catalog không có image_path")]
    report["do_phu"] = rows
    for r in rows:
        print("2.", r)
    pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in rows]) \
        .to_csv(OUT / "image_service_check.csv", index=False, encoding="utf-8-sig")

    # 3. Thời gian
    report["thoi_gian"] = latency(svc, cat)
    print("3.", report["thoi_gian"])

    (OUT / "image_service_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n==> Đã lưu {OUT / 'image_service_check.json'}")


if __name__ == "__main__":
    main()
