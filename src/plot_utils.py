"""
plot_utils.py - Hàm vẽ biểu đồ dùng chung (matplotlib), cùng một phong cách:
nền sáng, lưới mờ, nét mảnh, 1 màu chính cho 1 chuỗi dữ liệu.
Mọi biểu đồ đều lưu ra PNG (dpi 150) để chèn thẳng vào báo cáo Word.
"""
import matplotlib

matplotlib.use("Agg")  # vẽ ra file, không cần mở cửa sổ (chạy được trong PyCharm/terminal)
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# Bảng màu (đã kiểm định cho người mù màu) - dùng theo đúng thứ tự
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
TEXT, TEXT_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2,
    "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlecolor": TEXT,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "font.size": 9.5, "savefig.dpi": 150, "savefig.bbox": "tight",
})

usd = mticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
thousands = mticker.FuncFormatter(lambda x, _: f"{x:,.0f}")


def save(fig, path):
    fig.savefig(path)
    plt.close(fig)
    print(f"   -> đã lưu {path.name}")


def barh(series, title, path, xlabel="Số tin đăng", fmt=thousands, color=BLUE,
         annotate=True, figsize=(8, None), sort=True):
    """Biểu đồ cột ngang, sắp xếp giảm dần (sort=False: giữ thứ tự, phần tử đầu ở trên cùng)."""
    s = series.sort_values() if sort else series.iloc[::-1]
    h = figsize[1] or max(2.5, 0.32 * len(s) + 1)
    fig, ax = plt.subplots(figsize=(figsize[0], h))
    ax.barh(s.index.astype(str), s.values, color=color, height=0.7)
    ax.set_title(title, loc="left")
    ax.set_xlabel(xlabel)
    ax.xaxis.set_major_formatter(fmt)
    ax.grid(axis="y", visible=False)
    if annotate:
        xmax = s.max()
        for i, v in enumerate(s.values):
            ax.text(v + xmax * 0.01, i, fmt(v, None), va="center", fontsize=8, color=TEXT_2)
        ax.set_xlim(0, xmax * 1.15)
    save(fig, path)


def hist(values, title, path, bins=60, xlabel="", log_x=False, fmt=None, color=BLUE,
         vlines=None):
    """Histogram; vlines = {nhãn: giá_trị} để đánh dấu ngưỡng làm sạch."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    if log_x:
        v = v[v > 0]
        bins = np.logspace(np.log10(v.min()), np.log10(v.max()), bins)
        ax.set_xscale("log")
    ax.hist(v, bins=bins, color=color, edgecolor=SURFACE, linewidth=0.4)
    ax.set_title(title, loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Số tin đăng")
    ax.yaxis.set_major_formatter(thousands)
    if fmt is not None:
        ax.xaxis.set_major_formatter(fmt)
    for label, x in (vlines or {}).items():
        ax.axvline(x, color=ORANGE, linewidth=1.5, linestyle="--")
        ax.text(x, ax.get_ylim()[1] * 0.95, f" {label}", color=ORANGE, fontsize=8, va="top")
    save(fig, path)
