"""Graphit-Dialoge für die Qt-Widgets-Apps von Creative OS.

Ersetzt die Standard-Dialoge von Qt durch Dialoge im Creative-Look – mit
genau denselben Aufrufen. Eine App braucht dafür nur eine Zeile:

    from creative_dialogs import QColorDialog, QFileDialog, QInputDialog, QMessageBox

Die Klassen erben von den Qt-Klassen; alle Aufzählungen wie
``QMessageBox.StandardButton.Yes`` bleiben also gleich. Ersetzt werden die
statischen Aufrufe (getOpenFileName, question, getText, getColor …).

Selbsttest beim Bauen:  python3 -m creative_dialogs --selftest
"""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QDir, QRect, QRectF, QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImageReader, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut
from PySide6.QtWidgets import QColorDialog as _QColorDialog
from PySide6.QtWidgets import QFileDialog as _QFileDialog
from PySide6.QtWidgets import QInputDialog as _QInputDialog
from PySide6.QtWidgets import QMessageBox as _QMessageBox
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFileSystemModel, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListView, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
    QSpinBox, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

C = {
    "ground": "#12151b", "surface": "#1c2029", "raised": "#232836", "track": "#3a4252",
    "line": "#2c3242", "text": "#dce6ff", "muted": "#9aa6c4", "accent": "#8fb3ff",
    "accentHover": "#a6c3ff", "accentText": "#12151b", "flame": "#ffb07a",
    "danger": "#e5484d", "dangerHover": "#ec5d62", "dangerBg": "#3a1d22", "dangerText": "#ff8a8e",
    "infoBg": "#23304a",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_last_dir = {"path": ""}

STYLE = f"""
QDialog#creativeDialog {{ background: transparent; }}
QFrame#card {{ background: {C['surface']}; border: 1px solid {C['line']}; border-radius: 18px; }}
QFrame#card * {{ font-family: "Arial", "Liberation Sans"; font-size: 13px; color: {C['text']}; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 16px; font-weight: bold; }}
QLabel#text, QLabel#muted {{ color: {C['muted']}; }}
QLabel#path {{ background: {C['ground']}; border-radius: 10px; padding: 7px 12px; color: {C['muted']}; }}
QPushButton {{ background: {C['raised']}; border: none; border-radius: 10px; padding: 8px 18px; min-height: 18px; }}
QPushButton:hover {{ background: {C['track']}; }}
QPushButton:focus {{ outline: none; }}
QPushButton#primary {{ background: {C['accent']}; color: {C['accentText']}; font-weight: bold; }}
QPushButton#primary:hover {{ background: {C['accentHover']}; }}
QPushButton#danger {{ background: {C['danger']}; color: white; font-weight: bold; }}
QPushButton#danger:hover {{ background: {C['dangerHover']}; }}
QPushButton#icon {{ padding: 0; min-width: 34px; max-width: 34px; min-height: 34px; max-height: 34px; font-size: 16px; }}
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
    background: {C['ground']}; border: 1px solid {C['line']}; border-radius: 10px; padding: 7px 10px;
    selection-background-color: {C['accent']}; selection-color: {C['accentText']}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {C['accent']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {C['raised']}; border: 1px solid {C['line']}; border-radius: 10px;
    selection-background-color: {C['accent']}; selection-color: {C['accentText']}; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
QListWidget#places {{ background: transparent; border: none; outline: none; }}
QListWidget#places::item {{ border-radius: 10px; padding: 7px 10px; margin: 1px 0; }}
QListWidget#places::item:hover {{ background: {C['raised']}; }}
QListWidget#places::item:selected {{ background: {C['accent']}; color: {C['accentText']}; font-weight: bold; }}
QListView#files {{ background: {C['ground']}; border: none; border-radius: 0; outline: none; padding: 8px; }}
QFrame#sep {{ background: {C['line']}; max-height: 1px; min-height: 1px; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {C['track']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QColorDialog {{ background: transparent; }}
"""


def _icon(name):
    for base in (Path(__file__).resolve().parent.parent / "shell" / "creative_shell" / "qml" / "Creative" / "icons",
                 Path("/usr/lib/creative-shell/creative_shell/qml/Creative/icons")):
        path = base / f"{name}.svg"
        if path.exists():
            return QIcon(str(path))
    return QIcon()


def _danger_words(*texts):
    text = " ".join(t or "" for t in texts).lower()
    return any(word in text for word in ("löschen", "entfernen", "verwerfen", "ersetzen", "überschreiben"))


class _Dialog(QDialog):
    """Rahmenloses Graphit-Fenster mit Titel, Inhalt und Knopfleiste."""

    def __init__(self, parent, title):
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(title or QApplication.applicationDisplayName())
        self.setModal(True)
        self.setObjectName("creativeDialog")
        self.setStyleSheet(STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame(objectName="card")
        outer.addWidget(self.card)
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(22, 18, 22, 18)
        self.body.setSpacing(14)
        self.title = QLabel(title or "", objectName="title")
        self.title.setWordWrap(True)
        self.footer = QHBoxLayout()
        self.footer.setSpacing(10)
        self._drag = None

    def add_title(self):
        self.body.addWidget(self.title)

    def add_footer(self):
        self.body.addLayout(self.footer)

    def button(self, text, kind="", slot=None):
        btn = QPushButton(text, objectName=kind)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setAutoDefault(False)
        if slot:
            btn.clicked.connect(slot)
        return btn

    # Fenster am Rand verschieben (auch unter Wayland)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 56:
            handle = self.windowHandle()
            if handle and handle.startSystemMove():
                return
            self._drag = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)


# ── Rückfragen und Hinweise ────────────────────────────────────────────────

SB = _QMessageBox.StandardButton
_LABELS = [
    (SB.Ok, "OK", "accept"), (SB.Save, "Speichern", "accept"), (SB.SaveAll, "Alle speichern", "accept"),
    (SB.Open, "Öffnen", "accept"), (SB.Yes, "Ja", "accept"), (SB.YesToAll, "Ja, alle", "accept"),
    (SB.Apply, "Anwenden", "accept"), (SB.Retry, "Wiederholen", "accept"),
    (SB.Discard, "Nicht speichern", "destructive"), (SB.Reset, "Zurücksetzen", "destructive"),
    (SB.RestoreDefaults, "Standard", "destructive"), (SB.Ignore, "Ignorieren", "reject"),
    (SB.No, "Nein", "reject"), (SB.NoToAll, "Nein, keine", "reject"), (SB.Abort, "Abbrechen", "reject"),
    (SB.Close, "Schließen", "reject"), (SB.Cancel, "Abbrechen", "reject"), (SB.Help, "Hilfe", "reject"),
]


class _MessageDialog(_Dialog):
    KINDS = {  # Zeichen, Hintergrund, Farbe
        "question": ("?", C["infoBg"], C["accent"]),
        "information": ("i", C["infoBg"], C["accent"]),
        "warning": ("!", C["dangerBg"], C["dangerText"]),
        "critical": ("!", C["dangerBg"], C["dangerText"]),
    }

    def __init__(self, parent, kind, title, text, buttons, default):
        super().__init__(parent, title)
        self.result_button = SB.NoButton
        self.setMinimumWidth(400)
        self.setMaximumWidth(620)
        row = QHBoxLayout()
        row.setSpacing(14)
        glyph, bg, fg = self.KINDS.get(kind, self.KINDS["information"])
        badge = QLabel(glyph)
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 20px; font-size: 20px; font-weight: bold;")
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(8)
        col.addWidget(self.title)
        text = str(text or "")
        if len(text) > 700 or text.count("\n") > 14:
            view = QPlainTextEdit(text)
            view.setReadOnly(True)
            view.setMinimumHeight(220)
            col.addWidget(view)
        else:
            label = QLabel(text, objectName="text")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setTextFormat(Qt.TextFormat.AutoText)
            col.addWidget(label)
        row.addLayout(col, 1)
        self.body.addLayout(row)

        chosen = [(flag, label, role) for flag, label, role in _LABELS if buttons & flag]
        if not chosen:
            chosen = [(SB.Ok, "OK", "accept")]
        accept = [c for c in chosen if c[2] == "accept"]
        primary = default if default not in (None, SB.NoButton) and any(c[0] == default for c in chosen) \
            else (accept[0][0] if accept else chosen[0][0])
        danger = kind == "question" and _danger_words(title, text) and primary in (SB.Yes, SB.Ok)
        self.escape = next((c[0] for c in chosen if c[0] in (SB.Cancel, SB.Close, SB.Abort)), None) \
            or next((c[0] for c in chosen if c[0] in (SB.No, SB.NoToAll)), None) \
            or (chosen[0][0] if len(chosen) == 1 else None)
        order = sorted(chosen, key=lambda c: {"destructive": 0, "reject": 1, "accept": 2}[c[2]] + (3 if c[0] == primary else 0))
        self.footer.addStretch(1)
        for flag, label, role in order:
            kind_name = ("danger" if danger else "primary") if flag == primary else ""
            btn = self.button(label, kind_name, lambda _=False, f=flag: self.pick(f))
            self.footer.addWidget(btn)
            if flag == primary:
                btn.setDefault(True)
                QTimer.singleShot(0, btn.setFocus)
        self.add_footer()

    def pick(self, flag):
        self.result_button = flag
        self.accept()

    def reject(self):
        if self.escape is None:
            return  # z. B. Speichern / Nicht speichern ohne Abbrechen: Esc schließt nicht
        self.result_button = self.escape
        super().reject()


def _message(kind, parent, title, text, buttons, default):
    dialog = _MessageDialog(parent, kind, title, text, buttons, default)
    dialog.exec()
    return dialog.result_button


class QMessageBox(_QMessageBox):
    @staticmethod
    def question(parent, title, text, buttons=SB.Yes | SB.No, defaultButton=SB.NoButton):
        return _message("question", parent, title, text, buttons, defaultButton)

    @staticmethod
    def information(parent, title, text, buttons=SB.Ok, defaultButton=SB.NoButton):
        return _message("information", parent, title, text, buttons, defaultButton)

    @staticmethod
    def warning(parent, title, text, buttons=SB.Ok, defaultButton=SB.NoButton):
        return _message("warning", parent, title, text, buttons, defaultButton)

    @staticmethod
    def critical(parent, title, text, buttons=SB.Ok, defaultButton=SB.NoButton):
        return _message("critical", parent, title, text, buttons, defaultButton)

    @staticmethod
    def about(parent, title, text):
        _message("information", parent, title, text, SB.Close, SB.Close)


# ── Eingaben ───────────────────────────────────────────────────────────────

class _InputDialog(_Dialog):
    def __init__(self, parent, title, label, field):
        super().__init__(parent, title)
        self.setMinimumWidth(420)
        self.add_title()
        if label:
            text = QLabel(label, objectName="text")
            text.setWordWrap(True)
            self.body.addWidget(text)
        self.field = field
        self.body.addWidget(field)
        self.footer.addStretch(1)
        self.footer.addWidget(self.button("Abbrechen", "", self.reject))
        ok = self.button("OK", "primary", self.accept)
        ok.setDefault(True)
        self.footer.addWidget(ok)
        self.add_footer()
        QTimer.singleShot(0, field.setFocus)


class QInputDialog(_QInputDialog):
    @staticmethod
    def getText(parent, title, label, echo=QLineEdit.EchoMode.Normal, text="", *args, **kwargs):
        field = QLineEdit(text or "")
        field.setEchoMode(kwargs.get("mode", echo))
        field.selectAll()
        dialog = _InputDialog(parent, title, label, field)
        field.returnPressed.connect(dialog.accept)
        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return (field.text() if ok else "", ok)

    @staticmethod
    def getInt(parent, title, label, value=0, minValue=-2147483647, maxValue=2147483647, step=1, *args, **kwargs):
        minValue = kwargs.get("min", kwargs.get("minValue", minValue))
        maxValue = kwargs.get("max", kwargs.get("maxValue", maxValue))
        field = QSpinBox()
        field.setRange(int(minValue), int(maxValue))
        field.setSingleStep(int(kwargs.get("step", step)))
        field.setValue(int(kwargs.get("value", value)))
        field.selectAll()
        dialog = _InputDialog(parent, title, label, field)
        ok = dialog.exec() == QDialog.DialogCode.Accepted
        return (field.value() if ok else int(value), ok)


# ── Farbwahl ───────────────────────────────────────────────────────────────

SWATCHES = ["#ffffff", "#dce6ff", "#9aa6c4", "#5b6478", "#232836", "#000000",
            "#ff8a8e", "#e5484d", "#ffb07a", "#f2d58a", "#ffe38a", "#c8e68a",
            "#6fdcc0", "#5ec8f0", "#8fb3ff", "#4f6fd8", "#d7a8ff", "#f29cc8"]


class _ColorDialog(_Dialog):
    def __init__(self, parent, title, initial):
        super().__init__(parent, title or "Farbe wählen")
        self.add_title()
        self.picker = _QColorDialog(self)
        self.picker.setWindowFlags(Qt.WindowType.Widget)
        self.picker.setOptions(_QColorDialog.ColorDialogOption.NoButtons
                               | _QColorDialog.ColorDialogOption.DontUseNativeDialog)
        self.picker.setCurrentColor(QColor(initial) if initial is not None else QColor("white"))
        grid = QHBoxLayout()
        grid.setSpacing(6)
        for hex_color in SWATCHES:
            swatch = QPushButton(objectName="swatch")
            swatch.setFixedSize(26, 26)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.setToolTip(hex_color)
            swatch.setStyleSheet(f"QPushButton {{ background: {hex_color}; border: 1px solid {C['line']}; border-radius: 13px; padding: 0; }}"
                                 f"QPushButton:hover {{ border: 2px solid {C['accent']}; }}")
            swatch.clicked.connect(lambda _=False, h=hex_color: self.picker.setCurrentColor(QColor(h)))
            grid.addWidget(swatch)
        grid.addStretch(1)
        self.body.addLayout(grid)
        self.body.addWidget(self.picker)
        self.footer.addStretch(1)
        self.footer.addWidget(self.button("Abbrechen", "", self.reject))
        ok = self.button("Farbe nehmen", "primary", self.accept)
        ok.setDefault(True)
        self.footer.addWidget(ok)
        self.add_footer()


class QColorDialog(_QColorDialog):
    @staticmethod
    def getColor(initial=QColor("white"), parent=None, title="", options=None):
        dialog = _ColorDialog(parent, title, initial)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.picker.currentColor()
        return QColor()


# ── Dateien und Ordner ─────────────────────────────────────────────────────

def _parse_filters(text):
    """'Bilder (*.png *.jpg);;Alle Dateien (*)' → [(Beschriftung, [Muster]), …]"""
    result = []
    for part in (text or "").split(";;"):
        part = part.strip()
        if not part:
            continue
        if "(" in part and part.endswith(")"):
            patterns = part[part.rindex("(") + 1:-1].split()
        else:
            patterns = part.split()
        result.append((part, [p for p in patterns if p] or ["*"]))
    return result or [("Alle Dateien (*)", ["*"])]


def _single_suffix(patterns):
    concrete = [p[1:] for p in patterns if p.startswith("*.") and "*" not in p[2:] and "?" not in p]
    return concrete[0] if len(concrete) >= 1 and len(patterns) >= 1 and patterns[0].startswith("*.") else ""


def _places():
    L = QStandardPaths.StandardLocation
    home = QDir.homePath()
    entries = [("Persönlicher Ordner", home, "home"), ("Schreibtisch", None, "pc"), ("Dokumente", None, "editor"),
               ("Downloads", None, "download"), ("Bilder", None, "image"), ("Musik", None, "music"),
               ("Videos", None, "video")]
    keys = {"Schreibtisch": L.DesktopLocation, "Dokumente": L.DocumentsLocation, "Downloads": L.DownloadLocation,
            "Bilder": L.PicturesLocation, "Musik": L.MusicLocation, "Videos": L.MoviesLocation}
    out = []
    for name, path, icon in entries:
        path = path or QStandardPaths.writableLocation(keys[name])
        if path and os.path.isdir(path) and (name == "Persönlicher Ordner" or os.path.realpath(path) != os.path.realpath(home)):
            out.append((name, path, icon))
    return out


class _Thumbs:
    """Lädt Vorschaubilder nach und nach im Hintergrund der Ereignisschleife."""

    def __init__(self, view):
        self.view = view
        self.cache = {}
        self.queue = []
        self.timer = QTimer(view)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self.step)

    def get(self, path):
        if path in self.cache:
            return self.cache[path]
        if path not in self.queue:
            self.queue.append(path)
            self.timer.start()
        return None

    def step(self):
        if not self.queue:
            self.timer.stop()
            return
        path = self.queue.pop(0)
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        pixmap = QPixmap()
        if size.isValid() and size.width() * size.height() <= 120_000_000:
            reader.setScaledSize(size.scaled(QSize(180, 132), Qt.AspectRatioMode.KeepAspectRatio))
            image = reader.read()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
        self.cache[path] = pixmap
        self.view.viewport().update()


