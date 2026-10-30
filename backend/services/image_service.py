"""
image_service.py - D05: XỬ LÝ HÌNH ẢNH XE CHO BACKEND

Nhận đường dẫn ảnh lưu trong catalog (cột image_path của recommendation_catalog.pkl,
đường dẫn tương đối so với gốc repo, ví dụ "assets/car_images_unique/ford_f150_2015.jpg"),
kiểm tra ảnh có dùng được hay không và trả về đường dẫn tuyệt đối để giao diện PyQt6 nạp.
Ảnh không dùng được thì trả ảnh thay thế assets/placeholder_car.png, để thẻ xe không
bao giờ bị trống và giao diện không phải tự xử lý lỗi ảnh.

Thứ tự tìm ảnh cho một thẻ xe (CarCard):
  1. image_path trong catalog (do C01 ghép sẵn).
  2. Nếu image_path trống hoặc hỏng: tìm theo khóa <hãng>_<dòng>_<năm> trong
     assets/car_images_unique, cùng quy tắc với build_catalog.attach_images()
     (đúng năm, nếu không có thì năm gần nhất của cùng dòng xe).
  3. Ảnh thay thế.

Một ảnh chỉ được coi là dùng được khi:
  - nằm trong thư mục ảnh của dự án (chặn đường dẫn kiểu "../../..."),
  - có đuôi .jpg / .jpeg / .png (định dạng QPixmap đọc được mà không cần plugin),
  - tồn tại, không rỗng, không quá MAX_FILE_MB,
  - Pillow đọc được phần đầu file và file có đủ dấu kết thúc của định dạng (không tải dở / cắt ngang).
Kết quả kiểm tra được lưu đệm theo (đường dẫn, thời điểm sửa, kích thước), nên mỗi ảnh
chỉ đọc từ đĩa một lần trong suốt phiên chạy ứng dụng.

Cách dùng trong Backend (D06 - app_service.py):
    from backend.services.image_service import get_image_service
    images = get_image_service()
    cards = images.with_images(result.to_cards())    # image_path luôn có giá trị
"""
from __future__ import annotations

import os
import re
import stat
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageDraw, ImageFont

from backend.schemas.result_schema import CarCard

PROJECT_DIR = Path(__file__).resolve().parents[2]
IMAGE_DIR = PROJECT_DIR / "assets" / "car_images_unique"
PLACEHOLDER_PATH = PROJECT_DIR / "assets" / "placeholder_car.png"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_FILE_MB = 20
PLACEHOLDER_SIZE = (720, 468)        # cùng tỷ lệ ~1,54 với ảnh trung vị của bộ ảnh (1.200 x 779)

# Nguồn của ảnh trả về
SOURCE_CATALOG = "catalog"                   # đúng image_path trong catalog
SOURCE_LOOKUP_EXACT = "lookup_exact"         # tìm lại theo hãng_dòng_năm, đúng năm
SOURCE_LOOKUP_NEAREST = "lookup_nearest_year"  # tìm lại theo dòng xe, năm gần nhất
SOURCE_PLACEHOLDER = "placeholder"

# Lý do một ảnh không dùng được (hoặc "ok")
OK = "ok"
MISSING_PATH = "missing_path"            # catalog không có đường dẫn ảnh
OUTSIDE_IMAGE_DIR = "outside_image_dir"  # đường dẫn trỏ ra ngoài thư mục ảnh
UNSUPPORTED_FORMAT = "unsupported_format"
NOT_FOUND = "not_found"
EMPTY_FILE = "empty_file"
TOO_LARGE = "too_large"
CORRUPT_IMAGE = "corrupt_image"

ILLUSTRATION_LABEL = "Ảnh minh họa dòng xe"
PLACEHOLDER_LABEL = "Chưa có ảnh minh họa"


