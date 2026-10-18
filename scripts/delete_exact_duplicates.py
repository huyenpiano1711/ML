#!/usr/bin/env python3
"""
AutoWiseAI - Vehicle Image Exact Duplicates Handler
===================================================

Sửa đổi quy trình xử lý ảnh trùng lặp:
Thay vì xóa thô sơ khiến gãy tham chiếu CSV, công cụ này thực hiện hợp nhất (consolidate)
1,867 ảnh trùng tuyệt đối (SHA-256) vào thư mục ảnh sạch `assets/car_images_unique/`,
đồng thời tạo bản sao CSV mới chuẩn hóa toàn bộ đường dẫn ảnh và bảo toàn dữ liệu gốc.
"""

import sys
import argparse
from pathlib import Path

# Thêm scripts/ vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from consolidate_exact_duplicates import run_consolidation


def main():
    parser = argparse.ArgumentParser(
        description="AutoWiseAI - Safe Exact Duplicate Image Consolidation"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Thực hiện hợp nhất 1,867 file trùng vào assets/car_images_unique/ và tạo CSV mới"
    )
    args = parser.parse_args()

    if not args.apply:
        print("=" * 70)
        print(" 🚘 AutoWiseAI - Exact Duplicate Consolidation (DRY RUN MODE)")
        print("=" * 70)
        print("[!] Chế độ mặc định: Để chạy hợp nhất và tạo thư mục ảnh/CSV sạch, vui lòng dùng:")
        print("    python scripts/delete_exact_duplicates.py --apply")
        print("    (Toàn bộ ảnh gốc và CSV gốc sẽ được bảo toàn nguyên vẹn 100%)")
        print("=" * 70)
        return

    run_consolidation()


if __name__ == "__main__":
    main()
