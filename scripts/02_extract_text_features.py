"""
02_extract_text_features.py - TRÍCH ĐẶC TRƯNG TỪ CỘT MÔ TẢ (description)

Cột description chiếm phần lớn dung lượng file nên ta đọc theo từng khối 50.000
dòng (chunk), chỉ lấy 2 cột id + description, rồi biến văn bản thành các cờ 0/1
bằng biểu thức chính quy (regex). Không bao giờ giữ toàn bộ văn bản trong RAM.

Kết quả: data/interim/desc_features.csv  (id + các đặc trưng văn bản)
         reports/eda_raw/text_keyword_rates.csv

Chạy: Run '02_extract_text_features' (~2-4 phút).
"""
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd

from src import config

# Mỗi cờ = 1 nếu mô tả khớp biểu thức. Đặt tên theo ý nghĩa với người mua xe.
KEYWORDS = {
    "kw_one_owner":     r"\b(?:one|1|single)[\s-]*owner\b",
    "kw_clean_history": r"clean\s*(?:carfax|autocheck|history)|no\s+accidents?|accident[\s-]*free",
    "kw_warranty":      r"warrant(?:y|ies)",
    "kw_financing":     r"financ|down\s*payment|bad\s*credit|no\s*credit|credit\s*approval",
    "kw_needs_work":    r"mechanic'?s?\s*special|needs?\s+(?:some\s+)?(?:work|repair|engine|transmission)"
                        r"|not\s+running|does\s*n[o']?t\s+run|won'?t\s+start|parts\s+car",
    # (Đã kiểm tra: KHÔNG dùng 'as is' vì đó chủ yếu là câu miễn trừ trách nhiệm của đại lý
    #  - tin chỉ có 'as is' có giá trung vị 18.950 USD, cao hơn cả tin bình thường.)
    "kw_new_tires":     r"new\s+tires",
    "kw_leather":       r"leather",
    "kw_sunroof":       r"sun\s*roof|moon\s*roof|panoramic",
    "kw_navigation":    r"navigation|\bnav\b|\bgps\b",
    "kw_backup_camera": r"back[\s-]*up\s*camera|rear[\s-]*view\s*camera",
    "kw_lifted":        r"\blifted\b|lift\s*kit",
    "kw_low_miles":     r"low\s+miles|low\s+mileage",
}

CHUNK = 50_000


# Lưu từng khối -> chạy lại được nếu bị ngắt giữa chừng. Tên thư mục chứa mã băm của bộ
# từ khóa: sửa regex thì tự động tính lại từ đầu, không dùng nhầm kết quả cũ.
_KW_HASH = hashlib.md5(repr(sorted(KEYWORDS.items())).encode()).hexdigest()[:8]
PARTS_DIR = config.INTERIM_DIR / f"desc_parts_{_KW_HASH}"


def featurize(chunk):
    text = chunk["description"].fillna("").str.lower()
    feat = pd.DataFrame({"id": chunk["id"].values})
    feat["desc_missing"] = chunk["description"].isna().astype("int8").values
    feat["desc_len"] = text.str.len().astype("int32").values           # số ký tự
    feat["desc_words"] = text.str.count(r"\S+").astype("int32").values  # số từ
    for name, pattern in KEYWORDS.items():
        feat[name] = text.str.contains(pattern, regex=True).astype("int8").values
    return feat


def main(time_budget=None):
    """time_budget (giây): dừng sớm nếu vượt thời gian; lần chạy sau sẽ tiếp tục
    từ khối chưa làm. Mặc định None = chạy hết một lượt."""
    if not config.RAW_CSV.exists():
        raise FileNotFoundError(config.RAW_CSV)
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    t0, n = time.time(), 0
    reader = pd.read_csv(config.RAW_CSV, usecols=["id", "description"],
                         dtype={"id": "int64", "description": "string"}, chunksize=CHUNK)
    for i, chunk in enumerate(reader):
        n += len(chunk)
        part = PARTS_DIR / f"part_{i:03d}.pkl"
        if part.exists():
            continue                      # khối này đã xử lý ở lần chạy trước
        if time_budget and time.time() - t0 > time_budget:
            print("   [tạm dừng] hết thời gian cho phép -> chạy lại file để làm tiếp")
            return
        featurize(chunk).to_pickle(part)
        print(f"   khối {i}: đã xử lý đến dòng {n:,} ({time.time() - t0:.0f}s)", flush=True)
    parts = [pd.read_pickle(p) for p in sorted(PARTS_DIR.glob("part_*.pkl"))]
    out = pd.concat(parts, ignore_index=True)
    assert len(out) == n, f"Số dòng ghép ({len(out):,}) khác số dòng file gốc ({n:,})"
    # Kiểm tra chéo: số dòng phải khớp với file gốc và id không trùng
    assert out["id"].is_unique, "id bị trùng trong desc_features!"
    out.to_csv(config.DESC_FEATURES_CSV, index=False)

    rates = out.drop(columns=["id", "desc_len", "desc_words"]).mean().mul(100).round(2)
    rates.rename("pct_rows").to_csv(config.EDA_RAW_DIR / "text_keyword_rates.csv", encoding="utf-8-sig")
    print("\nTỷ lệ tin đăng chứa từ khóa (%):")
    print(rates.to_string())
    print(f"\nĐộ dài mô tả (ký tự): trung vị {out['desc_len'].median():.0f}, "
          f"p95 {out['desc_len'].quantile(.95):.0f}")
    print(f"==> Đã lưu {len(out):,} dòng vào {config.DESC_FEATURES_CSV}")


if __name__ == "__main__":
    import os
    budget = os.environ.get("AUTOWISE_TIME_BUDGET")
    main(float(budget) if budget else None)
