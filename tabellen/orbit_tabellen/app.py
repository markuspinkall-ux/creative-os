"""Tabellen-Ansicht: Excel-Dateien ansehen (nur lesen). Öffnet sich per Doppelklick auf eine .xlsx.

    orbit-tabellen datei.xlsx
"""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QKeySequence, QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSlider, QStyledItemDelegate,
                               QTabBar, QTableView, QToolButton, QVBoxLayout, QWidget)

from . import xlsxdata

APP = "Tabellen-Ansicht"
EXTS = (".xlsx", ".xlsm", ".xltx", ".xltm")

# Graphit (wie das System)
GROUND, SURFACE, RAISED = "#12151b", "#1c2029", "#232836"
TEXT, MUTED, ACCENT, ACCENT_TEXT = "#dce6ff", "#9aa6c0", "#8fb3ff", "#12151b"
HAIRLINE = "rgba(220,230,255,0.10)"

STYLE = f"""
QMainWindow, QWidget#root {{ background: {GROUND}; }}
QWidget {{ color: {TEXT}; font-family: Arial, Helvetica, sans-serif; font-size: 13px; }}
QFrame#bar {{ background: {SURFACE}; border-bottom: 1px solid {HAIRLINE}; }}
QFrame#foot {{ background: {SURFACE}; border-top: 1px solid {HAIRLINE}; }}
QLabel#title {{ font-size: 15px; font-weight: bold; }}
QLabel#muted, QLabel#status {{ color: {MUTED}; font-size: 12px; }}
QLabel#cellname {{ background: {RAISED}; border-radius: 8px; padding: 0 10px; font-weight: bold; min-width: 56px; }}
QLineEdit {{ background: {RAISED}; border: 1px solid {HAIRLINE}; border-radius: 8px; padding: 5px 10px;
             selection-background-color: {ACCENT}; selection-color: {ACCENT_TEXT}; }}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit#formula {{ font-family: "DejaVu Sans Mono", monospace; }}
QPushButton, QToolButton {{ background: rgba(220,230,255,0.06); border: 0; border-radius: 9px; padding: 7px 14px; }}
QPushButton:hover, QToolButton:hover {{ background: rgba(220,230,255,0.12); }}
QPushButton#primary {{ background: {ACCENT}; color: {ACCENT_TEXT}; font-weight: bold; }}
QTabBar::tab {{ background: transparent; color: {MUTED}; padding: 7px 16px; margin: 6px 2px; border-radius: 8px; }}
QTabBar::tab:selected {{ background: rgba(143,179,255,0.18); color: {TEXT}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ background: rgba(220,230,255,0.06); }}
QSlider::groove:horizontal {{ height: 4px; background: rgba(220,230,255,0.15); border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
QTableView {{ background: #ffffff; color: #000000; gridline-color: #d9dde5; border: 0;
              selection-background-color: rgba(143,179,255,0.35); selection-color: #000000; font-size: 13px; }}
QHeaderView::section {{ background: {RAISED}; color: {MUTED}; border: 0; border-right: 1px solid {HAIRLINE};
                        border-bottom: 1px solid {HAIRLINE}; padding: 0 4px; font-size: 12px; }}
QTableCornerButton::section {{ background: {RAISED}; border: 0; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {SURFACE}; width: 12px; height: 12px; }}
QScrollBar::handle {{ background: rgba(220,230,255,0.22); border-radius: 5px; min-height: 30px; min-width: 30px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
"""


