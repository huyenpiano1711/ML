"""
10_image_audit.py - KIỂM TOÁN BỘ ẢNH XE ĐÃ CRAWL (phục vụ báo cáo, không sửa/xóa ảnh nào)

Đọc bộ ảnh nhóm crawl từ Wikimedia Commons (assets/car_images), tính:
  - SHA-256 của từng file  -> nhóm file TRÙNG TUYỆT ĐỐI (cùng một ảnh, khác tên)
  - pHash (perceptual hash) -> cặp ảnh GẦN GIỐNG (khoảng cách Hamming <= 4 / <= 8)
  - kích thước, dung lượng, hãng + dòng xe + năm lấy từ tên file
Kết quả: reports/image_audit/ (inventory.csv, summary.json, 3 hình minh họa cho báo cáo)

Chạy: python 10_image_audit.py   (chạy lại được: ảnh đã tính thì bỏ qua, lưu tạm theo khối)
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # thư mục gốc repo
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
from PIL import Image

from src import config
from src import plot_utils as pu

IMG_DIR = config.PROJECT_DIR / "assets" / "car_images"
UNIQUE_DIR = config.PROJECT_DIR / "assets" / "car_images_unique"
OUT = config.REPORT_DIR / "image_audit"
PARTS = OUT / "_parts"
CHUNK = 500


def parse_key(stem):
    """'land_rover_range_rover_sport_2015' -> ('land_rover_range_rover_sport', 2015)"""
    head, _, year = stem.rpartition("_")
    return head, int(year) if year.isdigit() else None


def inspect(path):
    import imagehash
    b = path.read_bytes()
    with Image.open(path) as im:
        w, h = im.size
        ph = str(imagehash.phash(im))
    mm, yr = parse_key(path.stem)
    return {"file": path.name, "make_model_key": mm, "year": yr, "sha256": hashlib.sha256(b).hexdigest(),
            "phash": ph, "width": w, "height": h, "bytes": len(b)}


def build_inventory(time_budget=None):
    PARTS.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in IMG_DIR.iterdir() if p.suffix.lower() == ".jpg")
    t0 = time.time()
    for i in range(0, len(files), CHUNK):
        part = PARTS / f"part_{i // CHUNK:03d}.csv"
        if part.exists():
            continue
        if time_budget and time.time() - t0 > time_budget:
            print("   [tạm dừng] hết thời gian -> chạy lại để làm tiếp")
            return None
        pd.DataFrame([inspect(p) for p in files[i:i + CHUNK]]).to_csv(part, index=False)
        print(f"   đã kiểm {min(i + CHUNK, len(files)):,}/{len(files):,} ảnh ({time.time() - t0:.0f}s)", flush=True)
    inv = pd.concat([pd.read_csv(p) for p in sorted(PARTS.glob("part_*.csv"))], ignore_index=True)
    assert len(inv) == len(files) and inv["file"].is_unique
    return inv


def near_duplicates(phashes, max_dist=8):
    """So từng cặp pHash 64 bit (vector hóa bằng numpy), trả về các cặp có khoảng cách <= max_dist."""
    h = np.array([int(x, 16) for x in phashes], dtype=np.uint64)
    pairs = []
    for i in range(len(h) - 1):
        x = np.bitwise_xor(h[i], h[i + 1:])
        d = np.unpackbits(x.view(np.uint8).reshape(-1, 8), axis=1).sum(axis=1)
        for j in np.nonzero(d <= max_dist)[0]:
            pairs.append((i, i + 1 + int(j), int(d[j])))
    return pairs


def thumb(path, size=(360, 240)):
    with Image.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail(size)
        return np.asarray(im)


def grid_figure(items, title, out_path, ncols=4):
    """items = [(đường dẫn ảnh, chú thích)]"""
    nrows = -(-len(items) // ncols)
    fig, axes = pu.plt.subplots(nrows, ncols, figsize=(ncols * 2.6, nrows * 2.2))
    for ax in np.ravel(axes):
        ax.axis("off")
    for ax, (p, cap) in zip(np.ravel(axes), items):
        ax.imshow(thumb(p))
        ax.set_title(cap, fontsize=8, color=pu.TEXT_2)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout(h_pad=1.6)
    pu.save(fig, out_path)


def main():
    budget = float(os.environ.get("AUTOWISE_TIME_BUDGET", 0)) or None
    OUT.mkdir(parents=True, exist_ok=True)
    inv = build_inventory(budget)
    if inv is None:
        return
    inv.to_csv(OUT / "inventory.csv", index=False, encoding="utf-8-sig")

    # --- Trùng tuyệt đối (SHA-256) -----------------------------------------------------------
    g = inv.groupby("sha256")
    inv["dup_group_size"] = g["file"].transform("size")
    inv["years_in_group"] = g["year"].transform(lambda s: s.max() - s.min())
    uniq = inv.drop_duplicates("sha256").reset_index(drop=True)
    sizes = g.size()
    n_unique_dir = len(list(UNIQUE_DIR.glob("*.jpg"))) if UNIQUE_DIR.exists() else None

    # --- Gần giống (pHash) trên các ảnh khác nhau ------------------------------------------------
    pairs = near_duplicates(uniq["phash"].tolist(), 8)
    nd = pd.DataFrame(pairs, columns=["i", "j", "dist"])
    nd["file_a"], nd["file_b"] = uniq.loc[nd["i"], "file"].values, uniq.loc[nd["j"], "file"].values
    nd["same_make_model"] = (uniq.loc[nd["i"], "make_model_key"].values == uniq.loc[nd["j"], "make_model_key"].values)
    nd.drop(columns=["i", "j"]).sort_values("dist").to_csv(OUT / "near_duplicates.csv", index=False, encoding="utf-8-sig")

    s = {
        "so_file_anh": int(len(inv)),
        "so_anh_khac_nhau_sha256": int(len(uniq)),
        "so_file_trung_tuyet_doi": int(len(inv) - len(uniq)),
        "so_anh_dung_cho_tu_2_file_tro_len": int((sizes >= 2).sum()),
        "nhom_trung_lon_nhat": int(sizes.max()),
        "so_anh_trong_thu_muc_unique": n_unique_dir,
        "so_dong_xe_trong_ten_file": int(inv["make_model_key"].nunique()),
        "cap_gan_giong_dist_le_4": int((nd["dist"] <= 4).sum()),
        "cap_gan_giong_dist_5_8": int(((nd["dist"] > 4) & (nd["dist"] <= 8)).sum()),
        "ty_le_cap_gan_giong_cung_dong_xe_pct": round(float(nd["same_make_model"].mean() * 100), 1) if len(nd) else None,
        "dung_luong_tong_mb": round(inv["bytes"].sum() / 1e6, 1),
        "dung_luong_unique_mb": round(uniq["bytes"].sum() / 1e6, 1),
        "chieu_rong_trung_vi": int(inv["width"].median()),
        "chieu_cao_trung_vi": int(inv["height"].median()),
    }
    (OUT / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=2))

    # --- Hình 1: một ảnh bị lưu thành nhiều file của nhiều đời xe -----------------------------------
    big = inv[inv["dup_group_size"] == inv["dup_group_size"].max()].sort_values("year")
    pick = big.iloc[np.linspace(0, len(big) - 1, 8).round().astype(int)]
    grid_figure([(IMG_DIR / f, f) for f in pick["file"]],
                f"Cùng một ảnh bị lưu thành {len(big)} file cho {big['year'].nunique()} đời xe khác nhau",
                OUT / "fig_exact_duplicate_example.png")

    # --- Hình 2: phân bố số file dùng chung một ảnh ---------------------------------------------------
    bins = pd.cut(sizes, [0, 1, 2, 3, 5, 10, 20, 1000], labels=["1", "2", "3", "4-5", "6-10", "11-20", "> 20"])
    vc = bins.value_counts().sort_index()
    pu.barh(vc, "Một ảnh gốc được lưu thành bao nhiêu file? (số ảnh gốc)", OUT / "fig_duplicate_group_sizes.png",
            xlabel="Số ảnh gốc", sort=False)

    # --- Hình 3: ảnh mẫu của các dòng xe phổ biến (1 ảnh / dòng) -----------------------------------------
    top = inv["make_model_key"].value_counts().index[:12]
    samp = [(IMG_DIR / inv[inv["make_model_key"] == k].sort_values("year").iloc[-1]["file"],
             inv[inv["make_model_key"] == k].sort_values("year").iloc[-1]["file"].removesuffix(".jpg")) for k in top]
    grid_figure(samp, "12 dòng xe nhiều ảnh nhất: nhãn năm mới nhưng nhiều ảnh là xe đời cũ", OUT / "fig_sample_images.png")

    # --- Hình 4: vài cặp gần giống (pHash) ----------------------------------------------------------------
    if len(nd):
        ex = nd[(nd["dist"] > 0) & (nd["dist"] <= 8)].sort_values("dist").head(4)
        items = []
        for _, r in ex.iterrows():
            items += [(IMG_DIR / r["file_a"], f"{r['file_a'][:-4]}"), (IMG_DIR / r["file_b"], f"{r['file_b'][:-4]} (d={r['dist']})")]
        if items:
            grid_figure(items, "pHash bắt nhầm: các cặp “gần giống” (d ≤ 6) thực ra là xe khác nhau chụp cùng góc",
                        OUT / "fig_near_duplicate_pairs.png", ncols=4)
    print(f"\n==> Kết quả trong {OUT}")


if __name__ == "__main__":
    main()
