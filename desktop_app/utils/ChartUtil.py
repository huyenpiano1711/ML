"""
ChartUtil.py - Matplotlib charts inside PyQt6 widgets (FigureCanvasQTAgg), in the AutoWise colours.
"""
import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

RED, RED_LIGHT, INK, MUTED, GRID, GREEN = "#D7263D", "#F5A3AF", "#18181B", "#6B6B74", "#ECECEF", "#16A34A"
PALETTE = ["#D7263D", "#18181B", "#F59E0B", "#2563EB", "#16A34A", "#7C3AED", "#0891B2", "#DB2777", "#65A30D", "#78716C",
           "#EA580C", "#4F46E5"]


class ChartUtil:
    @staticmethod
    def canvas(layout, height=2.8):
        """Remove the old chart of this layout and put a new empty one. Returns (figure, canvas)."""
        while layout.count():
            widget = layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        fig = Figure(figsize=(6, height), dpi=100, facecolor="white")
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(int(height * 90))
        layout.addWidget(canvas)
        return fig, canvas

    @staticmethod
    def style(ax, title=None):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#D4D4DA")
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        if title:
            ax.set_title(title, fontsize=9, color=INK, loc="left")
        return ax

    @staticmethod
    def money_axis(axis):
        from matplotlib.ticker import FuncFormatter
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"${v / 1000:,.0f}k" if abs(v) >= 1000 else f"${v:,.0f}"))

    @staticmethod
    def empty(layout, text="No data yet"):
        fig, canvas = ChartUtil.canvas(layout)
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", color=MUTED, fontsize=10)
        canvas.draw()
        return fig, canvas
