"""
17_build_image_aliases.py - Tạo assets/image_aliases.csv (alias,file) từ báo cáo khử trùng ảnh.

Bước khử trùng (scripts/consolidate_exact_duplicates.py) chỉ giữ MỘT file cho mỗi nhóm ảnh trùng
tuyệt đối, vd giữ lexus_rx_1999.jpg và bỏ lexus_rx300_1999.jpg. image_service (D05) tìm ảnh theo
tên <hãng>_<dòng>_<năm>, nên các tên bị bỏ cần bảng này để vẫn tìm được ảnh.

    python scripts/17_build_image_aliases.py [đường_dẫn/exact_duplicates.csv]
    (mặc định: reports/image_deduplication/exact_duplicates.csv)
"""
import sys
from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROJECT_DIR / "reports" / "image_deduplication" / "exact_duplicates.csv"
IMAGE_DIR = PROJECT_DIR / "assets" / "car_images_unique"
OUT = PROJECT_DIR / "assets" / "image_aliases.csv"


def main():
    report = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPORT
    dup = pd.read_csv(report, encoding="utf-8-sig")
    dup["alias"] = dup["image_path"].map(lambda p: Path(p).name)
    dup["file"] = dup["preferred_image"].map(lambda p: Path(p).name)
    aliases = dup.loc[dup["alias"] != dup["file"], ["alias", "file"]].drop_duplicates()
    if IMAGE_DIR.is_dir():                       # chỉ giữ alias trỏ tới file còn trong car_images_unique
        kept = {p.name for p in IMAGE_DIR.iterdir()}
        aliases = aliases[aliases["file"].isin(kept) & ~aliases["alias"].isin(kept)]
    aliases.sort_values("alias").to_csv(OUT, index=False)
    print(f"Đã ghi {OUT} ({len(aliases)} tên ảnh cũ)")


if __name__ == "__main__":
    main()
