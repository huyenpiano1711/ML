#!/usr/bin/env python3
"""
AutoWiseAI - Vehicle Image Deduplication and Integrity Tool
===========================================================

Identifies exact binary duplicates (SHA-256) and visual near-duplicates (pHash)
in the AutoWiseAI vehicle dataset while preserving dataset integrity.

Key Safety Guarantees:
- Default mode is strictly DRY RUN.
- NEVER modifies or deletes original images in dry-run mode.
- NEVER overwrites original dataset CSV files.
- Preserves CSV reference relationships.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import imagehash
from tqdm import tqdm


# ==============================================================================
# BK-TREE FOR EFFICIENT PERCEPTUAL HASH SEARCH
# ==============================================================================

class BKTree:
    """
    BK-Tree for fast discrete metric search on 64-bit Hamming distance.
    Significantly outperforms O(N^2) pairwise comparisons.
    """
    def __init__(self):
        self.tree = None

    def add(self, item_id: int, hash_int: int):
        if self.tree is None:
            self.tree = (item_id, hash_int, {})
            return
        curr_id, curr_hash, children = self.tree
        while True:
            d = (curr_hash ^ hash_int).bit_count()
            if d in children:
                curr_id, curr_hash, children = children[d]
            else:
                children[d] = (item_id, hash_int, {})
                break

    def search(self, hash_int: int, radius: int):
        if self.tree is None:
            return []
        results = []
        stack = [self.tree]
        while stack:
            curr_id, curr_hash, children = stack.pop()
            d = (curr_hash ^ hash_int).bit_count()
            if d <= radius:
                results.append((curr_id, d))
            low = d - radius
            high = d + radius
            for dist, child in children.items():
                if low <= dist <= high:
                    stack.append(child)
        return results


# ==============================================================================
# IMAGE PROCESSING & METRICS
# ==============================================================================

def compute_sharpness(img_gray: Image.Image) -> float:
    """
    Computes sharpness using the variance of the 2D Laplacian operator.
    Higher values indicate crisper, more detailed images.
    """
    try:
        arr = np.array(img_gray, dtype=np.float32)
        if arr.shape[0] < 5 or arr.shape[1] < 5:
            return 0.0
        # Discrete 2D Laplacian kernel [[0, 1, 0], [1, -4, 1], [0, 1, 0]]
        lap = (
            arr[:-2, 1:-1]
            + arr[2:, 1:-1]
            + arr[1:-1, :-2]
            + arr[1:-1, 2:]
            - 4.0 * arr[1:-1, 1:-1]
        )
        return float(np.var(lap))
    except Exception:
        return 0.0


def inspect_single_image(file_path: Path, base_dir: Path) -> dict:
    """
    Extracts metadata, binary SHA-256, perceptual hash (pHash), dimensions,
    and sharpness for a single image file.
    """
    rel_path = file_path.relative_to(base_dir).as_posix()
    file_size = file_path.stat().st_size

    # 1. SHA-256 binary hash
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        sha256_str = sha256_hash.hexdigest()
    except Exception as e:
        return {
            "filename": file_path.name,
            "relative_path": rel_path,
            "sha256": "",
            "phash": "",
            "phash_int": 0,
            "width": 0,
            "height": 0,
            "file_size": file_size,
            "readable": False,
            "sharpness": 0.0,
            "error": str(e),
        }

    # 2. PIL Image decode & pHash
    try:
        with Image.open(file_path) as im:
            width, height = im.size
            im_gray = im.convert("L")
            phash_obj = imagehash.phash(im)
            phash_str = str(phash_obj)
            # Convert hex pHash to 64-bit integer
            phash_int = int(phash_str, 16)
            sharpness = compute_sharpness(im_gray)

        return {
            "filename": file_path.name,
            "relative_path": rel_path,
            "sha256": sha256_str,
            "phash": phash_str,
            "phash_int": phash_int,
            "width": width,
            "height": height,
            "file_size": file_size,
            "readable": True,
            "sharpness": round(sharpness, 2),
            "error": "",
        }
    except Exception as e:
        return {
            "filename": file_path.name,
            "relative_path": rel_path,
            "sha256": sha256_str,
            "phash": "",
            "phash_int": 0,
            "width": 0,
            "height": 0,
            "file_size": file_size,
            "readable": False,
            "sharpness": 0.0,
            "error": str(e),
        }


# ==============================================================================
# CSV REFERENCE INDEXING
# ==============================================================================

def load_csv_reference_counts(data_dir: Path) -> dict:
    """
    Collects counts of how often each image path is referenced in the CSVs
    (vehicles_clean.csv, image_manifest.csv, vehicles_with_images.csv).
    Returns mapping from normalized relative path (assets/car_images/...) to int count.
    """
    ref_counts = defaultdict(int)

    csv_candidates = [
        data_dir / "vehicles_clean.csv",
        data_dir / "image_manifest.csv",
        data_dir / "vehicles_with_images.csv",
    ]

    for csv_file in csv_candidates:
        if not csv_file.exists():
            continue
        try:
            # Read only relevant image path columns for speed
            sample_df = pd.read_csv(csv_file, nrows=2)
            path_cols = [
                c for c in sample_df.columns
                if "path" in c.lower() or "image" in c.lower()
            ]
            for col in path_cols:
                # We specifically look for column 'image_path'
                if col == "image_path":
                    df = pd.read_csv(csv_file, usecols=[col], low_memory=False)
                    for val in df[col].dropna():
                        val_str = str(val).strip().replace("\\", "/")
                        if val_str:
                            ref_counts[val_str] += 1
                            # Also store filename alone for loose lookup
                            fname = Path(val_str).name
                            ref_counts[f"fname::{fname}"] += 1
        except Exception as e:
            print(f"  [!] Lưu ý khi đọc {csv_file.name}: {e}")

    return ref_counts


# ==============================================================================
# VISUAL CONTACT SHEET GENERATION
# ==============================================================================

def generate_contact_sheets(
    review_pairs: list,
    images_by_path: dict,
    base_dir: Path,
    output_dir: Path,
    max_sheets: int = 25,
    pairs_per_sheet: int = 4
):
    """
    Generates side-by-side visual comparison contact sheets for near-duplicate pairs.
    Allows human reviewers to quickly verify similarity.
    """
    sheet_dir = output_dir / "contact_sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)

    if not review_pairs:
        return 0

    # Limit to top candidate pairs
    sample_pairs = review_pairs[: max_sheets * pairs_per_sheet]
    total_sheets = (len(sample_pairs) + pairs_per_sheet - 1) // pairs_per_sheet

    thumb_w, thumb_h = 320, 200
    card_h = thumb_h + 90
    card_w = (thumb_w * 2) + 60
    margin = 30
    header_h = 60

    sheet_count = 0
    font = ImageFont.load_default()

    for sheet_idx in range(min(total_sheets, max_sheets)):
        start = sheet_idx * pairs_per_sheet
        batch = sample_pairs[start : start + pairs_per_sheet]

        canvas_w = card_w + (margin * 2)
        canvas_h = header_h + (len(batch) * card_h) + (margin * 2)

        canvas = Image.new("RGB", (canvas_w, canvas_h), color=(245, 247, 250))
        draw = ImageDraw.Draw(canvas)

        # Header
        title = f"AutoWiseAI Near-Duplicate Review - Sheet {sheet_idx + 1:02d}/{total_sheets:02d}"
        draw.text((margin, 20), title, fill=(20, 30, 50), font=font)
        draw.line(
            [(margin, 48), (canvas_w - margin, 48)],
            fill=(200, 210, 220),
            width=2
        )

        for i, pair in enumerate(batch):
            y_offset = header_h + margin + (i * card_h)
            draw.rectangle(
                [(margin, y_offset), (canvas_w - margin, y_offset + card_h - 15)],
                fill=(255, 255, 255),
                outline=(220, 225, 230),
                width=1
            )

            pref_path = base_dir / pair["preferred_path"]
            cand_path = base_dir / pair["candidate_path"]
            dist = pair["phash_distance"]
            group_id = pair["group_id"]

            # Info Header
            info_txt = (
                f"Group {group_id} | Hamming Distance: {dist} | "
                f"Status: {pair['review_status']} | Reason: {pair['reason']}"
            )
            draw.text((margin + 15, y_offset + 10), info_txt, fill=(30, 60, 100), font=font)

            # Left image: Preferred
            x1 = margin + 15
            y1 = y_offset + 30
            try:
                if pref_path.exists():
                    with Image.open(pref_path) as im1:
                        im1.thumbnail((thumb_w, thumb_h))
                        canvas.paste(im1, (x1, y1))
            except Exception:
                draw.rectangle([(x1, y1), (x1 + thumb_w, y1 + thumb_h)], fill=(230, 230, 230))
                draw.text((x1 + 20, y1 + 50), "[Error loading image]", fill=(200, 0, 0), font=font)

            pref_meta = images_by_path.get(pair["preferred_path"], {})
            txt_pref = (
                f"[PREFERRED] {pref_path.name[:35]}\n"
                f"Res: {pref_meta.get('width', 0)}x{pref_meta.get('height', 0)} | "
                f"CSV Refs: {pref_meta.get('csv_reference_count', 0)} | "
                f"Sharpness: {pref_meta.get('sharpness', 0)}"
            )
            draw.text((x1, y1 + thumb_h + 8), txt_pref, fill=(0, 120, 50), font=font)

            # Right image: Candidate
            x2 = x1 + thumb_w + 30
            y2 = y1
            try:
                if cand_path.exists():
                    with Image.open(cand_path) as im2:
                        im2.thumbnail((thumb_w, thumb_h))
                        canvas.paste(im2, (x2, y2))
            except Exception:
                draw.rectangle([(x2, y2), (x2 + thumb_w, y2 + thumb_h)], fill=(230, 230, 230))
                draw.text((x2 + 20, y2 + 50), "[Error loading image]", fill=(200, 0, 0), font=font)

            cand_meta = images_by_path.get(pair["candidate_path"], {})
            txt_cand = (
                f"[CANDIDATE] {cand_path.name[:35]}\n"
                f"Res: {cand_meta.get('width', 0)}x{cand_meta.get('height', 0)} | "
                f"CSV Refs: {cand_meta.get('csv_reference_count', 0)} | "
                f"Sharpness: {cand_meta.get('sharpness', 0)}"
            )
            draw.text((x2, y2 + thumb_h + 8), txt_cand, fill=(180, 80, 0), font=font)

        out_file = sheet_dir / f"contact_sheet_{sheet_idx + 1:02d}.jpg"
        canvas.save(out_file, "JPEG", quality=88)
        sheet_count += 1

    return sheet_count


# ==============================================================================
# MAIN SCAN PIPELINE
# ==============================================================================

def run_deduplication_scan(
    image_dir: Path,
    data_dir: Path,
    output_dir: Path,
    base_dir: Path,
    strong_thresh: int = 4,
    review_thresh: int = 8,
    max_workers: int = 8,
    skip_contact_sheets: bool = False
):
    print("=" * 70)
    print(" 🚘 AutoWiseAI - Vehicle Image Deduplication Scanner (DRY RUN)")
    print("=" * 70)
    print(f"[*] Base Directory:      {base_dir}")
    print(f"[*] Image Directory:     {image_dir}")
    print(f"[*] Data Directory:      {data_dir}")
    print(f"[*] Output Reports:      {output_dir}")
    print(f"[*] Strong Threshold:    <= {strong_thresh} (strong near-duplicate)")
    print(f"[*] Review Threshold:    <= {review_thresh} (manual review candidate)")
    print("=" * 70)

    start_time = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # STEP 1: Scan and inspect image files
    # -------------------------------------------------------------------------
    print("\n[Bước 1/5] Quét danh mục hình ảnh và tính toán mã Hash...")
    extensions = {".jpg", ".jpeg", ".png", ".webp"}
    image_files = [
        f for f in image_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in extensions
    ]
    print(f"  -> Tìm thấy tổng cộng {len(image_files)} tệp ảnh.")

    # Load CSV references
    print("  -> Đang tra cứu tần suất tham chiếu trong CSV dữ liệu...")
    csv_ref_counts = load_csv_reference_counts(data_dir)

    # Process images with ThreadPoolExecutor
    print(f"  -> Đang xử lý băm SHA-256, pHash, độ phân giải ({max_workers} threads)...")
    inventory = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = executor.map(lambda f: inspect_single_image(f, base_dir), image_files)
        for item in tqdm(futures, total=len(image_files), desc="Phân tích ảnh"):
            rel_p = item["relative_path"]
            fname = item["filename"]
            # Look up CSV references
            ref_c = csv_ref_counts.get(rel_p, 0)
            if ref_c == 0:
                ref_c = csv_ref_counts.get(f"fname::{fname}", 0)
            item["csv_reference_count"] = ref_c
            inventory.append(item)

    # Convert inventory to DataFrame
    inventory_df = pd.DataFrame(inventory)
    inventory_csv_path = output_dir / "image_inventory.csv"
    inventory_df[[
        "filename", "relative_path", "sha256", "phash",
        "width", "height", "file_size", "readable", "csv_reference_count"
    ]].to_csv(inventory_csv_path, index=False, encoding="utf-8-sig")
    print(f"  [✓] Đã xuất kiểm kê: {inventory_csv_path.name} ({len(inventory_df)} bản ghi)")

    # Filter readable images
    readable_images = [img for img in inventory if img["readable"]]
    corrupted_images = [img for img in inventory if not img["readable"]]
    images_by_path = {img["relative_path"]: img for img in inventory}

    # -------------------------------------------------------------------------
    # STEP 2: Detect exact binary duplicates (SHA-256)
    # -------------------------------------------------------------------------
    print("\n[Bước 2/5] Nhận diện ảnh trùng lặp nhị phân tuyệt đối (SHA-256)...")
    sha_groups = defaultdict(list)
    for img in readable_images:
        sha_groups[img["sha256"]].append(img)

    exact_dup_groups = [g for g in sha_groups.values() if len(g) > 1]
    exact_records = []
    exact_proposed_mappings = []
    exact_redundant_files_count = 0
    potential_savings_bytes = 0

    group_counter = 1
    for grp in exact_dup_groups:
        # Preferred image selection rules:
        # 1. Highest CSV reference count
        # 2. Highest resolution (width * height)
        # 3. Largest file size
        # 4. Shortest filename
        sorted_grp = sorted(
            grp,
            key=lambda x: (
                x["csv_reference_count"],
                x["width"] * x["height"],
                x["file_size"],
                -len(x["filename"])
            ),
            reverse=True
        )
        preferred = sorted_grp[0]
        group_id = f"EXACT_{group_counter:04d}"
        group_counter += 1

        for item in sorted_grp:
            is_pref = (item["relative_path"] == preferred["relative_path"])
            exact_records.append({
                "group_id": group_id,
                "image_path": item["relative_path"],
                "preferred_image": preferred["relative_path"],
                "sha256": item["sha256"],
                "csv_reference_count": item["csv_reference_count"]
            })
            if not is_pref:
                exact_redundant_files_count += 1
                potential_savings_bytes += item["file_size"]
                exact_proposed_mappings.append({
                    "old_image_path": item["relative_path"],
                    "proposed_image_path": preferred["relative_path"],
                    "duplicate_type": "exact",
                    "confidence_category": "exact_binary_match",
                    "review_required": False
                })

    exact_df = pd.DataFrame(exact_records)
    exact_csv_path = output_dir / "exact_duplicates.csv"
    if not exact_df.empty:
        exact_df.to_csv(exact_csv_path, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=[
            "group_id", "image_path", "preferred_image", "sha256", "csv_reference_count"
        ]).to_csv(exact_csv_path, index=False, encoding="utf-8-sig")

    print(f"  -> Nhóm trùng lặp tuyệt đối (Exact): {len(exact_dup_groups)} nhóm.")
    print(f"  -> Số tệp dư thừa có thể tối ưu:    {exact_redundant_files_count} tệp.")
    print(f"  -> Dung lượng có thể tiết kiệm:      {potential_savings_bytes / (1024*1024):.2f} MB.")
    print(f"  [✓] Đã xuất báo cáo: {exact_csv_path.name}")

    # -------------------------------------------------------------------------
    # STEP 3: Detect visual near-duplicates using BK-Tree and pHash
    # -------------------------------------------------------------------------
    print("\n[Bước 3/5] Nhận diện ảnh tương đồng thị giác (pHash & BK-Tree)...")
    # For near-duplicates, we index unique SHA images to avoid duplicate pair explosions
    canonical_for_sha = {}
    for grp in exact_dup_groups:
        sorted_grp = sorted(
            grp,
            key=lambda x: (x["csv_reference_count"], x["width"] * x["height"]),
            reverse=True
        )
        for member in sorted_grp[1:]:
            canonical_for_sha[member["relative_path"]] = sorted_grp[0]["relative_path"]

    # Build BK-tree on representative images
    rep_images = [
        img for img in readable_images
        if img["relative_path"] not in canonical_for_sha
    ]
    print(f"  -> Xây dựng cấu trúc chỉ mục BK-Tree trên {len(rep_images)} ảnh độc lập...")

    tree = BKTree()
    idx_to_img = {}
    for idx, img in enumerate(rep_images):
        idx_to_img[idx] = img
        tree.add(idx, img["phash_int"])

    print(f"  -> Tìm kiếm ứng viên tương đồng với bán kính Hamming <= {review_thresh}...")
    candidate_pairs = []
    seen_pairs = set()

    for idx, img in tqdm(enumerate(rep_images), total=len(rep_images), desc="BK-Tree Search"):
        matches = tree.search(img["phash_int"], review_thresh)
        for match_idx, dist in matches:
            if match_idx == idx:
                continue
            u, v = min(idx, match_idx), max(idx, match_idx)
            if (u, v) in seen_pairs:
                continue
            seen_pairs.add((u, v))

            img_a = idx_to_img[u]
            img_b = idx_to_img[v]

            # Choose candidate preferred between the pair
            # Criteria: CSV reference, resolution, sharpness, file size
            score_a = (
                img_a["csv_reference_count"],
                img_a["width"] * img_a["height"],
                img_a["sharpness"],
                img_a["file_size"]
            )
            score_b = (
                img_b["csv_reference_count"],
                img_b["width"] * img_b["height"],
                img_b["sharpness"],
                img_b["file_size"]
            )
            if score_a >= score_b:
                pref, cand = img_a, img_b
            else:
                pref, cand = img_b, img_a

            if dist <= strong_thresh:
                status = "STRONG_CANDIDATE"
                conf = "strong_near_match"
                reason = f"pHash distance {dist} (high visual similarity)"
            else:
                status = "REVIEW_CANDIDATE"
                conf = "candidate_review_needed"
                reason = f"pHash distance {dist} (moderate similarity, manual check needed)"

            candidate_pairs.append({
                "preferred_path": pref["relative_path"],
                "candidate_path": cand["relative_path"],
                "phash_distance": dist,
                "review_status": status,
                "confidence_category": conf,
                "reason": reason,
            })

    # Sort pairs by distance ascending
    candidate_pairs.sort(key=lambda x: (x["phash_distance"], x["review_status"]))

    # Construct near_duplicates_review.csv and proposed mappings
    near_dup_records = []
    near_proposed_mappings = []

    for idx, pair in enumerate(candidate_pairs, 1):
        group_id = f"NEAR_{idx:04d}"
        pair["group_id"] = group_id

        near_dup_records.append({
            "group_id": group_id,
            "image_path": pair["candidate_path"],
            "candidate_preferred_image": pair["preferred_path"],
            "phash_distance": pair["phash_distance"],
            "review_status": pair["review_status"],
            "reason": pair["reason"]
        })

        near_proposed_mappings.append({
            "old_image_path": pair["candidate_path"],
            "proposed_image_path": pair["preferred_path"],
            "duplicate_type": "near",
            "confidence_category": pair["confidence_category"],
            "review_required": True  # All near-duplicates require manual review
        })

    near_df = pd.DataFrame(near_dup_records)
    near_csv_path = output_dir / "near_duplicates_review.csv"
    if not near_df.empty:
        near_df.to_csv(near_csv_path, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=[
            "group_id", "image_path", "candidate_preferred_image",
            "phash_distance", "review_status", "reason"
        ]).to_csv(near_csv_path, index=False, encoding="utf-8-sig")

    print(f"  -> Cặp ảnh tương đồng thị giác phát hiện: {len(candidate_pairs)} cặp.")
    strong_cnt = sum(1 for p in candidate_pairs if p["review_status"] == "STRONG_CANDIDATE")
    review_cnt = sum(1 for p in candidate_pairs if p["review_status"] == "REVIEW_CANDIDATE")
    print(f"     * Strong candidates (khoảng cách 0-{strong_thresh}):  {strong_cnt}")
    print(f"     * Review candidates (khoảng cách {strong_thresh+1}-{review_thresh}): {review_cnt}")
    print(f"  [✓] Đã xuất báo cáo: {near_csv_path.name}")

    # -------------------------------------------------------------------------
    # STEP 4: Combine proposed mappings
    # -------------------------------------------------------------------------
    print("\n[Bước 4/5] Tổng hợp bảng đề xuất ánh xạ đường dẫn (Proposed Mapping)...")
    all_mappings = exact_proposed_mappings + near_proposed_mappings
    mapping_df = pd.DataFrame(all_mappings)
    mapping_csv_path = output_dir / "image_path_mapping_proposed.csv"
    if not mapping_df.empty:
        mapping_df.to_csv(mapping_csv_path, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=[
            "old_image_path", "proposed_image_path",
            "duplicate_type", "confidence_category", "review_required"
        ]).to_csv(mapping_csv_path, index=False, encoding="utf-8-sig")
    print(f"  [✓] Đã xuất ánh xạ đề xuất: {mapping_csv_path.name} ({len(mapping_df)} dòng)")

    # -------------------------------------------------------------------------
    # STEP 5: Visual Contact Sheets & Summary Report
    # -------------------------------------------------------------------------
    print("\n[Bước 5/5] Tạo báo cáo tổng kết JSON & Contact Sheets...")
    sheet_count = 0
    if not skip_contact_sheets and candidate_pairs:
        print("  -> Đang sinh bảng ảnh so sánh trực quan (Contact Sheets)...")
        sheet_count = generate_contact_sheets(
            candidate_pairs,
            images_by_path,
            base_dir,
            output_dir,
            max_sheets=30,
            pairs_per_sheet=4
        )
        print(f"  [✓] Đã tạo {sheet_count} contact sheets tại: {output_dir / 'contact_sheets'}")

    # Build summary
    referenced_files_count = sum(1 for img in inventory if img["csv_reference_count"] > 0)
    summary = {
        "scan_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dry_run": True,
        "base_directory": str(base_dir),
        "image_directory": str(image_dir),
        "total_files_scanned": len(inventory),
        "readable_images": len(readable_images),
        "corrupted_images": len(corrupted_images),
        "files_referenced_by_csv": referenced_files_count,
        "unreferenced_images": len(inventory) - referenced_files_count,
        "exact_duplicate_groups": len(exact_dup_groups),
        "exact_duplicate_redundant_files": exact_redundant_files_count,
        "near_duplicate_candidate_pairs": len(candidate_pairs),
        "near_duplicate_strong_candidates": strong_cnt,
        "near_duplicate_review_candidates": review_cnt,
        "items_requiring_human_review": len(candidate_pairs),
        "potential_storage_savings_bytes": potential_savings_bytes,
        "potential_storage_savings_mb": round(potential_savings_bytes / (1024 * 1024), 2),
        "contact_sheets_generated": sheet_count,
        "execution_time_seconds": round(time.time() - start_time, 2)
    }

    summary_path = output_dir / "deduplication_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  [✓] Đã xuất báo cáo tổng kết: {summary_path.name}")

    print("\n" + "=" * 70)
    print(" 🎉 HOÀN THÀNH QUÉT DRY RUN AN TOÀN!")
    print("=" * 70)
    print(f"  * Tổng số file ảnh đã quét:      {summary['total_files_scanned']}")
    print(f"  * Trùng lặp chính xác (Exact):   {summary['exact_duplicate_groups']} nhóm ({summary['exact_duplicate_redundant_files']} file dư thừa)")
    print(f"  * Tương đồng thị giác (Near):    {summary['near_duplicate_candidate_pairs']} cặp cần xem xét")
    print(f"  * Dung lượng có thể thu hồi:     {summary['potential_storage_savings_mb']} MB")
    print(f"  * Toàn bộ báo cáo được lưu tại:   {output_dir}")
    print("=" * 70)
    return summary


# ==============================================================================
# SAFE APPLY MODE (APPLIES ONLY APPROVED MAPPINGS TO COPIES, NEVER OVERWRITES)
# ==============================================================================

def run_safe_apply(
    mapping_file: Path,
    data_dir: Path,
    output_dir: Path,
    base_dir: Path,
    confirm: bool = False
):
    print("=" * 70)
    print(" 🛡️ AutoWiseAI - Safe Apply Mode")
    print("=" * 70)

    if not confirm:
        print("[!] LƯU Ý: Chế độ --apply yêu cầu thêm cờ --confirm để tiến hành.")
        print("    Mặc định hệ thống ngăn chặn mọi thay đổi tự động để bảo toàn dữ liệu.")
        print("    Vui lòng kiểm tra kỹ reports/image_deduplication/ trước khi áp dụng.")
        return

    if not mapping_file.exists():
        print(f"[!] Không tìm thấy tệp ánh xạ: {mapping_file}")
        return

    mapping_df = pd.read_csv(mapping_file)
    print(f"[*] Đọc danh sách ánh xạ từ: {mapping_file} ({len(mapping_df)} dòng)")

    # Only apply approved or exact duplicates where review_required is False
    applicable = mapping_df[~mapping_df["review_required"]].copy()
    print(f"[*] Số ánh xạ hợp lệ (Exact / Đã duyệt, review_required=False): {len(applicable)}")

    if applicable.empty:
        print("[*] Không có ánh xạ nào đủ điều kiện tự động áp dụng (tất cả đang chờ duyệt).")
        return

    map_dict = dict(zip(applicable["old_image_path"], applicable["proposed_image_path"]))

    # Create backup manifest
    backup_dir = output_dir / "apply_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest_record = {
        "apply_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mapping_source": str(mapping_file),
        "applied_mappings_count": len(applicable),
        "mappings": map_dict,
        "files_modified": []
    }

    # Create DEDUP copies of CSV datasets (NEVER overwrite originals)
    for csv_name in ["vehicles_clean.csv", "image_manifest.csv"]:
        src_csv = data_dir / csv_name
        if not src_csv.exists():
            continue
        dst_csv = data_dir / f"{src_csv.stem}_dedup{src_csv.suffix}"
        print(f"  -> Tạo bản sao cập nhật đường dẫn: {dst_csv.name}...")
        df = pd.read_csv(src_csv, low_memory=False)
        if "image_path" in df.columns:
            replaced_count = df["image_path"].isin(map_dict).sum()
            df["image_path"] = df["image_path"].replace(map_dict)
            df.to_csv(dst_csv, index=False, encoding="utf-8-sig")
            print(f"     [✓] Đã cập nhật {replaced_count} dòng tham chiếu trong {dst_csv.name}")
            manifest_record["files_modified"].append({
                "source": str(src_csv),
                "created_copy": str(dst_csv),
                "rows_updated": int(replaced_count)
            })

    # Save backup manifest
    backup_manifest_path = output_dir / "apply_backup_manifest.json"
    with open(backup_manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_record, f, indent=2, ensure_ascii=False)
    print(f"\n[✓] Áp dụng an toàn hoàn tất! Nhật ký audit: {backup_manifest_path}")
    print("[*] Các tệp gốc và hình ảnh nguyên bản KHÔNG hề bị xóa hay sửa đổi.")


# ==============================================================================
# CLI ENTRYPOINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="AutoWiseAI Vehicle Image Deduplication Tool"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Chạy ở chế độ quét an toàn, không xóa hay sửa đổi bất kỳ file nào (mặc định)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Áp dụng bảng ánh xạ đã được người dùng phê duyệt (chỉ ghi vào bản sao CSV)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Xác nhận áp dụng thay đổi khi dùng cùng --apply"
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        default="assets/car_images",
        help="Đường dẫn thư mục ảnh xe (mặc định: assets/car_images)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Đường dẫn thư mục dữ liệu CSV (mặc định: data)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports/image_deduplication",
        help="Đường dẫn lưu trữ báo cáo (mặc định: reports/image_deduplication)"
    )
    parser.add_argument(
        "--strong-thresh",
        type=int,
        default=4,
        help="Ngưỡng khoảng cách Hamming cho ứng viên trùng lặp mạnh (mặc định: 4)"
    )
    parser.add_argument(
        "--review-thresh",
        type=int,
        default=8,
        help="Ngưỡng khoảng cách Hamming cho ứng viên cần xem xét (mặc định: 8)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Số luồng CPU xử lý băm ảnh song song (mặc định: 8)"
    )
    parser.add_argument(
        "--skip-contact-sheets",
        action="store_true",
        help="Bỏ qua bước tạo ảnh Contact Sheets để quét nhanh nhất"
    )

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    image_dir = (base_dir / args.image_dir).resolve()
    data_dir = (base_dir / args.data_dir).resolve()
    output_dir = (base_dir / args.output_dir).resolve()

    if args.apply:
        mapping_file = output_dir / "image_path_mapping_proposed.csv"
        run_safe_apply(
            mapping_file=mapping_file,
            data_dir=data_dir,
            output_dir=output_dir,
            base_dir=base_dir,
            confirm=args.confirm
        )
    else:
        run_deduplication_scan(
            image_dir=image_dir,
            data_dir=data_dir,
            output_dir=output_dir,
            base_dir=base_dir,
            strong_thresh=args.strong_thresh,
            review_thresh=args.review_thresh,
            max_workers=args.workers,
            skip_contact_sheets=args.skip_contact_sheets
        )


if __name__ == "__main__":
    main()