class _TileDelegate(QStyledItemDelegate):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog

    def sizeHint(self, option, index):
        return QSize(118, 118)

    def paint(self, painter, option, index):
        model = self.dialog.model
        info = model.fileInfo(index)
        rect = option.rect.adjusted(4, 4, -4, -4)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        selected = option.state & QStyle.StateFlag.State_Selected
        hover = option.state & QStyle.StateFlag.State_MouseOver
        if selected or hover:
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 10, 10)
            painter.fillPath(path, QColor(C["accent"] if selected else C["raised"]))
        thumb = QRect(rect.left() + 10, rect.top() + 8, rect.width() - 20, 66)
        if not selected:
            box = QPainterPath()
            box.addRoundedRect(QRectF(thumb), 10, 10)
            painter.fillPath(box, QColor(C["raised"]))
        pixmap = None
        if info.isFile() and info.suffix().lower() and "." + info.suffix().lower() in IMAGE_SUFFIXES:
            pixmap = self.dialog.thumbs.get(info.absoluteFilePath())
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(thumb.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                   Qt.TransformationMode.SmoothTransformation)
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(thumb), 10, 10)
            painter.setClipPath(clip)
            painter.drawPixmap(thumb.left() + (thumb.width() - scaled.width()) // 2,
                               thumb.top() + (thumb.height() - scaled.height()) // 2, scaled)
            painter.setClipping(False)
        else:
            icon = model.fileIcon(index)
            icon_rect = QRect(0, 0, 34, 34)
            icon_rect.moveCenter(thumb.center())
            if info.isDir():
                painter.setPen(Qt.PenStyle.NoPen)
                tab = QPainterPath()
                body = QRect(thumb.center().x() - 20, thumb.center().y() - 13, 40, 28)
                tab.addRoundedRect(QRectF(body.left(), body.top() - 5, 18, 10), 3, 3)
                tab.addRoundedRect(QRectF(body), 5, 5)
                painter.fillPath(tab, QColor(C["accentText"] if selected else C["flame"]))
            else:
                icon.paint(painter, icon_rect)
        painter.setPen(QColor(C["accentText"] if selected else C["text"]))
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(bool(selected))
        painter.setFont(font)
        text_rect = QRect(rect.left() + 6, thumb.bottom() + 6, rect.width() - 12, 32)
        name = info.fileName()
        metrics = painter.fontMetrics()
        width = text_rect.width()
        if metrics.horizontalAdvance(name) > width:
            cut = len(name)
            while cut > 1 and metrics.horizontalAdvance(name[:cut]) > width:
                cut -= 1
            name = name[:cut] + "\n" + metrics.elidedText(name[cut:], Qt.TextElideMode.ElideMiddle, width)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, name)
        painter.restore()


