"""Sơ đồ tuần tự (sequence diagram) của luồng 'Ước tính giá và tìm xe' - vẽ bằng matplotlib."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

RED, INK, MUTED = "#D7263D", "#18181B", "#6B6B74"
ACTORS = ["Người dùng", "AutoWise\nMainWindowEx", "Vehicle\nController", "app_service", "prediction\n_service",
          "recommendation\n_service", "SearchDao\n(SQLite)"]
STEPS = [(0, 1, "nhập form, bấm ANALYZE"), (1, 2, "validatedInput()"), (2, 2, "kiểm tra ô bắt buộc, dòng xe,\nsố dặm hợp lý"),
         (2, 1, "VehicleInput", True), (1, 3, "analyze(form)"), (3, 3, "VehicleInput.check()"),
         (3, 4, "predict_vehicle_price()"), (4, 3, "PriceResult (giá, khoảng 80%)", True), (3, 5, "recommend(ngân sách, sở thích)"),
         (5, 3, "Top 5 + điểm match", True), (3, 3, "xe cùng mức giá, ảnh, cảnh báo"), (3, 1, "AnalysisResult", True),
         (1, 6, "save(user_id, vehicle, result)"), (6, 1, "search_id", True), (1, 0, "hiển thị Màn hình kết quả", True)]


def main(out):
    plt.rcParams["font.family"] = "Inter"
    gap, step = 2.3, 0.62
    n = len(STEPS)
    H = 1.6 + n * step
    fig, ax = plt.subplots(figsize=(len(ACTORS) * gap * 0.95, H * 0.95), dpi=170)
    ax.set_xlim(-1.2, (len(ACTORS) - 1) * gap + 1.2)
    ax.set_ylim(-H, 0.9)
    ax.axis("off")
    for i, a in enumerate(ACTORS):
        x = i * gap
        ax.add_patch(FancyBboxPatch((x - 0.95, -0.15), 1.9, 0.85, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=RED if i == 0 else INK, ec="none"))
        ax.text(x, 0.28, a, ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        ax.plot([x, x], [-0.2, -H + 0.2], color="#BDBDC5", lw=1, ls=(0, (4, 3)))
    for k, s in enumerate(STEPS):
        a, b, text = s[:3]
        back = len(s) > 3
        y = -0.75 - k * step
        xa, xb = a * gap, b * gap
        if a == b:
            ax.add_patch(Rectangle((xa - 0.06, y - 0.32), 0.12, 0.42, fc="#FDE8EB", ec=RED, lw=0.8))
            ax.annotate("", xy=(xa + 0.08, y - 0.25), xytext=(xa + 0.08, y + 0.05),
                        arrowprops=dict(arrowstyle="-|>", color=RED, connectionstyle="arc3,rad=-1.4", lw=1))
            ax.text(xa + 0.45, y - 0.1, f"{k + 1}. {text}", fontsize=8, color=INK, va="center")
        else:
            ax.annotate("", xy=(xb, y), xytext=(xa, y),
                        arrowprops=dict(arrowstyle="-|>", color=MUTED if back else INK, lw=1, ls="--" if back else "-"))
            ax.text((xa + xb) / 2, y + 0.08, f"{k + 1}. {text}", fontsize=8, color=MUTED if back else INK, ha="center", va="bottom")
    fig.savefig(out, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    main(Path(__file__).with_name("09_tuan_tu_phan_tich.png"))
