"""
run_all.py - Chạy lần lượt toàn bộ quy trình EDA + tiền xử lý + kiểm tra.
(Có thể chạy từng file riêng; file này chỉ để tiện.)
Tổng thời gian trên laptop thường: ~5-10 phút (bước 02 lâu nhất).
"""
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = ["01_eda_raw.py", "02_extract_text_features.py", "03_preprocess.py",
         "04_eda_clean.py", "05_validate.py"]

for step in STEPS:
    print("\n" + "=" * 80 + f"\n>>> {step}\n" + "=" * 80)
    t0 = time.time()
    try:
        runpy.run_path(str(ROOT / step), run_name="__main__")
    except SystemExit as e:          # 05_validate trả mã 1 nếu có lỗi
        if e.code:
            sys.exit(e.code)
    print(f"<<< {step} xong sau {time.time() - t0:.0f}s")