class _FileDialog(_Dialog):
    """mode: 'open', 'open-many', 'save' oder 'folder'"""

    def __init__(self, parent, mode, caption, directory, filters, options):
        super().__init__(parent, caption or {"open": "Datei öffnen", "open-many": "Dateien öffnen",
                                              "save": "Speichern unter", "folder": "Ordner wählen"}[mode])
        self.mode = mode
        self.options = options
        self.filters = _parse_filters(filters) if mode != "folder" else [("Ordner", ["*"])]
        self.result_paths = []
        self.result_filter = ""
        self.resize(820, 560)
        self.body.setContentsMargins(0, 18, 0, 0)
        self.body.setSpacing(12)
        self.title.setContentsMargins(22, 0, 22, 0)
        self.add_title()

        start, name = self._start(directory)
        # Pfadzeile
        bar = QHBoxLayout()
        bar.setContentsMargins(22, 0, 22, 0)
        up = self.button("↑", "icon", self.go_up)
        up.setToolTip("Übergeordneter Ordner (Rücktaste)")
        bar.addWidget(up)
        self.path = QLabel(objectName="path")
        bar.addWidget(self.path, 1)
        if mode in ("save", "folder"):
            bar.addWidget(self.button("Neuer Ordner", "", self.new_folder))
        self.body.addLayout(bar)

        sep = QFrame(objectName="sep")
        self.body.addWidget(sep)
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)
        self.places = QListWidget(objectName="places")
        self.places.setFixedWidth(196)
        self.places.setContentsMargins(10, 10, 10, 10)
        self.places.setSpacing(0)
        self.places.setIconSize(QSize(16, 16))
        self.places.setStyleSheet("QListWidget#places { padding: 10px; }")
        for label, path, icon in _places():
            item = QListWidgetItem(_icon(icon), label)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.places.addItem(item)
        self.places.itemClicked.connect(lambda item: self.go(item.data(Qt.ItemDataRole.UserRole)))
        middle.addWidget(self.places)

        self.model = QFileSystemModel(self)
        self.model.setReadOnly(mode not in ("save", "folder"))
        self.model.setNameFilterDisables(False)
        self.show_hidden = False
        self.view = QListView(objectName="files")
        self.view.setModel(self.model)
        self.view.setViewMode(QListView.ViewMode.IconMode)
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setUniformItemSizes(True)
        self.view.setGridSize(QSize(122, 122))
        self.view.setSpacing(0)
        self.view.setMouseTracking(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if mode == "open-many"
                                   else QAbstractItemView.SelectionMode.SingleSelection)
        self.thumbs = _Thumbs(self.view)
        self.view.setItemDelegate(_TileDelegate(self))
        self.view.doubleClicked.connect(self.activate)
        self.view.selectionModel().selectionChanged.connect(self.selection_changed)
        middle.addWidget(self.view, 1)
        self.body.addLayout(middle, 1)

        sep2 = QFrame(objectName="sep")
        self.body.addWidget(sep2)
        foot = QHBoxLayout()
        foot.setContentsMargins(22, 0, 22, 18)
        foot.setSpacing(10)
        self.name = None
        if mode == "save":
            foot.addWidget(QLabel("Name", objectName="muted"))
            self.name = QLineEdit(name)
            self.name.returnPressed.connect(self.accept_choice)
            foot.addWidget(self.name, 1)
        self.filter_box = QComboBox()
        for label, _patterns in self.filters:
            self.filter_box.addItem(label)
        self.filter_box.currentIndexChanged.connect(self.apply_filter)
        if mode != "folder" and len(self.filters) > 1:
            foot.addWidget(self.filter_box, 0 if mode == "save" else 1)
        elif mode != "save":
            hint = QLabel({"folder": "Wähle einen Ordner oder öffne ihn und klicke rechts.",
                           "open-many": "Mehrere Dateien mit Strg oder Umschalt markieren."}.get(mode, ""),
                          objectName="muted")
            foot.addWidget(hint, 1)
        foot.addWidget(self.button("Abbrechen", "", self.reject))
        self.primary = self.button({"open": "Öffnen", "open-many": "Öffnen", "save": "Speichern",
                                    "folder": "Ordner wählen"}[mode], "primary", self.accept_choice)
        self.primary.setDefault(True)
        foot.addWidget(self.primary)
        self.body.addLayout(foot)

        for keys, owner, slot, context in (("Backspace", self.view, self.go_up, Qt.ShortcutContext.WidgetShortcut),
                                           ("Alt+Up", self, self.go_up, Qt.ShortcutContext.WindowShortcut),
                                           ("Ctrl+H", self, self.toggle_hidden, Qt.ShortcutContext.WindowShortcut),
                                           ("Ctrl+L", self, self.type_path, Qt.ShortcutContext.WindowShortcut)):
            shortcut = QShortcut(QKeySequence(keys), owner)
            shortcut.setContext(context)
            shortcut.activated.connect(slot)
        self.apply_filter(0)
        self.go(start)
        if self.name:
            QTimer.singleShot(0, self._focus_name)
        else:
            QTimer.singleShot(0, self.view.setFocus)

    def _start(self, directory):
        directory = os.path.expanduser(str(directory or ""))
        name = ""
        if directory and not os.path.isdir(directory):
            head, name = os.path.split(directory)
            directory = head
            if self.mode != "save":
                name = ""
        if not directory or not os.path.isdir(directory):
            directory = _last_dir["path"] if os.path.isdir(_last_dir["path"]) else self._default_dir()
        return os.path.abspath(directory), name

    def _default_dir(self):
        L = QStandardPaths.StandardLocation
        patterns = " ".join(" ".join(p) for _l, p in self.filters).lower()
        for suffixes, location in (((".png", ".jpg", ".webp"), L.PicturesLocation),
                                   ((".mp4", ".mov", ".mkv"), L.MoviesLocation),
                                   ((".mp3", ".flac", ".wav"), L.MusicLocation),
                                   ((".pdf", ".html", ".docx", ".odt"), L.DocumentsLocation)):
            if any(s in patterns for s in suffixes):
                path = QStandardPaths.writableLocation(location)
                if path and os.path.isdir(path):
                    return path
        return QDir.homePath()

    def _focus_name(self):
        self.name.setFocus()
        text = self.name.text()
        stem = text.rsplit(".", 1)[0] if "." in text[1:] else text
        self.name.setSelection(0, len(stem))

    # Navigation
    def go(self, path):
        if not path or not os.path.isdir(path):
            return
        path = os.path.abspath(path)
        self.current = path
        root = self.model.setRootPath(path)
        self.view.setRootIndex(root)
        self.view.clearSelection()
        home = QDir.homePath()
        shown = path
        if path == home:
            shown = "Persönlicher Ordner"
        elif path.startswith(home + os.sep):
            shown = "Persönlicher Ordner › " + " › ".join(Path(path).relative_to(home).parts)
        else:
            shown = " › ".join(["/"] + list(Path(path).parts[1:]))
        self.path.setText(shown)
        self.path.setToolTip(path)
        for row in range(self.places.count()):
            item = self.places.item(row)
            item.setSelected(os.path.realpath(item.data(Qt.ItemDataRole.UserRole)) == os.path.realpath(path))

    def go_up(self):
        parent = os.path.dirname(self.current)
        if parent and parent != self.current:
            child = self.current
            self.go(parent)
            QTimer.singleShot(150, lambda: self._select_path(child))

    def _select_path(self, path):
        index = self.model.index(path)
        if index.isValid():
            self.view.setCurrentIndex(index)

    def toggle_hidden(self):
        self.show_hidden = not self.show_hidden
        self.apply_filter(self.filter_box.currentIndex())

    def type_path(self):
        target = self.name if self.name else None
        if target:
            target.setText(self.current + os.sep)
            target.setFocus()

    def new_folder(self):
        name, ok = QInputDialog.getText(self, "Neuer Ordner", "Name des Ordners:", text="Neuer Ordner")
        name = name.strip().replace("/", "")
        if ok and name:
            try:
                os.makedirs(os.path.join(self.current, name), exist_ok=False)
                self.go(os.path.join(self.current, name))
            except OSError as error:
                QMessageBox.warning(self, "Ordner nicht angelegt", error.strerror or str(error))

    def apply_filter(self, index):
        index = max(0, index)
        flags = QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot
        if self.mode != "folder":
            flags |= QDir.Filter.Files
        if self.show_hidden:
            flags |= QDir.Filter.Hidden
        self.model.setFilter(flags)
        patterns = self.filters[index][1] if index < len(self.filters) else ["*"]
        self.model.setNameFilters([] if patterns == ["*"] or self.mode == "folder" else patterns)
        if self.name and self.name.text():
            suffix = _single_suffix(patterns)
            text = self.name.text()
            if suffix and "." in text[1:]:
                self.name.setText(text.rsplit(".", 1)[0] + suffix)

    def selection_changed(self, *_):
        indexes = self.view.selectionModel().selectedIndexes()
        if self.name and len(indexes) == 1:
            info = self.model.fileInfo(indexes[0])
            if info.isFile():
                self.name.setText(info.fileName())

    def activate(self, index):
        info = self.model.fileInfo(index)
        if info.isDir():
            self.go(info.absoluteFilePath())
        elif self.mode in ("open", "open-many"):
            self.finish([info.absoluteFilePath()])
        elif self.mode == "save":
            self.name.setText(info.fileName())
            self.accept_choice()

    # Abschluss
    def accept_choice(self):
        selected = [self.model.fileInfo(i) for i in self.view.selectionModel().selectedIndexes()]
        if self.mode == "folder":
            dirs = [i for i in selected if i.isDir()]
            self.finish([dirs[0].absoluteFilePath() if dirs else self.current])
        elif self.mode in ("open", "open-many"):
            if len(selected) == 1 and selected[0].isDir():
                self.go(selected[0].absoluteFilePath())
                return
            files = [i.absoluteFilePath() for i in selected if i.isFile()]
            if files:
                self.finish(files if self.mode == "open-many" else files[:1])
        else:
            self.accept_save()

    def accept_save(self):
        text = self.name.text().strip()
        if not text:
            self.name.setFocus()
            return
        target = os.path.abspath(os.path.join(self.current, os.path.expanduser(text)))
        if os.path.isdir(target):
            self.go(target)
            self.name.clear()
            return
        if not os.path.isdir(os.path.dirname(target)):
            QMessageBox.warning(self, "Ordner fehlt", f"Den Ordner „{os.path.dirname(target)}“ gibt es nicht.")
            return
        suffix = _single_suffix(self.filters[max(0, self.filter_box.currentIndex())][1])
        if suffix and "." not in os.path.basename(target)[1:]:
            target += suffix
        dont_confirm = self.options is not None and bool(self.options & _QFileDialog.Option.DontConfirmOverwrite)
        if os.path.exists(target) and not dont_confirm:
            if QMessageBox.question(self, "Datei ersetzen?",
                                    f"„{os.path.basename(target)}“ gibt es schon. Ersetzen?") != SB.Yes:
                return
        self.finish([target])

    def finish(self, paths):
        self.result_paths = paths
        self.result_filter = self.filters[max(0, self.filter_box.currentIndex())][0] if self.filters else ""
        _last_dir["path"] = paths[0] if self.mode == "folder" else os.path.dirname(paths[0])
        self.accept()