@dataclass(frozen=True)
class ImageResult:
    """Kết quả tìm ảnh cho một xe. path luôn là đường dẫn tuyệt đối tới một file ảnh."""
    path: str
    is_placeholder: bool
    source: str                     # một trong các hằng SOURCE_*
    reason: str = OK                # lý do ảnh catalog không dùng được (OK nếu dùng được)
    requested: Optional[str] = None  # image_path gốc trong catalog

    @property
    def label(self) -> str:
        """Chú thích hiển thị dưới ảnh: ảnh lấy từ Wikimedia chỉ là ảnh minh họa dòng xe."""
        return PLACEHOLDER_LABEL if self.is_placeholder else ILLUSTRATION_LABEL


def safe_key(value: object) -> str:
    """Cùng quy tắc với safe_key() trong src/recommendation/build_catalog.py
    và safe_filename() trong scripts/download_car_images.py."""
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower().strip()).strip("_")[:120]


def create_placeholder(path: Path, size: tuple[int, int] = PLACEHOLDER_SIZE) -> Path:
    """Vẽ ảnh thay thế (hình xe đơn giản + dòng chữ) bằng Pillow và lưu ra file PNG."""
    w, h = size
    bg, body, dark, text = (241, 243, 245), (196, 202, 209), (120, 128, 138), (90, 98, 108)
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    s = w / 720                                       # tỷ lệ theo chiều rộng
    cx, base = w / 2, h * 0.60                        # tâm ngang, đường gầm xe

    def box(x0, y0, x1, y1):
        return [cx + x0 * s, base + y0 * s, cx + x1 * s, base + y1 * s]

    d.rounded_rectangle(box(-210, -70, 210, 0), radius=int(28 * s), fill=body)    # thân xe
    d.polygon([(cx - 120 * s, base - 70 * s), (cx - 70 * s, base - 140 * s),
               (cx + 80 * s, base - 140 * s), (cx + 140 * s, base - 70 * s)], fill=body)  # mui
    d.polygon([(cx - 100 * s, base - 76 * s), (cx - 62 * s, base - 128 * s),
               (cx - 8 * s, base - 128 * s), (cx - 8 * s, base - 76 * s)], fill=bg)       # kính trước
    d.polygon([(cx + 4 * s, base - 76 * s), (cx + 4 * s, base - 128 * s),
               (cx + 74 * s, base - 128 * s), (cx + 118 * s, base - 76 * s)], fill=bg)    # kính sau
    for x in (-125, 125):                                                          # bánh xe
        d.ellipse(box(x - 46, -38, x + 46, 54), fill=dark)
        d.ellipse(box(x - 20, -12, x + 20, 28), fill=body)

    font = None
    for name in ("DejaVuSans.ttf", "arial.ttf", "segoeui.ttf", "Arial.ttf"):
        try:
            font = ImageFont.truetype(name, int(26 * s))
            break
        except OSError:
            continue
    label = PLACEHOLDER_LABEL if font is not None else "No image available"
    font = font or ImageFont.load_default()
    tw = d.textlength(label, font=font)
    d.text(((w - tw) / 2, base + 80 * s), label, fill=text, font=font)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)
    return path