class SheetModel(QAbstractTableModel):
    def __init__(self, sheet, zoom=1.0):
        super().__init__()
        self.sheet = sheet
        self.zoom = zoom
        self._fonts = {}

    # wie in Excel: hinter den Daten noch leere Zeilen und Spalten
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.sheet.rows + 40

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else max(self.sheet.cols + 8, 12)

    def cell(self, r, c):
        return self.sheet.cells.get((r, c))

    def _font(self, cell):
        key = (cell.bold, cell.italic, cell.underline, cell.strike, cell.size, self.zoom)
        f = self._fonts.get(key)
        if f is None:
            f = QFont("Arial")
            f.setPointSizeF(max(5.0, cell.size * self.zoom * 0.92))
            f.setBold(cell.bold)
            f.setItalic(cell.italic)
            f.setUnderline(cell.underline or False)
            f.setStrikeOut(cell.strike)
            self._fonts[key] = f
        return f

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        cell = self.cell(index.row(), index.column())
        if cell is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return cell.text
        if role == Qt.ItemDataRole.FontRole:
            return self._font(cell)
        if role == Qt.ItemDataRole.ForegroundRole:
            if cell.link and not cell.color:
                return QColor("#0563c1")
            return QColor(cell.color) if cell.color else None
        if role == Qt.ItemDataRole.BackgroundRole:
            return QColor(cell.fill) if cell.fill else None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            h = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                 "right": Qt.AlignmentFlag.AlignRight}.get(cell.align)
            if h is None:
                h = Qt.AlignmentFlag.AlignRight if cell.number else Qt.AlignmentFlag.AlignLeft
            v = {"top": Qt.AlignmentFlag.AlignTop, "center": Qt.AlignmentFlag.AlignVCenter}.get(
                cell.valign, Qt.AlignmentFlag.AlignBottom)
            return int(h | v)
        if role == Qt.ItemDataRole.ToolTipRole:
            tip = []
            if cell.formula:
                tip.append(cell.formula + ("  (nachgerechnet)" if cell.computed else ""))
            if cell.link:
                tip.append("Link: " + cell.link + " – Doppelklick öffnet")
            return "\n".join(tip) or None
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                from openpyxl.utils import get_column_letter
                return get_column_letter(section + 1)
            return str(section + 1)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class WrapDelegate(QStyledItemDelegate):
    """Zeilenumbruch nur in Zellen, die ihn in Excel haben; sonst einzeilig (läuft nicht über)."""

    def __init__(self, model_getter, parent=None):
        super().__init__(parent)
        self._model = model_getter

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        model = self._model()
        cell = model.cell(index.row(), index.column()) if model else None
        from PySide6.QtWidgets import QStyleOptionViewItem
        if cell is not None and cell.wrap:
            option.features |= QStyleOptionViewItem.ViewItemFeature.WrapText
        else:
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.WrapText
            option.textElideMode = Qt.TextElideMode.ElideNone


class Viewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.book = None
        self.model = None
        self.zoom = 1.0
        self.setWindowTitle(APP)
        self.setWindowIcon(QIcon.fromTheme("orbit-tabellen"))
        self.resize(1180, 760)
        self.setAcceptDrops(True)

        root = QWidget(objectName="root")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.setCentralWidget(root)

        # Kopfzeile
        bar = QFrame(objectName="bar")
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.title = QLabel(APP, objectName="title")
        self.info = QLabel("", objectName="muted")
        top.addWidget(self.title)
        top.addWidget(self.info)
        top.addStretch(1)
        self.search = QLineEdit(placeholderText="Suchen (Strg+F)")
        self.search.setFixedWidth(240)
        self.search.returnPressed.connect(self.find_next)
        top.addWidget(self.search)
        btn_copy = QPushButton("Kopieren")
        btn_copy.setToolTip("Markierte Zellen kopieren (Strg+C)")
        btn_copy.clicked.connect(self.copy)
        top.addWidget(btn_copy)
        btn_open = QPushButton("Öffnen …", objectName="primary")
        btn_open.clicked.connect(self.choose)
        top.addWidget(btn_open)
        bl.addLayout(top)
        fl = QHBoxLayout()
        fl.setSpacing(8)
        self.cellname = QLabel("", objectName="cellname")
        self.cellname.setFixedHeight(30)
        self.cellname.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fx = QLabel("fx", objectName="muted")
        self.formula = QLineEdit(objectName="formula")
        self.formula.setReadOnly(True)
        self.formula.setPlaceholderText("Inhalt der markierten Zelle")
        fl.addWidget(self.cellname)
        fl.addWidget(fx)
        fl.addWidget(self.formula, 1)
        bl.addLayout(fl)
        lay.addWidget(bar)

        # Tabelle
        self.table = QTableView()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setWordWrap(True)
        self.table.setItemDelegate(WrapDelegate(lambda: self.model, self.table))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(4)
        self.table.verticalHeader().setMinimumSectionSize(4)
        self.table.doubleClicked.connect(self.open_link)
        lay.addWidget(self.table, 1)

        # Leere Ansicht
        self.empty = QLabel("Excel-Datei hierher ziehen oder „Öffnen …“ wählen", objectName="muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet("font-size: 15px;")
        lay.addWidget(self.empty, 1)

        # Fußzeile: Blätter, Auswertung, Zoom
        foot = QFrame(objectName="foot")
        ft = QHBoxLayout(foot)
        ft.setContentsMargins(10, 0, 16, 0)
        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.currentChanged.connect(self.show_sheet)
        ft.addWidget(self.tabs, 1)
        self.status = QLabel("", objectName="status")
        ft.addWidget(self.status)
        ft.addSpacing(14)
        zo = QToolButton(text="−")
        zo.clicked.connect(lambda: self.slider.setValue(self.slider.value() - 10))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(30, 300)
        self.slider.setValue(100)
        self.slider.setFixedWidth(120)
        self.slider.valueChanged.connect(self.set_zoom)
        zi = QToolButton(text="+")
        zi.clicked.connect(lambda: self.slider.setValue(self.slider.value() + 10))
        self.zlabel = QLabel("100 %", objectName="status")
        self.zlabel.setFixedWidth(48)
        for w in (zo, self.slider, zi, self.zlabel):
            ft.addWidget(w)
        foot.setFixedHeight(48)
        lay.addWidget(foot)

        for seq, fn in ((QKeySequence.StandardKey.Copy, self.copy), (QKeySequence.StandardKey.Find, self.search.setFocus),
                        (QKeySequence.StandardKey.Open, self.choose), (QKeySequence.StandardKey.ZoomIn, lambda: self.slider.setValue(self.slider.value() + 10)),
                        (QKeySequence.StandardKey.ZoomOut, lambda: self.slider.setValue(self.slider.value() - 10)),
                        (QKeySequence("F3"), self.find_next), (QKeySequence("Ctrl+0"), lambda: self.slider.setValue(100))):
            a = QAction(self)
            a.setShortcut(seq)
            a.triggered.connect(fn)
            self.addAction(a)
        self.table.hide()
        self._find_pos = None
        QTimer.singleShot(0, lambda: (self.table if self.book else root).setFocus())

    # ---- Datei --------------------------------------------------------------------------------
    def choose(self):
        start = str(Path(self.book.path).parent) if self.book else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Excel-Datei öffnen", start, "Excel-Dateien (*.xlsx *.xlsm *.xltx *.xltm)")
        if path:
            self.open(path)

    def open(self, path):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            book = xlsxdata.load(path)
        except ValueError as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, APP, str(exc))
            return False
        QApplication.restoreOverrideCursor()
        self.book = book
        name = Path(path).name
        self.setWindowTitle(f"{name} – {APP}")
        self.title.setText(name)
        extra = []
        if book.charts:
            extra.append(f"{book.charts} Diagramm{'e' if book.charts > 1 else ''}")
        if book.images:
            extra.append(f"{book.images} Bild{'er' if book.images > 1 else ''}")
        self.info.setText("Nur ansehen" + (" · " + ", ".join(extra) + " werden nicht angezeigt" if extra else ""))
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        for sh in book.sheets:
            i = self.tabs.addTab(sh.name)
            if sh.state != "visible":
                self.tabs.setTabVisible(i, False)
        self.tabs.blockSignals(False)
        self.empty.hide()
        self.table.show()
        self.tabs.setCurrentIndex(book.active)
        self.show_sheet(book.active)
        self.table.setFocus()
        return True

    def show_sheet(self, i):
        if not self.book or i < 0 or i >= len(self.book.sheets):
            return
        sh = self.book.sheets[i]
        self.model = SheetModel(sh, self.zoom)
        self.table.setModel(self.model)
        self.table.clearSpans()
        for r, c, rs, cs in sh.merged:
            if rs > 1 or cs > 1:
                self.table.setSpan(r, c, rs, cs)
        self.apply_sizes()
        for r in sh.hidden_rows:
            self.table.setRowHidden(r, True)
        for c in sh.hidden_cols:
            self.table.setColumnHidden(c, True)
        self.table.selectionModel().selectionChanged.connect(self.selection_changed)
        self.table.setCurrentIndex(self.model.index(0, 0))
        self._find_pos = None
        self.selection_changed()

    def apply_sizes(self):
        sh = self.model.sheet
        z = self.zoom
        default_h = sh.heights.get(-1, 20)
        for c in range(self.model.columnCount()):
            self.table.setColumnWidth(c, int(sh.widths.get(c, 64) * z))
        vh = self.table.verticalHeader()
        vh.setDefaultSectionSize(max(6, int(default_h * z)))
        for r, h in sh.heights.items():
            if r >= 0:
                self.table.setRowHeight(r, max(6, int(h * z)))
        vh.setFixedWidth(max(36, int((len(str(self.model.rowCount())) * 8 + 16) * min(z, 1.4))))

    def set_zoom(self, value):
        self.zoom = value / 100
        self.zlabel.setText(f"{value} %")
        if self.model:
            self.model.zoom = self.zoom
            self.model._fonts.clear()
            self.apply_sizes()
            self.model.layoutChanged.emit()

    # ---- Auswahl, Kopieren, Suchen, Links --------------------------------------------------------
    def selection_changed(self, *_):
        if not self.model:
            return
        idx = self.table.currentIndex()
        if idx.isValid():
            cell = self.model.cell(idx.row(), idx.column())
            self.cellname.setText(xlsxdata.cell_name(idx.row(), idx.column()))
            self.formula.setText((cell.formula or cell.text) if cell else "")
            self.formula.setCursorPosition(0)
        nums = []
        count = 0
        for i in self.table.selectedIndexes()[:200000]:
            cell = self.model.cell(i.row(), i.column())
            if cell and cell.text:
                count += 1
                if cell.number and isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                    nums.append(float(cell.value))
        sh = self.model.sheet
        size = f"{sh.rows} Zeilen × {sh.cols} Spalten" + (" (gekürzt)" if sh.truncated else "")
        if len(nums) > 1:
            fmt = lambda v: xlsxdata.format_value(v, "#,##0.00")
            self.status.setText(f"Summe: {fmt(sum(nums))}   Mittelwert: {fmt(sum(nums) / len(nums))}   Anzahl: {count}")
        elif count > 1:
            self.status.setText(f"Anzahl: {count}")
        else:
            self.status.setText(size)

    def copy(self):
        if not self.model:
            return
        idxs = self.table.selectedIndexes()
        if not idxs:
            return
        rows = sorted({i.row() for i in idxs})
        cols = sorted({i.column() for i in idxs})
        chosen = {(i.row(), i.column()) for i in idxs}
        lines = []
        for r in rows:
            out = []
            for c in cols:
                cell = self.model.cell(r, c) if (r, c) in chosen else None
                out.append((cell.text if cell else "").replace("\t", " ").replace("\n", " "))
            lines.append("\t".join(out))
        QGuiApplication.clipboard().setText("\n".join(lines))
        self.status.setText(f"{len(chosen)} Zelle{'n' if len(chosen) > 1 else ''} kopiert")

    def find_next(self):
        text = self.search.text().strip().lower()
        if not text or not self.model:
            return
        keys = sorted(k for k, c in self.model.sheet.cells.items() if text in c.text.lower() or text in c.formula.lower())
        if not keys:
            self.status.setText(f"„{self.search.text()}“ nicht gefunden")
            return
        cur = self._find_pos
        nxt = next((k for k in keys if cur is None or k > cur), keys[0])
        self._find_pos = nxt
        idx = self.model.index(*nxt)
        self.table.setCurrentIndex(idx)
        self.table.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.status.setText(f"Treffer {keys.index(nxt) + 1} von {len(keys)}")

    def open_link(self, index):
        cell = self.model.cell(index.row(), index.column()) if self.model else None
        if cell and cell.link and cell.link.lower().startswith(("http://", "https://", "mailto:")):
            QDesktopServices.openUrl(QUrl(cell.link))

    # ---- Ziehen und Ablegen ------------------------------------------------------------------
    def dragEnterEvent(self, e):
        if any(u.toLocalFile().lower().endswith(EXTS) for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.toLocalFile().lower().endswith(EXTS):
                self.open(u.toLocalFile())
                break


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName(APP)
    app.setDesktopFileName("orbit-tabellen")
    app.setStyleSheet(STYLE)
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(GROUND))
    app.setPalette(pal)
    win = Viewer()
    files = [a for a in argv[1:] if not a.startswith("-")]
    for a in files:
        if a.startswith("file://"):
            a = QUrl(a).toLocalFile()
        if os.path.isfile(a):
            win.open(a)
            break
    shot = next((a.split("=", 1)[1] for a in argv if a.startswith("--screenshot=")), "")
    if "--selftest" in argv:
        ok = win.book is not None and win.model is not None and win.model.rowCount() > 0
        print("Tabellen-Ansicht: Selbsttest", "bestanden" if ok else "FEHLGESCHLAGEN")
        return 0 if ok else 1
    win.show()
    if shot:
        def grab():
            if "--auswahl" in argv and win.model:
                from PySide6.QtCore import QItemSelection, QItemSelectionModel
                sel = QItemSelection(win.model.index(3, 1), win.model.index(8, 2))
                win.table.selectionModel().select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                win.table.setCurrentIndex(win.model.index(3, 3))
                win.table.selectionModel().select(sel, QItemSelectionModel.SelectionFlag.Select)
                win.selection_changed()
            QTimer.singleShot(400, lambda: (win.grab().save(shot), app.quit()))
        QTimer.singleShot(800, grab)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