def _run_file_dialog(parent, mode, caption, directory, filters, selected_filter, options):
    dialog = _FileDialog(parent, mode, caption, directory, filters, options)
    if selected_filter:
        labels = [label for label, _p in dialog.filters]
        if selected_filter in labels:
            dialog.filter_box.setCurrentIndex(labels.index(selected_filter))
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return [], ""
    return dialog.result_paths, dialog.result_filter


def _args(args, kwargs, names):
    values = dict(zip(names, args))
    for key, alias in (("caption", "caption"), ("dir", "directory"), ("dir", "dir"), ("filter", "filter"),
                       ("selectedFilter", "selectedFilter"), ("options", "options")):
        if alias in kwargs:
            values[key] = kwargs[alias]
    return values


class QFileDialog(_QFileDialog):
    @staticmethod
    def getOpenFileName(parent=None, *args, **kwargs):
        v = _args(args, kwargs, ["caption", "dir", "filter", "selectedFilter", "options"])
        paths, used = _run_file_dialog(parent, "open", v.get("caption", ""), v.get("dir", ""), v.get("filter", ""),
                                       v.get("selectedFilter", ""), v.get("options"))
        return (paths[0] if paths else "", used)

    @staticmethod
    def getOpenFileNames(parent=None, *args, **kwargs):
        v = _args(args, kwargs, ["caption", "dir", "filter", "selectedFilter", "options"])
        paths, used = _run_file_dialog(parent, "open-many", v.get("caption", ""), v.get("dir", ""),
                                       v.get("filter", ""), v.get("selectedFilter", ""), v.get("options"))
        return (paths, used)

    @staticmethod
    def getSaveFileName(parent=None, *args, **kwargs):
        v = _args(args, kwargs, ["caption", "dir", "filter", "selectedFilter", "options"])
        paths, used = _run_file_dialog(parent, "save", v.get("caption", ""), v.get("dir", ""), v.get("filter", ""),
                                       v.get("selectedFilter", ""), v.get("options"))
        return (paths[0] if paths else "", used)

    @staticmethod
    def getExistingDirectory(parent=None, *args, **kwargs):
        v = _args(args, kwargs, ["caption", "dir", "options"])
        paths, _used = _run_file_dialog(parent, "folder", v.get("caption", ""), v.get("dir", ""), "", "",
                                        v.get("options"))
        return paths[0] if paths else ""


