
import re
import time
import html
import sys
from io import BytesIO
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import requests
from PIL import Image
from tqdm import tqdm


# ==========================================
# 1. CẤU HÌNH
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_CSV = BASE_DIR / "data" / "vehicles_clean.csv"
OUTPUT_CSV = BASE_DIR / "data" / "vehicles_with_images.csv"
MANIFEST_CSV = BASE_DIR / "data" / "image_manifest.csv"

IMAGE_DIR = BASE_DIR / "assets" / "car_images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

MAX_CARS = None          # None để tải toàn bộ các mẫu xe trong dataset
DELAY = 1.0             # Nghỉ 1 giây giữa các lượt tìm kiếm
SAVE_EVERY = 10         # Lưu tiến độ định kỳ mỗi 10 xe (tránh nghẽn ổ đĩa)
MIN_WIDTH = 400
MIN_HEIGHT = 250

API_URL = "https://commons.wikimedia.org/w/api.php"

HEADERS = {
    "User-Agent": (
        "AutoWiseAcademicProject/1.0 "
        "(student research; contact: replace-with-your-email@example.com)"
    )
}

session = requests.Session()
session.headers.update(HEADERS)


# ==========================================
# 2. HÀM TIỆN ÍCH
# ==========================================

def clean_value(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.lower() in [
        "nan", "none", "null", "unknown", "unspecified"
    ]:
        return ""

    return value


def safe_filename(value):
    value = str(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")[:120]


def get_column(df, possible_names):
    lookup = {
        column.lower().strip(): column
        for column in df.columns
    }

    for name in possible_names:
        if name.lower() in lookup:
            return lookup[name.lower()]

    return None


def normalize_year(value):
    value = clean_value(value)

    if not value:
        return ""

    try:
        year = int(float(value))
        if 1900 <= year <= 2030:
            return str(year)
    except ValueError:
        pass

    return ""


def make_car_key(row):
    year = row["_year"]
    brand = row["_brand"]
    model = row["_model"]

    return safe_filename(
        f"{brand}_{model}_{year}"
    )


def build_queries(row):
    year = row["_year"]
    brand = row["_brand"]
    model = row["_model"]

    queries = []

    if brand and model and year:
        queries.append(
            f"{brand} {model} {year} automobile"
        )
        queries.append(
            f"{brand} {model} {year}"
        )

    if brand and model:
        queries.append(
            f"{brand} {model} automobile"
        )
        queries.append(
            f"{brand} {model}"
        )

    return queries


# ==========================================
# 3. TÌM ẢNH TRÊN WIKIMEDIA COMMONS
# ==========================================

def search_commons(query, limit=12):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": 1000,
        "format": "json"
    }

    try:
        response = session.get(
            API_URL,
            params=params,
            timeout=25
        )
        response.raise_for_status()

        data = response.json()
        pages = data.get("query", {}).get(
            "pages", {}
        )

        results = []

        for page in pages.values():
            imageinfo = page.get("imageinfo", [])

            if not imageinfo:
                continue

            info = imageinfo[0]
            title = page.get("title", "")
            url = info.get(
                "thumburl",
                info.get("url", "")
            )

            if not url:
                continue

            metadata = info.get(
                "extmetadata", {}
            )

            results.append({
                "title": title,
                "url": url,
                "source_url": info.get(
                    "descriptionurl", ""
                ),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "license": metadata.get(
                    "LicenseShortName", {}
                ).get("value", ""),
                "license_url": metadata.get(
                    "LicenseUrl", {}
                ).get("value", ""),
                "artist": html.unescape(
                    re.sub(
                        r"<[^>]+>",
                        "",
                        metadata.get(
                            "Artist", {}
                        ).get("value", "")
                    )
                )
            })

        return results

    except requests.RequestException as e:
        print("Lỗi tìm kiếm:", e)
        return []


# ==========================================
# 4. CHẤM ĐIỂM ẢNH THEO TÊN FILE
# ==========================================

def image_score(image, row):
    title = image["title"].lower()
    clean_title = re.sub(r"[^a-z0-9]+", "", title)

    brand = row["_brand"].lower()
    clean_brand = re.sub(r"[^a-z0-9]+", "", brand)

    model = row["_model"].lower()
    clean_model = re.sub(r"[^a-z0-9]+", "", model)

    year = str(row["_year"]).strip()

    score = 0

    if clean_brand and clean_brand in clean_title:
        score += 3

    if clean_model and clean_model in clean_title:
        score += 5

    if year and year in title:
        score += 2

    if image["width"] >= MIN_WIDTH:
        score += 1

    if image["height"] >= MIN_HEIGHT:
        score += 1

    # Loại bớt những ảnh không phải ảnh xe
    negative_words = [
        "logo", "badge", "diagram",
        "engine", "interior", "wheel",
        "dashboard", "emblem"
    ]

    if any(word in title for word in negative_words):
        score -= 10

    return score


def find_best_image(row):
    if not row["_brand"]:
        return None

    if not row["_model"]:
        return None

    candidates = []

    for query in build_queries(row):
        images = search_commons(query)

        for image in images:
            score = image_score(image, row)

            if score >= 8:
                image["score"] = score
                candidates.append(image)

        if candidates:
            break

        time.sleep(DELAY)

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return candidates[0]


# ==========================================
# 5. TẢI VÀ KIỂM TRA ẢNH
# ==========================================

def download_image(image_info, filename):
    destination = IMAGE_DIR / f"{filename}.jpg"

    if destination.exists():
        return destination

    try:
        response = session.get(
            image_info["url"],
            timeout=35
        )
        response.raise_for_status()

        img = Image.open(
            BytesIO(response.content)
        )

        if (
            img.width < MIN_WIDTH
            or img.height < MIN_HEIGHT
        ):
            return None

        img = img.convert("RGB")

        img.thumbnail(
            (1200, 900),
            Image.Resampling.LANCZOS
        )

        img.save(
            destination,
            "JPEG",
            quality=90
        )

        return destination

    except Exception as e:
        print("Lỗi tải ảnh:", e)
        return None


# ==========================================
# 6. CHƯƠNG TRÌNH CHÍNH
# ==========================================

def main():
    if not INPUT_CSV.exists():
        print("Không tìm thấy CSV:")
        print(INPUT_CSV)
        return

    print("Đang đọc dữ liệu...")

    df = pd.read_csv(
        INPUT_CSV,
        low_memory=False
    )

    print("Tổng số xe trong dataset:", len(df))

    brand_col = get_column(
        df, ["manufacturer", "make", "brand"]
    )

    model_base_col = get_column(
        df, ["model_base"]
    )

    model_col = get_column(
        df, ["model", "car_model"]
    )

    year_col = get_column(
        df, ["year", "model_year"]
    )

    if not brand_col or (not model_base_col and not model_col):
        print(
            "CSV cần có cột hãng xe và dòng xe."
        )
        return

    df["_brand"] = df[brand_col].map(clean_value)

    # Ưu tiên lấy model_base để gom nhóm (ví dụ: civic lx, civic ex -> civic)
    if model_base_col:
        df["_model"] = df[model_base_col].map(clean_value)
        if model_col:
            empty_mask = df["_model"] == ""
            df.loc[empty_mask, "_model"] = df.loc[empty_mask, model_col].map(clean_value)
    else:
        df["_model"] = df[model_col].map(clean_value)

    df["_year"] = (
        df[year_col].map(normalize_year)
        if year_col else ""
    )

    # Vectorized tạo key cực nhanh (<0.5 giây cho toàn bộ dataset)
    clean_keys = (
        df["_brand"].str.lower()
        + "_"
        + df["_model"].str.lower()
        + "_"
        + df["_year"].astype(str)
    )
    df["_image_key"] = (
        clean_keys.str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_")
    )

    # Đếm số lượng xe thực tế trong dataset cho mỗi mẫu xe
    key_counts = df["_image_key"].value_counts()

    unique_cars = df.drop_duplicates(
        "_image_key"
    )[["_image_key", "_brand", "_model", "_year"]].copy()

    unique_cars["frequency"] = unique_cars["_image_key"].map(key_counts)

    unique_cars = unique_cars[
        (unique_cars["_brand"] != "")
        & (unique_cars["_model"] != "")
    ]

    # Sắp xếp giảm dần theo số lượng xe trong dataset (xe phổ biến nhất tải trước)
    unique_cars = unique_cars.sort_values(
        by="frequency", ascending=False
    ).reset_index(drop=True)

    # Đọc kết quả cũ để có thể tiếp tục
    if MANIFEST_CSV.exists():
        manifest = pd.read_csv(
            MANIFEST_CSV
        )
        records = manifest.to_dict(
            "records"
        )
    else:
        records = []

    completed = {
        str(record["image_key"])
        for record in records
    }

    # Lọc các xe chưa được xử lý trước đó
    pending_cars = unique_cars[
        ~unique_cars["_image_key"].isin(completed)
    ].copy()

    if MAX_CARS is not None:
        cars_to_process = pending_cars.head(
            MAX_CARS
        )
    else:
        cars_to_process = pending_cars

    print(
        f"Tổng số mẫu xe độc nhất (theo model_base + year): {len(unique_cars)}"
    )
    print(
        f"Đã xử lý trước đó: {len(completed)}"
    )
    print(
        f"Số mẫu xe cần tìm ảnh đợt này: {len(cars_to_process)}"
    )

    if cars_to_process.empty:
        print("Tất cả các mẫu xe đã được xử lý xong trong manifest!")

    def save_manifest_file():
        if records:
            pd.DataFrame(records).to_csv(
                MANIFEST_CSV,
                index=False,
                encoding="utf-8-sig"
            )

    def export_output():
        if not records:
            return
        manifest_df = pd.DataFrame(records)

        # Giữ nguyên các cột gốc trong CSV (loại bỏ các cột ảnh cũ nếu có)
        original_columns = [
            col for col in df.columns
            if not col.startswith("_") and not col.startswith("image_")
        ]

        output = df[
            original_columns + ["_image_key"]
        ].copy()

        manifest_renamed = manifest_df.rename(
            columns={"image_key": "_image_key"}
        )

        output = output.merge(
            manifest_renamed,
            on="_image_key",
            how="left"
        )

        output = output.drop(
            columns=["_image_key"]
        )

        output.to_csv(
            OUTPUT_CSV,
            index=False,
            encoding="utf-8-sig"
        )
        output.to_csv(
            INPUT_CSV,
            index=False,
            encoding="utf-8-sig"
        )

        print("\nHOÀN THÀNH LƯU TIẾN ĐỘ!")
        print("CSV kết quả:", OUTPUT_CSV)
        print("Ảnh lưu tại:", IMAGE_DIR)

        print("\nThống kê hiện tại:")
        print(
            output["image_status"].value_counts(
                dropna=False
            )
        )

    try:
        for idx, (_, row) in enumerate(tqdm(
            cars_to_process.iterrows(),
            total=len(cars_to_process),
            desc="Đang tải ảnh xe"
        )):
            key = row["_image_key"]

            image = find_best_image(row)

            result = {
                "image_key": key,
                "image_path": "",
                "image_source": "",
                "image_license": "",
                "image_license_url": "",
                "image_artist": "",
                "image_match_score": "",
                "image_status": "not_found"
            }

            if image is not None:
                path = download_image(
                    image, key
                )

                if path:
                    result.update({
                        "image_path": path.relative_to(
                            BASE_DIR
                        ).as_posix(),
                        "image_source": image[
                            "source_url"
                        ],
                        "image_license": image[
                            "license"
                        ],
                        "image_license_url": image[
                            "license_url"
                        ],
                        "image_artist": image[
                            "artist"
                        ],
                        "image_match_score": image[
                            "score"
                        ],
                        "image_status": "downloaded"
                    })

            records.append(result)
            completed.add(key)

            # Lưu tiến độ định kỳ mỗi SAVE_EVERY xe hoặc xe cuối cùng
            if (idx + 1) % SAVE_EVERY == 0 or (idx + 1) == len(cars_to_process):
                save_manifest_file()

            time.sleep(DELAY)

    except KeyboardInterrupt:
        print("\n\nĐã nhận lệnh dừng (Ctrl+C). Đang lưu tiến độ...")
        save_manifest_file()

    # Luôn đồng bộ và xuất CSV kết quả
    export_output()


if __name__ == "__main__":
    main()
