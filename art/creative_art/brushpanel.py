"""Bedienfeld „Pinsel“: Bibliothek, Import (.abr/.gbr/Bilder) und Pinseleinstellungen."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFormLayout, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QListView, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

try:  # Graphit-Dialoge von Creative OS statt der Qt-Standarddialoge
    from creative_dialogs import QFileDialog, QInputDialog, QMessageBox  # noqa: F811
except ImportError:
    pass

from . import brushes as B
from .brushengine import preview, selection_tip

try:  # Design (Graphit/Porzellan) und Akzentfarbe von Creative OS
    from creative_look import themed as T
except ImportError:
    def T(value):
        return value


BRUSH_FILTER = ("Alle Pinsel (*.abr *.gbr *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;"
                "Photoshop-Pinsel (*.abr);;GIMP-Pinsel (*.gbr);;Bilder (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)")
THUMB = QSize(132, 54)

STYLE = """
QListWidget#brushes { background: #12151b; border: 1px solid #2c3242; border-radius: 10px; padding: 4px; }
QListWidget#brushes::item { border-radius: 8px; padding: 2px; color: #b8c3de; }
QListWidget#brushes::item:hover { background: #232836; }
QListWidget#brushes::item:selected { background: #2f4675; color: #ffffff; }
QPushButton { background: #232836; border: none; border-radius: 8px; padding: 6px 10px; color: #dce6ff; }
QPushButton:hover { background: #3a4252; }
QLabel#section { color: #8fb3ff; font-weight: bold; padding-top: 8px; }
QSpinBox { background: #12151b; border: 1px solid #2c3242; border-radius: 6px; padding: 2px 4px; min-width: 58px; }
"""

# (Beschriftung, Feld, min, max, Einheit)
NUMBERS = [
    ("Größe", "size", 1, 2500, " px"),
    ("Härte", "hardness", 0, 100, " %"),
    ("Deckkraft", "opacity", 1, 100, " %"),
    ("Fluss", "flow", 1, 100, " %"),
    ("Abstand", "spacing", 1, 1000, " %"),
    ("Winkel", "angle", -180, 180, "°"),
    ("Rundheit", "roundness", 1, 100, " %"),
]
DYNAMICS = [
    ("Größen-Jitter", "size_jitter", 0, 100, " %"),
    ("Winkel-Jitter", "angle_jitter", 0, 100, " %"),
    ("Rundheits-Jitter", "roundness_jitter", 0, 100, " %"),
    ("Streuung", "scatter", 0, 1000, " %"),
    ("Anzahl", "count", 1, 16, ""),
    ("Deckkraft-Jitter", "opacity_jitter", 0, 100, " %"),
]
SWITCHES = [
    ("Stiftdruck steuert Größe", "pressure_size"),
    ("Stiftdruck steuert Deckkraft", "pressure_opacity"),
    ("Spitze folgt der Strichrichtung", "follow_stroke"),
    ("Zufällig spiegeln", "flip_jitter"),
]


class BrushPanel(QWidget):
    def __init__(self, canvas, window):
        super().__init__()
        self.canvas = canvas
        self.window = window
        self.library = canvas.library
        self.controls = {}
        self.setStyleSheet(STYLE)
        self.save_timer = QTimer(self, singleShot=True, interval=700)
        self.save_timer.timeout.connect(self.library.save)
        self.thumb_timer = QTimer(self, singleShot=True, interval=250)
        self.thumb_timer.timeout.connect(self.refresh_current_thumb)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.list = QListWidget(objectName="brushes")
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setGridSize(QSize(THUMB.width() + 10, THUMB.height() + 30))
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setUniformItemSizes(True)
        self.list.setWordWrap(True)
        self.list.setMinimumHeight(220)
        self.list.currentItemChanged.connect(self.pick)
        layout.addWidget(self.list, 2)

        buttons = QGridLayout()
        buttons.setSpacing(6)
        for i, (text, tip, slot) in enumerate((
            ("Pinsel laden …", "Photoshop (.abr), GIMP (.gbr) oder ein Bild als Pinselspitze", self.import_brushes),
            ("Aus Auswahl", "Auswahl der aktiven Ebene als neue Pinselspitze festlegen", self.from_selection),
            ("Als neuen Pinsel sichern", "Aktuelle Einstellungen als eigenen Pinsel speichern", self.duplicate),
            ("Löschen", "Eigenen Pinsel entfernen", self.remove),
        )):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            buttons.addWidget(button, i // 2, i % 2)
        layout.addLayout(buttons)

        settings = QWidget()
        form = QVBoxLayout(settings)
        form.setContentsMargins(0, 0, 0, 0)
        form.addWidget(QLabel("Pinselspitze", objectName="section"))
        form.addLayout(self.number_rows(NUMBERS))
        form.addWidget(QLabel("Formeigenschaften und Streuung", objectName="section"))
        form.addLayout(self.number_rows(DYNAMICS))
        form.addWidget(QLabel("Stift und Richtung", objectName="section"))
        for label, key in SWITCHES:
            box = QCheckBox(label)
            box.toggled.connect(lambda value, k=key: self.set_value(k, value))
            self.controls[key] = box
            form.addWidget(box)
        form.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(settings)
        layout.addWidget(scroll, 3)

        canvas.presetChanged.connect(self.sync)
        self.populate()

    def number_rows(self, rows):
        grid = QFormLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        for label, key, low, high, unit in rows:
            line = QHBoxLayout()
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(low, min(high, 500) if key in ("size", "spacing", "scatter") else high)
            spin = QSpinBox()
            spin.setRange(low, high)
            spin.setSuffix(unit)
            slider.valueChanged.connect(lambda v, s=spin: s.setValue(v) if s.value() != v else None)
            spin.valueChanged.connect(lambda v, sl=slider: sl.setValue(min(v, sl.maximum())) if sl.value() != v else None)
            spin.valueChanged.connect(lambda v, k=key: self.set_value(k, v))
            line.addWidget(slider, 1)
            line.addWidget(spin)
            grid.addRow(label, line)
            self.controls[key] = spin
            self.controls[key + ":slider"] = slider
        return grid

    # Bibliothek
    def thumb(self, preset):
        image = preview(preset, self.library, THUMB)
        pixmap = QPixmap(THUMB)
        pixmap.fill(QColor(T("#12151b")))
        with QPainter(pixmap) as painter:
            painter.drawImage(0, 0, image)
        return QIcon(pixmap)

    def populate(self):
        current = self.canvas.preset.id
        self.list.blockSignals(True)
        self.list.clear()
        for preset in self.library.presets:
            item = QListWidgetItem(self.thumb(preset), preset.name)
            item.setData(Qt.ItemDataRole.UserRole, preset.id)
            item.setToolTip(preset.name + (f"\naus {preset.source}" if preset.source else ""))
            item.setSizeHint(QSize(THUMB.width() + 8, THUMB.height() + 28))
            self.list.addItem(item)
            if preset.id == current:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        self.sync()

    def preset_by_id(self, pid):
        return next((p for p in self.library.presets if p.id == pid), None)

    def pick(self, item, _previous=None):
        if item is None:
            return
        preset = self.preset_by_id(item.data(Qt.ItemDataRole.UserRole))
        if preset:
            self.canvas.set_preset(preset)

    def sync(self):
        p = self.canvas.preset
        for key, widget in self.controls.items():
            if key.endswith(":slider"):
                continue
            widget.blockSignals(True)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(getattr(p, key)))
            else:
                widget.setValue(int(getattr(p, key)))
                slider = self.controls[key + ":slider"]
                slider.blockSignals(True)
                slider.setValue(min(int(getattr(p, key)), slider.maximum()))
                slider.blockSignals(False)
            widget.blockSignals(False)
        round_tip = p.tip == "round"
        self.controls["hardness"].setEnabled(round_tip)
        self.controls["hardness:slider"].setEnabled(round_tip)
        self.thumb_timer.start()
        self.save_timer.start()

    def set_value(self, key, value):
        preset = self.canvas.preset
        if getattr(preset, key) == value:
            return
        setattr(preset, key, value)
        preset.clamp()
        if key in ("size", "opacity"):
            self.canvas.presetChanged.emit()   # Werkzeugleiste mitziehen
        else:
            self.thumb_timer.start()
            self.save_timer.start()
        self.canvas.update()

    def refresh_current_thumb(self):
        item = self.list.currentItem()
        if item is not None:
            preset = self.preset_by_id(item.data(Qt.ItemDataRole.UserRole))
            if preset:
                item.setIcon(self.thumb(preset))
                item.setText(preset.name)

    def select(self, preset):
        self.canvas.set_preset(preset)
        self.populate()

    # Aktionen
    def import_brushes(self):
        paths, _ = QFileDialog.getOpenFileNames(self.window, "Pinsel laden", "", BRUSH_FILTER)
        if paths:
            self.import_paths(paths)

    def import_paths(self, paths):
        added, problems = [], []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for path in paths:
                try:
                    added += self.library.import_file(path)
                except (B.BrushError, OSError, ValueError, MemoryError) as error:
                    problems.append(f"{Path(path).name}: {error}")
        finally:
            QApplication.restoreOverrideCursor()
        if added:
            self.select(added[0])
            self.window.statusBar().showMessage(
                f"{len(added)} Pinsel geladen." if len(added) != 1 else f"Pinsel „{added[0].name}“ geladen.", 6000)
        if problems:
            QMessageBox.warning(self.window, "Pinsel laden", "\n".join(problems[:12]))
        return added

    def from_selection(self):
        doc = self.canvas.document
        if doc.selection.isEmpty():
            QMessageBox.information(self.window, "Pinsel aus Auswahl",
                                    "Wähle zuerst mit einem Auswahlwerkzeug den Bereich aus, der zur Pinselspitze "
                                    "werden soll. Dunkle Stellen malen, helle und durchsichtige nicht.")
            return
        name, ok = QInputDialog.getText(self.window, "Pinsel aus Auswahl", "Name des Pinsels:",
                                        text=f"Eigener Pinsel {len(self.library.presets) + 1}")
        if not ok:
            return
        try:
            tip = selection_tip(doc.layer.image, doc.selection)
            if tip.max() == 0:
                raise B.BrushError("Die Auswahl ist leer oder ganz weiß.")
            preset = self.library.add_tip(name.strip() or "Eigener Pinsel", tip)
            self.library.save()
        except (B.BrushError, OSError) as error:
            QMessageBox.warning(self.window, "Pinsel aus Auswahl", str(error))
            return
        self.select(preset)

    def duplicate(self):
        name, ok = QInputDialog.getText(self.window, "Als neuen Pinsel sichern", "Name des Pinsels:",
                                        text=f"{self.canvas.preset.name} (eigene)")
        if ok and name.strip():
            self.select(self.library.duplicate(self.canvas.preset, name.strip()))

    def remove(self):
        preset = self.canvas.preset
        if self.library.is_builtin(preset):
            QMessageBox.information(self.window, "Pinsel löschen", "Eingebaute Pinsel lassen sich nicht löschen.")
            return
        if QMessageBox.question(self.window, "Pinsel löschen",
                                f"Den Pinsel „{preset.name}“ löschen?") != QMessageBox.StandardButton.Yes:
            return
        self.library.remove(preset)
        self.select(self.library.presets[0])