class ImageService:
    """Tìm và kiểm tra ảnh xe; nạp một lần, dùng lại cho mọi yêu cầu (không đọc lại ảnh đã kiểm)."""

    def __init__(self, project_dir: Path | str = PROJECT_DIR, image_dir: Path | str | None = None,
                 placeholder_path: Path | str | None = None, verify_images: bool = True,
                 max_file_mb: float = MAX_FILE_MB, full_verify: bool = False):
        self.project_dir = Path(project_dir).resolve()
        self.image_dir = Path(image_dir).resolve() if image_dir else (self.project_dir / "assets" / "car_images_unique")
        self.placeholder = Path(placeholder_path) if placeholder_path else (self.project_dir / "assets" / "placeholder_car.png")
        self.verify_images = verify_images
        self.full_verify = full_verify
        self.max_bytes = int(max_file_mb * 1024 * 1024)
        self._lock = threading.Lock()
        self._checked: dict[tuple[str, int, int], str] = {}   # (path, mtime_ns, size) -> reason
        self._index: dict[str, list[tuple[int, str]]] | None = None
        self._placeholder_ok = False
        self._placeholder_abs = self.placeholder.resolve()

    # ------------------------------------------------------------------ kiểm tra 1 file
    def _to_path(self, image_path: str | Path) -> Path:
        """Đường dẫn tuyệt đối đã chuẩn hóa ('..' được rút gọn) - không cần truy cập đĩa."""
        p = Path(str(image_path).strip().replace("\\", "/"))
        return Path(os.path.normpath(p if p.is_absolute() else self.project_dir / p))

    def check_file(self, path: Path) -> str:
        """Trả về OK hoặc lý do file ảnh không dùng được."""
        if not path.is_relative_to(self.image_dir):
            return OUTSIDE_IMAGE_DIR
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return UNSUPPORTED_FORMAT
        try:
            st = path.stat()
        except OSError:
            return NOT_FOUND
        if not stat.S_ISREG(st.st_mode):
            return NOT_FOUND
        if st.st_size == 0:
            return EMPTY_FILE
        if st.st_size > self.max_bytes:
            return TOO_LARGE
        key = (str(path), st.st_mtime_ns, st.st_size)
        with self._lock:
            cached = self._checked.get(key)
        if cached is not None:
            return cached
        reason = self._verify(path) if self.verify_images else OK
        with self._lock:
            self._checked[key] = reason
        return reason

    def _verify(self, path: Path) -> str:
        """Kiểm tra nhanh: Pillow đọc được phần đầu file (định dạng, kích thước) và file kết thúc
        đúng dấu kết thúc của định dạng (JPEG: FF D9, PNG: chunk IEND) - bắt được file tải dở hoặc
        bị cắt ngang mà không phải giải mã cả ảnh. full_verify=True: Pillow kiểm tra toàn bộ file."""
        try:
            with open(path, "rb") as f:                # mở file đúng một lần
                with Image.open(f) as im:
                    fmt = im.format
                    if fmt not in ("JPEG", "PNG"):
                        return UNSUPPORTED_FORMAT
                    w, h = im.size
                    if w <= 0 or h <= 0:
                        return CORRUPT_IMAGE
                    if self.full_verify:
                        im.verify()
                end = f.seek(0, os.SEEK_END)
                f.seek(max(0, end - 32))
                tail = f.read()
            if fmt == "JPEG" and b"\xff\xd9" not in tail:
                return CORRUPT_IMAGE
            if fmt == "PNG" and b"IEND" not in tail:
                return CORRUPT_IMAGE
            return OK
        except Exception:                  # noqa: BLE001 - mọi lỗi đọc ảnh đều coi là ảnh hỏng
            return CORRUPT_IMAGE

    # ------------------------------------------------------------------ ảnh thay thế
    def placeholder_path(self) -> Path:
        """Đường dẫn ảnh thay thế; tự vẽ lại nếu file bị xóa hoặc hỏng."""
        if self._placeholder_ok and self._placeholder_abs.is_file():
            return self._placeholder_abs
        with self._lock:
            ok = self.placeholder.is_file() and self._verify(self.placeholder) == OK
            if not ok:
                try:
                    create_placeholder(self.placeholder)
                    ok = True
                except OSError:            # thư mục chỉ đọc: vẫn trả đường dẫn, giao diện hiện khung trống
                    ok = False
            self._placeholder_ok = ok
            self._placeholder_abs = self.placeholder.resolve()
        return self._placeholder_abs

    def is_placeholder(self, path: str | Path | None) -> bool:
        return path is not None and Path(path).resolve() == self._placeholder_abs

    def _fallback(self, reason: str, requested: Optional[str]) -> ImageResult:
        return ImageResult(str(self.placeholder_path()), True, SOURCE_PLACEHOLDER, reason, requested)

    # ------------------------------------------------------------------ tìm theo hãng-dòng-năm
    def _build_index(self) -> dict[str, list[tuple[int, str]]]:
        index: dict[str, list[tuple[int, str]]] = {}
        if self.image_dir.is_dir():
            for p in self.image_dir.iterdir():
                m = re.match(r"^(.*)_(\d{4})\.(jpg|jpeg|png)$", p.name.lower())
                if m:
                    index.setdefault(m.group(1), []).append((int(m.group(2)), p.name))
        for files in index.values():
            files.sort()
        return index

    def lookup(self, manufacturer: object, model_base: object, year: object) -> tuple[Optional[Path], str]:
        """Tìm ảnh theo khóa <hãng>_<dòng>: đúng năm, nếu không có thì năm gần nhất
        (hòa thì lấy năm nhỏ hơn - cùng quy tắc build_catalog). Trả (đường dẫn | None, nguồn)."""
        if self._index is None:
            with self._lock:
                if self._index is None:
                    self._index = self._build_index()
        files = self._index.get(safe_key(f"{manufacturer}_{model_base}"))
        if not files:
            return None, SOURCE_PLACEHOLDER
        try:
            y = int(year)
        except (TypeError, ValueError):
            return None, SOURCE_PLACEHOLDER
        best_year, best_file = min(files, key=lambda f: (abs(f[0] - y), f[0]))
        source = SOURCE_LOOKUP_EXACT if best_year == y else SOURCE_LOOKUP_NEAREST
        return self.image_dir / best_file, source

    # ------------------------------------------------------------------ API cho Backend
    def resolve(self, image_path: object) -> ImageResult:
        """Kiểm tra một image_path của catalog; ảnh không dùng được -> ảnh thay thế."""
        if image_path is None or (isinstance(image_path, float) and image_path != image_path) \
                or not str(image_path).strip():
            return self._fallback(MISSING_PATH, None)
        requested = str(image_path)
        path = self._to_path(requested)
        reason = self.check_file(path)
        if reason == OK:
            return ImageResult(str(path), False, SOURCE_CATALOG, OK, requested)
        return self._fallback(reason, requested)

    def resolve_vehicle(self, manufacturer: object, model_base: object, year: object,
                        image_path: object = None) -> ImageResult:
        """Ảnh cho một xe: image_path của catalog trước, sau đó tìm theo hãng-dòng-năm."""
        first = self.resolve(image_path)
        if not first.is_placeholder:
            return first
        path, source = self.lookup(manufacturer, model_base, year)
        if path is not None and self.check_file(path) == OK:
            return ImageResult(str(path), False, source, first.reason, first.requested)
        return first

    def resolve_card(self, card: CarCard) -> ImageResult:
        return self.resolve_vehicle(card.manufacturer, card.model_base, card.year, card.image_path)

    def resolve_cards(self, cards: Iterable[CarCard]) -> list[ImageResult]:
        return [self.resolve_card(c) for c in cards]

    def with_images(self, cards: Iterable[CarCard]) -> list[CarCard]:
        """Trả bản sao các thẻ xe với image_path là đường dẫn tuyệt đối luôn mở được
        (ảnh minh họa hoặc ảnh thay thế). Các trường khác giữ nguyên."""
        return [replace(c, image_path=self.resolve_card(c).path) for c in cards]

    def clear_cache(self) -> None:
        """Xóa bộ đệm (dùng khi vừa thêm/xóa ảnh trong lúc ứng dụng đang chạy)."""
        with self._lock:
            self._checked.clear()
            self._index = None
            self._placeholder_ok = False


# Hàm tiện lợi cho Backend: tạo dịch vụ một lần cho cả phiên chạy
_DEFAULT: ImageService | None = None
_DEFAULT_LOCK = threading.Lock()


def get_image_service() -> ImageService:
    global _DEFAULT
    if _DEFAULT is None:
        with _DEFAULT_LOCK:
            if _DEFAULT is None:
                _DEFAULT = ImageService()
    return _DEFAULT


def get_image_path(image_path: object, manufacturer: object = None, model_base: object = None,
                   year: object = None) -> str:
    """Hàm ngắn cho Frontend/Backend: luôn trả một đường dẫn ảnh mở được."""
    service = get_image_service()
    if manufacturer is None:
        return service.resolve(image_path).path
    return service.resolve_vehicle(manufacturer, model_base, year, image_path).path
