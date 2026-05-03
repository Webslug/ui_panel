"""
gui.py — Command Editor (HQ)
QDialog table editor. Launched on tray icon double-click.
Reads from and writes back to store.py — never touches commands.json directly.
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLineEdit, QLabel, QMessageBox, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui  import QColor

import store


# ── Palette ───────────────────────────────────────────────────────────────────

STYLE = """
QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px;
}
QTableWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    gridline-color: #313244;
    selection-background-color: #45475a;
}
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section {
    background-color: #313244;
    color: #89b4fa;
    font-weight: bold;
    padding: 4px 8px;
    border: none;
}
QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus { border-color: #89b4fa; }
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 5px 14px;
    min-width: 80px;
}
QPushButton:hover  { background-color: #45475a; }
QPushButton:pressed { background-color: #585b70; }
QPushButton#btn_add    { color: #a6e3a1; border-color: #a6e3a1; }
QPushButton#btn_remove { color: #f38ba8; border-color: #f38ba8; }
QPushButton#btn_save   { color: #89b4fa; border-color: #89b4fa; }
QLabel { color: #a6adc8; }
QLabel#lbl_title {
    color: #89b4fa;
    font-size: 15px;
    font-weight: bold;
}
"""

COL_DISPLAY  = 0
COL_FULL     = 1
COL_TERMINAL = 2   # checkbox: needs a terminal window
COL_USES     = 3


# ── Main dialog ───────────────────────────────────────────────────────────────

class CommandEditor(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Panel — Command Editor")
        self.setMinimumSize(900, 520)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._populate_table()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Command Roster")
        title.setObjectName("lbl_title")
        root.addWidget(title)

        hint = QLabel("☑ Terminal — tick for interactive scripts (kobold, etc.) that need their own terminal window.")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # Table — 4 columns
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Display Label", "Full Command", "Terminal", "Uses"])
        self.table.horizontalHeader().setSectionResizeMode(COL_DISPLAY,  QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_FULL,     QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_TERMINAL, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_USES,     QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.table.verticalHeader().setVisible(False)
        root.addWidget(self.table)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.inp_full    = QLineEdit()
        self.inp_full.setPlaceholderText("Shell cmd or .desktop path  e.g.  bash /home/kim/Desktop/webstack.sh")

        self.inp_display = QLineEdit()
        self.inp_display.setPlaceholderText("Display label (optional — auto-shortened if blank)")

        btn_add = QPushButton("＋ Add")
        btn_add.setObjectName("btn_add")
        btn_add.clicked.connect(self._on_add)

        input_row.addWidget(QLabel("Command:"))
        input_row.addWidget(self.inp_full, stretch=3)
        input_row.addWidget(QLabel("Label:"))
        input_row.addWidget(self.inp_display, stretch=2)
        input_row.addWidget(btn_add)
        root.addLayout(input_row)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        btn_remove = QPushButton("✕ Remove Selected")
        btn_remove.setObjectName("btn_remove")
        btn_remove.clicked.connect(self._on_remove)

        btn_save = QPushButton("✔ Save Changes")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._on_save)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)

        btn_row.addWidget(btn_remove)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _populate_table(self):
        self.table.setRowCount(0)
        for rec in store.load_all():
            self._append_row(
                rec.get("display", ""),
                rec.get("full", ""),
                bool(rec.get("terminal", False)),
                str(rec.get("uses", 0))
            )

    def _append_row(self, display: str, full: str, terminal: bool = False, uses: str = "0"):
        row = self.table.rowCount()
        self.table.insertRow(row)

        item_display = QTableWidgetItem(display)
        item_full    = QTableWidgetItem(full)

        # Terminal checkbox — centred, checkable, not text-editable
        item_term = QTableWidgetItem()
        item_term.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        item_term.setCheckState(Qt.Checked if terminal else Qt.Unchecked)
        item_term.setTextAlignment(Qt.AlignCenter)

        item_uses = QTableWidgetItem(uses)
        item_uses.setFlags(item_uses.flags() & ~Qt.ItemIsEditable)
        item_uses.setTextAlignment(Qt.AlignCenter)
        item_uses.setForeground(QColor("#fab387"))

        self.table.setItem(row, COL_DISPLAY,  item_display)
        self.table.setItem(row, COL_FULL,     item_full)
        self.table.setItem(row, COL_TERMINAL, item_term)
        self.table.setItem(row, COL_USES,     item_uses)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_add(self):
        full    = self.inp_full.text().strip()
        display = self.inp_display.text().strip()
        if not full:
            QMessageBox.warning(self, "Empty Command", "Full command cannot be blank.")
            return
        store.add_command(full, display or None)
        self._append_row(display or store._shorten(full), full, False, "0")
        self.inp_full.clear()
        self.inp_display.clear()

    def _on_remove(self):
        if not self.table.selectedItems():
            QMessageBox.information(self, "Nothing Selected", "Select a row to remove.")
            return
        row  = self.table.currentRow()
        full = self.table.item(row, COL_FULL).text()
        confirm = QMessageBox.question(
            self, "Confirm Remove", f"Remove:\n{full}",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            store.remove_command(full)
            self.table.removeRow(row)

    def _on_save(self):
        records    = store.load_all()
        full_index = {rec["full"]: rec for rec in records}
        new_records = []

        for row in range(self.table.rowCount()):
            display  = self.table.item(row, COL_DISPLAY).text().strip()
            full     = self.table.item(row, COL_FULL).text().strip()
            terminal = self.table.item(row, COL_TERMINAL).checkState() == Qt.Checked

            if not full:
                continue

            existing = full_index.get(full)
            new_records.append({
                "display":   display or store._shorten(full),
                "full":      full,
                "terminal":  terminal,
                "uses":      existing["uses"]      if existing else 0,
                "last_used": existing["last_used"] if existing else None,
            })

        store._save_raw(new_records)
        QMessageBox.information(self, "Saved", "Command roster updated.")


# ── Entry point ───────────────────────────────────────────────────────────────

def launch():
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = CommandEditor()
    dlg.exec_()

if __name__ == "__main__":
    launch()