# ── Selbsttest beim Bauen ──────────────────────────────────────────────────

def _selftest():
    import tempfile
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert _parse_filters("Bilder (*.png *.jpg);;Alle Dateien (*)") == [
        ("Bilder (*.png *.jpg)", ["*.png", "*.jpg"]), ("Alle Dateien (*)", ["*"])]
    assert _single_suffix(["*.mp4"]) == ".mp4" and _single_suffix(["*"]) == ""
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "Ordner").mkdir()
        Path(tmp, "a.txt").write_text("x")
        image = QPixmap(40, 30)
        image.fill(QColor("red"))
        image.save(str(Path(tmp, "bild.png")))
        for mode in ("open", "open-many", "save", "folder"):
            d = _FileDialog(None, mode, "Test", str(Path(tmp, "neu.png")) if mode == "save" else tmp,
                            "Bilder (*.png);;Alle Dateien (*)", None)
            d.show()
            for _ in range(30):
                app.processEvents()
            assert d.current == tmp, (mode, d.current)
            if mode == "save":
                assert d.name.text() == "neu.png"
                d.name.setText("ergebnis")
                d.accept_save()
                assert d.result_paths == [str(Path(tmp, "ergebnis.png"))], d.result_paths
            if mode == "folder":
                d.accept_choice()
                assert d.result_paths == [tmp]
            d.go(str(Path(tmp, "Ordner")))
            d.go_up()
            d.view.grab()
            d.close()
    for kind in ("question", "information", "warning"):
        m = _MessageDialog(None, kind, "Löschen?", "Wirklich löschen?", SB.Yes | SB.No, SB.NoButton)
        m.show()
        app.processEvents()
        m.grab()
        m.close()
    m = _MessageDialog(None, "question", "Speichern?", "x", SB.Save | SB.Discard | SB.Cancel, SB.NoButton)
    assert m.escape == SB.Cancel
    m.reject()
    assert m.result_button == SB.Cancel
    _InputDialog(None, "Name", "Name:", QLineEdit("a")).grab()
    _ColorDialog(None, "Farbe", QColor("#8fb3ff")).grab()
    print("creative_dialogs: Selbsttest bestanden")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
