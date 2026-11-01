"""
16_backend_performance.py - ĐÁNH GIÁ HIỆU NĂNG BACKEND

Gửi nhiều yêu cầu giống như người dùng bấm "Phân tích và tìm xe" qua app_service.analyze():
  - Yêu cầu hợp lệ: lấy thông số của các xe thật trong tập test (data/splits/test_ids.csv)
    mà người dùng chọn được trên form (dòng xe có trong danh sách theo hãng, không chọn
    "unknown" ở ô bắt buộc); ngân sách = giá niêm yết x hệ số ngẫu nhiên 0,8-1,5.
  - Yêu cầu không hợp lệ: thiếu ô, sai kiểu, ngoài khoảng, dòng xe không thuộc hãng.
Đo thời gian từng bước (kiểm tra, dự đoán, gợi ý, xe cùng giá, ảnh, tổng), tỷ lệ lỗi, và
kiểm tra mô hình/catalog chỉ được nạp một lần.

Chạy: python scripts/16_backend_performance.py [số_yêu_cầu]   (mặc định 300)
Kết quả: reports/integration/backend_performance.csv          (thống kê theo bước)
         reports/integration/backend_performance_requests.csv (từng yêu cầu)
         reports/integration/backend_performance.json         (tóm tắt)
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

from backend.app_service import STAGES, AppService
from backend.schemas.vehicle_input import MODELS_BY_MAKE
from src import config
from src.prediction.predict import load_pipeline

OUT = config.REPORT_DIR / "integration"
FORM_COLUMNS = ["manufacturer", "model_base", "year", "type", "odometer", "condition", "fuel",
                "transmission", "drive", "cylinders", "paint_color", "title_status", "state"]
N_DEFAULT = 300


def valid_forms(n: int, rng: np.random.Generator) -> list[dict]:
    df = pd.read_pickle(config.PROCESSED_DIR / "vehicles_filled.pkl")
    test_ids = pd.read_csv(config.DATA_DIR / "splits" / "test_ids.csv")["id"]
    df = df[df["id"].isin(test_ids)]
    # Người dùng không chọn "unknown" ở các ô bắt buộc trên form
    df = df[(df[["type", "condition", "fuel", "transmission"]] != "unknown").all(axis=1)]
    # và chỉ chọn được những dòng xe có trong danh sách dòng xe theo hãng của form
    on_form = [m in MODELS_BY_MAKE.get(mk, ()) for mk, m in zip(df["manufacturer"], df["model_base"])]
    df = df[on_form]
    rows = df.sample(n=n, random_state=config.RANDOM_STATE)
    forms = []
    for _, r in rows.iterrows():
        f = {c: r[c] for c in FORM_COLUMNS}
        f["year"] = int(f["year"])
        f["odometer"] = float(f["odometer"])
        f["budget_max_usd"] = float(np.clip(round(r["price"] * rng.uniform(0.8, 1.5), -2), 1000, 150000))
        forms.append(f)
    return forms


def invalid_forms(base: dict) -> list[tuple[str, object]]:
    return [("thiếu hãng", {**base, "manufacturer": ""}),
            ("thiếu số miles", {**base, "odometer": None}),
            ("năm không phải số", {**base, "year": "abc"}),
            ("năm ngoài khoảng", {**base, "year": 1985}),
            ("số miles ngoài khoảng", {**base, "odometer": 999_999}),
            ("ngân sách ngoài khoảng", {**base, "budget_max_usd": 100}),
            ("giá trị không hợp lệ", {**base, "fuel": "nuclear"}),
            ("dòng xe không thuộc hãng", {**base, "model_base": "camry", "manufacturer": "ford"}),
            ("form rỗng", {}),
            ("không phải dict", None)]


def main(n: int):
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(config.RANDOM_STATE)
    forms = valid_forms(n, rng)

    load_pipeline.cache_clear()
    built = []
    from src.recommendation.recommend import Recommender
    def factory():
        built.append(1)
        return Recommender.from_pickle()
    app = AppService(recommender_factory=factory)

    t0 = time.perf_counter()
    warm_errors = app.warm_up()
    warm_ms = (time.perf_counter() - t0) * 1000
    print(f"Nạp mô hình + catalog + ảnh lúc mở ứng dụng: {warm_ms:,.0f} ms | lỗi: {warm_errors}")

    rows = []
    for i, f in enumerate(forms):
        r = app.analyze(f)
        rows.append({"loai": "hop_le", "mo_ta": f"{f['manufacturer']} {f['model_base']} {f['year']}",
                     "success": r.success, "so_loi": len(r.errors), "so_canh_bao": len(r.warnings),
                     "co_gia": r.price is not None, "so_top": len(r.top_matches),
                     "so_cung_gia": len(r.similar_price),
                     "top_trong_ngan_sach": all(c.price <= f["budget_max_usd"] for c in r.top_matches),
                     "trung_top_va_cung_gia": bool({c.id for c in r.top_matches} & {c.id for c in r.similar_price}),
                     "anh_mo_duoc": all(Path(c.image_path).is_file() for c in r.top_matches + r.similar_price),
                     "anh_thay_the": sum(app.images.is_placeholder(c.image_path) for c in r.top_matches + r.similar_price),
                     **{f"{s}_ms": app.last_timings[s] for s in STAGES}})
        if (i + 1) % 100 == 0:
            print(f"   {i + 1}/{len(forms)} yêu cầu hợp lệ", flush=True)
    for label, f in invalid_forms(forms[0]):
        r = app.analyze(f)
        rows.append({"loai": "khong_hop_le", "mo_ta": label, "success": r.success, "so_loi": len(r.errors),
                     "so_canh_bao": len(r.warnings), "co_gia": r.price is not None,
                     "so_top": len(r.top_matches), "so_cung_gia": len(r.similar_price),
                     **{f"{s}_ms": app.last_timings[s] for s in STAGES}})
    req = pd.DataFrame(rows)
    req.to_csv(OUT / "backend_performance_requests.csv", index=False, encoding="utf-8-sig")

    ok = req[req["loai"] == "hop_le"]
    bad = req[req["loai"] == "khong_hop_le"]
    stats = []
    for s in STAGES:
        v = ok[f"{s}_ms"].to_numpy()
        stats.append({"buoc": s, "so_yeu_cau": len(v), "trung_binh_ms": v.mean(), "trung_vi_ms": np.median(v),
                      "p95_ms": np.percentile(v, 95), "max_ms": v.max()})
    v = bad["total_ms"].to_numpy()
    stats.append({"buoc": "total (yêu cầu không hợp lệ)", "so_yeu_cau": len(v), "trung_binh_ms": v.mean(),
                  "trung_vi_ms": np.median(v), "p95_ms": np.percentile(v, 95), "max_ms": v.max()})
    st = pd.DataFrame(stats).round(2)
    st.to_csv(OUT / "backend_performance.csv", index=False, encoding="utf-8-sig")

    cache = load_pipeline.cache_info()
    summary = {
        "so_yeu_cau_hop_le": int(len(ok)), "so_yeu_cau_khong_hop_le": int(len(bad)),
        "ty_le_loi_yeu_cau_hop_le_pct": round(float((~ok["success"]).mean() * 100), 2),
        "ty_le_tu_choi_dung_yeu_cau_khong_hop_le_pct": round(float((~bad["success"] & (bad["so_loi"] > 0)).mean() * 100), 2),
        "ty_le_co_du_5_xe_pct": round(float((ok["so_top"] == 5).mean() * 100), 2),
        "ty_le_co_du_6_xe_cung_gia_pct": round(float((ok["so_cung_gia"] == 6).mean() * 100), 2),
        "top5_luon_trong_ngan_sach": bool(ok["top_trong_ngan_sach"].all()),
        "top5_va_cung_gia_khong_trung": bool(not ok["trung_top_va_cung_gia"].any()),
        "moi_anh_deu_mo_duoc": bool(ok["anh_mo_duoc"].all()),
        "ty_le_the_xe_dung_anh_thay_the_pct": round(float(ok["anh_thay_the"].sum() /
                                                          (ok["so_top"] + ok["so_cung_gia"]).sum() * 100), 2),
        "nap_mo_hinh_luc_mo_ung_dung_ms": round(warm_ms, 1),
        "so_lan_nap_mo_hinh": cache.misses, "so_lan_dung_lai_mo_hinh": cache.hits,
        "so_lan_nap_catalog": len(built),
        "thoi_gian_tong_trung_binh_ms": round(float(ok["total_ms"].mean()), 2),
        "thoi_gian_tong_p95_ms": round(float(np.percentile(ok["total_ms"], 95)), 2),
    }
    (OUT / "backend_performance.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + st.to_string(index=False))
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else N_DEFAULT)
