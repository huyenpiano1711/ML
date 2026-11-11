"""
TableUtil.py - Fill a QTableWidget from rows (same idea as showDataIntoTableWidget in the course exercises).
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem


class TableUtil:
    @staticmethod
    def fill(table: QTableWidget, rows, align_right=(), stretch_col=None, data_col=0):
        """rows: list of lists (display text). The value of column data_col is kept in UserRole of each row's
        first item, so the selected row can be found again after sorting."""
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem("" if value is None else str(value))
                if c in align_right:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row[data_col])
                table.setItem(r, c, item)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if stretch_col is not None:
            header.setSectionResizeMode(stretch_col, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(True)

    @staticmethod
    def selectedKey(table: QTableWidget):
        """UserRole value of the selected row (see fill), or None."""
        row = table.currentRow()
        if row < 0 or table.item(row, 0) is None or not table.selectionModel().hasSelection():
            return None
        return table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    @staticmethod
    def colorCell(table: QTableWidget, row, col, fg=None, bg=None, bold=False):
        item = table.item(row, col)
        if item is None:
            return
        if fg:
            item.setForeground(QColor(fg))
        if bg:
            item.setBackground(QColor(bg))
        if bold:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
