"""Creative Art desktop application."""

import sys
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImageReader, QKeySequence, QPainter, QPainterPath, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QDialog, QDialogButtonBox, QDockWidget, QFileDialog,
    QFormLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QScrollArea, QSpinBox, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from .canvas import Canvas
from .document import Document, MAX_SIDE, check_size, read_image, transparent

PROJECT = "Creative Art (*.cart)"
IMAGES = "Bilder (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif)"
HANDLED_ERRORS = (OSError, ValueError, RuntimeError)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.path = None
        self.source_name = ""
        self.canvas = Canvas(Document(transparent(QSize(1000, 700))))
        self.resize(1320, 870)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.canvas)
        self.scroll.setStyleSheet("QScrollArea { background: #101218; border: 0; }")
        self.setCentralWidget(self.scroll)
        self.make_actions()
        self.make_layers()
        self.canvas.changed.connect(self.refresh)
        self.canvas.zoomChanged.connect(self.update_status)
        self.canvas.colorChanged.connect(self.update_color)
        self.canvas.hint.connect(lambda text: self.statusBar().showMessage(text, 5000))
        self.refresh()

    @property
    def doc(self):
        return self.canvas.document

    def action(self, label, callback, shortcut=None, menu=None, toolbar=None):
        action = QAction(label, self)
        action.triggered.connect(callback)
        if shortcut:
            action.setShortcut(shortcut)
        if menu:
            menu.addAction(action)
        else:
            self.addAction(action)
        if toolbar:
            toolbar.addAction(action)
        return action

    def make_actions(self):
        standard = QKeySequence.StandardKey
        file = self.menuBar().addMenu("&Datei")
        edit = self.menuBar().addMenu("&Bearbeiten")
        view = self.menuBar().addMenu("&Ansicht")
        self.action("Neu …", self.new, standard.New, file)
        self.action("Öffnen …", self.open, standard.Open, file)
        self.action("Projekt speichern", self.save, standard.Save, file)
        self.action("Projekt speichern unter …", self.save_as, standard.SaveAs, file)
        self.action("PNG exportieren …", self.export, "Ctrl+Shift+E", file)
        self.undo_action = self.action("Rückgängig", lambda: self.history(True), standard.Undo, edit)
        self.redo_action = self.action("Wiederholen", lambda: self.history(False), standard.Redo, edit)
        edit.addSeparator()
        self.copy_action = self.action("Auswahl kopieren", self.copy, standard.Copy, edit)
        self.cut_action = self.action("Auswahl ausschneiden", self.cut, standard.Cut, edit)
        self.action("Bild als Ebene einfügen", self.paste, standard.Paste, edit)
        self.delete_action = self.action("Auswahl löschen", self.delete_selection, "Delete", edit)
        self.action("Alles auswählen", self.select_all, standard.SelectAll, edit)
        self.action("Auswahl aufheben", self.deselect, "Ctrl+D", edit)
        self.action("Auswahl aufheben", self.deselect, "Escape")
        self.crop_action = self.action("Auf Auswahl zuschneiden", self.crop, "Return", edit)
        self.action("Mit Vordergrundfarbe füllen", self.fill, "Alt+Backspace", edit)
        self.action("Einpassen", self.fit, "Ctrl+0", view)
        self.action("100 %", lambda: self.canvas.set_zoom(1), "Ctrl+1", view)
        self.action("Vergrößern", lambda: self.canvas.set_zoom(self.canvas.zoom * 1.25), "Ctrl++", view)
        self.action("Verkleinern", lambda: self.canvas.set_zoom(self.canvas.zoom * .8), "Ctrl+-", view)

        tools = QToolBar("Werkzeuge")
        tools.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tools)
        group = QActionGroup(self)
        for key, label, shortcut, shape in (
            ("move", "Ebene verschieben", "V", '<path d="M12 3v18M3 12h18m-12-6 3-3 3 3m-9 3-3 3 3 3m3 3 3 3 3-3m3-9 3 3-3 3"/>'),
            ("brush", "Pinsel", "B", '<path d="m10 14 8-10q3-2 2 2l-6 11m-4-3c-4 0-2 5-6 6 4 2 9 0 10-3z"/>'),
            ("eraser", "Radierer", "E", '<path d="m4 14 9-10 7 6-8 10H9zm3-4 8 7m-4 3h10"/>'),
            ("clone", "Kopierstempel", "S", '<path d="M5 18h14v3H5zm1-3c0-3 4-2 4-5L9 6a3 3 0 0 1 6 0l-1 4c0 3 4 2 4 5z"/>'),
            ("rectangle", "Rechteckauswahl", "M", '<rect x="4" y="5" width="16" height="14" stroke-dasharray="2 3"/>'),
            ("ellipse", "Ellipsenauswahl", "O", '<ellipse cx="12" cy="12" rx="8" ry="7" stroke-dasharray="2 3"/>'),
            ("lasso", "Lasso", "L", '<path d="M8 17c-8 0-6-12 4-12 11 0 12 13 2 13-4 0-7-3-8-1s1 4 5 3"/>'),
            ("crop", "Zuschneiden", "C", '<path d="M7 3v14h14M3 7h14v14m-7-7 9-9"/>'),
            ("picker", "Pipette", "I", '<path d="m9 9 6 6m-4-5 6-6a2 2 0 0 1 3 3l-6 6m-4-3-6 7v3h3l7-6"/>'),
            ("line", "Linie", "U", '<path d="m5 19 14-14"/>'),
            ("box", "Rechteck zeichnen", "R", '<rect x="4" y="5" width="16" height="14"/>'),
            ("oval", "Ellipse zeichnen", "P", '<ellipse cx="12" cy="12" rx="8" ry="7"/>'),
        ):
            action = self.action(label, lambda checked, tool=key, name=label: self.select_tool(tool, name),
                                 shortcut, toolbar=tools)
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
                   '<g fill="none" stroke="#dce6ff" stroke-width="1.7" stroke-linejoin="round" '
                   f'stroke-linecap="round">{shape}</g></svg>')
            icon = QPixmap()
            icon.loadFromData(svg.encode(), "SVG")
            action.setIcon(QIcon(icon))
            action.setToolTip(f"{label} ({shortcut})")
            action.setCheckable(True)
            group.addAction(action)
            action.setChecked(key == self.canvas.tool)
            tools.widgetForAction(action).setAccessibleName(label)

        options = self.addToolBar("Werkzeugoptionen")
        options.setMovable(False)
        self.tool_name = QLabel("Pinsel")
        self.tool_name.setMinimumWidth(108)
        options.addWidget(self.tool_name)
        self.color_button = QToolButton()
        self.color_button.setText("Farbe …")
        self.color_button.clicked.connect(self.choose_color)
        options.addWidget(self.color_button)
        self.update_color()
        for label, field, maximum in (("Größe", "diameter", 512), ("Deckkraft", "opacity", 100)):
            options.addWidget(QLabel(f"  {label} "))
            spin = QSpinBox()
            spin.setRange(1, maximum)
            spin.setSuffix(" px" if field == "diameter" else " %")
            spin.setValue(getattr(self.canvas, field))
            spin.valueChanged.connect(lambda value, prop=field: setattr(self.canvas, prop, value))
            options.addWidget(spin)
        options.addSeparator()
        self.action("Auswahl zuschneiden", self.crop, toolbar=options)
        self.action("Einpassen", self.fit, toolbar=options)

    def make_layers(self):
        dock = QDockWidget("Ebenen", self)
        dock.setMinimumWidth(240)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.layers = QListWidget()
        self.layers.currentRowChanged.connect(self.activate_layer)
        self.layers.itemChanged.connect(self.toggle_visibility)
        self.layers.itemDoubleClicked.connect(self.rename_layer)
        layout.addWidget(self.layers)
        self.layer_opacity = QSpinBox()
        self.layer_opacity.setRange(0, 100)
        self.layer_opacity.setSuffix(" %")
        self.layer_opacity.setKeyboardTracking(False)
        self.layer_opacity.valueChanged.connect(self.set_layer_opacity)
        form = QFormLayout()
        form.addRow("Ebenendeckkraft", self.layer_opacity)
        layout.addLayout(form)
        toolbar = QToolBar()
        self.action("+", self.add_layer, toolbar=toolbar).setToolTip("Neue Ebene")
        self.action("Bild", self.import_layer, toolbar=toolbar).setToolTip("Bild als Ebene öffnen")
        self.action("↑", lambda: self.move_layer(1), toolbar=toolbar).setToolTip("Ebene nach oben")
        self.action("↓", lambda: self.move_layer(-1), toolbar=toolbar).setToolTip("Ebene nach unten")
        self.action("−", self.remove_layer, toolbar=toolbar).setToolTip("Aktive Ebene entfernen")
        layout.addWidget(toolbar)
        dock.setWidget(panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.menuBar().actions()[2].menu().addAction(dock.toggleViewAction())

    def refresh(self):
        self.canvas.update()
        if self.canvas.raster_size != self.doc.size:
            self.canvas.set_zoom(self.canvas.zoom)
        with QSignalBlocker(self.layers):
            self.layers.clear()
            for index in reversed(range(len(self.doc.layers))):
                layer = self.doc.layers[index]
                item = QListWidgetItem(layer.name)
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setCheckState(Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
                self.layers.addItem(item)
            self.layers.setCurrentRow(len(self.doc.layers) - 1 - self.doc.active)
        with QSignalBlocker(self.layer_opacity):
            self.layer_opacity.setValue(self.doc.layer.opacity)
        self.undo_action.setEnabled(bool(self.doc.undo))
        self.redo_action.setEnabled(bool(self.doc.redo))
        has_selection = not self.doc.selection_bounds().isEmpty()
        self.copy_action.setEnabled(has_selection)
        self.cut_action.setEnabled(has_selection and self.doc.layer.visible)
        self.delete_action.setEnabled(self.cut_action.isEnabled())
        self.crop_action.setEnabled(has_selection)
        self.setWindowTitle(f"{self.source_name or 'Unbenannt'}[*] – Creative Art")
        self.setWindowModified(self.doc.modified)
        self.update_status()

    def update_status(self, *_):
        self.statusBar().showMessage(f"{self.doc.size.width()} × {self.doc.size.height()} px  ·  {self.canvas.zoom:.0%}")

    def select_tool(self, tool, name=""):
        self.canvas.set_tool(tool)
        if name:
            self.tool_name.setText(name)
        if tool == "clone":
            self.statusBar().showMessage("Kopierstempel: Alt oder Umschalt + Klick setzt die Quelle.", 7000)
        elif tool == "crop":
            self.statusBar().showMessage("Rahmen ziehen und Eingabetaste drücken.", 5000)

    def update_color(self):
        color = self.canvas.color.name()
        self.color_button.setStyleSheet(f"border-left: 15px solid {color}; padding: 4px 8px;")

    def choose_color(self):
        color = QColorDialog.getColor(self.canvas.color, self, "Vordergrundfarbe")
        if color.isValid():
            self.canvas.color = color
            self.update_color()

    def activate_layer(self, row):
        if row >= 0:
            self.doc.active = len(self.doc.layers) - 1 - row
            self.canvas.clone_source = None
            self.refresh()

    def toggle_visibility(self, item):
        layer = self.doc.layers[item.data(Qt.ItemDataRole.UserRole)]
        visible = item.checkState() == Qt.CheckState.Checked
        if layer.visible != visible:
            self.doc.checkpoint()
            layer.visible = visible
            self.refresh()

    def rename_layer(self, item):
        layer = self.doc.layers[item.data(Qt.ItemDataRole.UserRole)]
        name, ok = QInputDialog.getText(self, "Ebene umbenennen", "Name", text=layer.name)
        if ok and name.strip() and name.strip() != layer.name:
            self.doc.checkpoint()
            layer.name = name.strip()[:120]
            self.refresh()

    def set_layer_opacity(self, value):
        if self.doc.layer.opacity != value:
            self.doc.checkpoint()
            self.doc.layer.opacity = value
            self.refresh()

    def add_layer(self, name=None, image=None):
        try:
            self.doc.add_layer(name or f"Ebene {len(self.doc.layers) + 1}", image)
        except HANDLED_ERRORS as exc:
            self.error(exc)
            return
        self.canvas.clone_source = None
        self.refresh()

    def move_layer(self, step):
        current = self.doc.active
        target = current + step
        if 0 <= target < len(self.doc.layers):
            self.doc.checkpoint()
            self.doc.layers[current], self.doc.layers[target] = self.doc.layers[target], self.doc.layers[current]
            self.doc.active = target
            self.refresh()

    def remove_layer(self):
        if len(self.doc.layers) > 1:
            self.doc.checkpoint()
            self.doc.layers.pop(self.doc.active)
            self.doc.active = min(self.doc.active, len(self.doc.layers) - 1)
            self.canvas.clone_source = None
            self.refresh()

    def history(self, backwards):
        self.doc.step(backwards)
        self.canvas.clone_source = None
        self.refresh()

    def select_all(self):
        selection = QPainterPath()
        selection.addRect(self.doc.layer.image.rect())
        self.doc.selection = selection
        self.refresh()

    def deselect(self):
        self.doc.selection = QPainterPath()
        self.refresh()

    def crop(self):
        if self.doc.crop():
            self.canvas.clone_source = None
            self.fit()
            self.refresh()

    def delete_selection(self):
        if self.doc.clear_selection_pixels():
            self.refresh()

    def fill(self):
        if not self.doc.layer.visible:
            return
        self.doc.checkpoint()
        with QPainter(self.doc.layer.image) as painter:
            if not self.doc.selection.isEmpty():
                painter.setClipPath(self.doc.selection)
            painter.fillRect(self.doc.layer.image.rect(), self.canvas.color)
        self.refresh()

    def copy(self):
        QApplication.clipboard().setImage(self.doc.render(self.doc.selection_bounds(), selection=True))

    def cut(self):
        bounds = self.doc.selection_bounds()
        image = transparent(bounds.size())
        with QPainter(image) as painter:
            painter.translate(-bounds.x(), -bounds.y())
            painter.setClipPath(self.doc.selection)
            painter.drawImage(0, 0, self.doc.layer.image)
        QApplication.clipboard().setImage(image)
        self.delete_selection()

    def paste(self):
        image = QApplication.clipboard().image()
        if not image.isNull():
            self.add_layer("Zwischenablage", image)

    def fit(self):
        area = self.scroll.viewport().size()
        size = self.doc.size
        self.canvas.set_zoom(min(1, (area.width() - 28) / size.width(),
                                 (area.height() - 28) / size.height()))

    def error(self, exc):
        QMessageBox.warning(self, "Creative Art", str(exc))

    def confirm_discard(self):
        if not self.doc.modified:
            return True
        buttons = QMessageBox.StandardButton
        choice = QMessageBox.question(self, "Änderungen speichern?", "Das Projekt enthält ungespeicherte Änderungen.",
                                      buttons.Save | buttons.Discard | buttons.Cancel, buttons.Save)
        return choice == buttons.Discard or (choice == buttons.Save and self.save())

    def set_document(self, document, path=None, source_name=""):
        self.path = path
        self.source_name = source_name
        self.canvas.set_document(document)
        self.fit()
        self.refresh()

    def new(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Neues transparentes Bild")
        form = QFormLayout(dialog)
        dimensions = []
        for name, default in (("Breite", 1000), ("Höhe", 700)):
            spin = QSpinBox()
            spin.setRange(1, MAX_SIDE)
            spin.setValue(default)
            spin.setSuffix(" px")
            form.addRow(name, spin)
            dimensions.append(spin)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() and self.confirm_discard():
            try:
                size = QSize(*(spin.value() for spin in dimensions))
                check_size(size)
                self.set_document(Document(transparent(size)))
            except HANDLED_ERRORS as exc:
                self.error(exc)

    def open(self):
        name, _ = QFileDialog.getOpenFileName(self, "Bild oder Projekt öffnen", "", f"{PROJECT};;{IMAGES}")
        if name and self.confirm_discard():
            self.open_path(Path(name))

    def open_path(self, path):
        try:
            is_project = path.suffix.lower() == ".cart"
            if is_project:
                document = Document.open_project(path)
            else:
                document = Document(read_image(QImageReader(str(path))), path.stem)
            self.set_document(document, path if is_project else None, path.name)
        except HANDLED_ERRORS as exc:
            self.error(exc)

    def import_layer(self):
        name, _ = QFileDialog.getOpenFileName(self, "Bild als Ebene öffnen", "", IMAGES)
        if name:
            try:
                self.add_layer(Path(name).stem, read_image(QImageReader(name)))
            except HANDLED_ERRORS as exc:
                self.error(exc)

    def output_path(self, caption, suffix, file_filter):
        suggested = Path(self.source_name or "Unbenannt").with_suffix(suffix)
        name, _ = QFileDialog.getSaveFileName(self, caption, str(suggested), file_filter)
        if not name:
            return None
        path = Path(name)
        if path.suffix.lower() != suffix:
            path = path.with_name(path.name + suffix)
            if path.exists() and QMessageBox.question(
                self, "Datei ersetzen?", f"„{path.name}“ existiert bereits. Ersetzen?"
            ) != QMessageBox.StandardButton.Yes:
                return None
        return path

    def save_as(self):
        path = self.output_path("Projekt speichern", ".cart", PROJECT)
        return self.save_project(path) if path else False

    def save(self):
        return self.save_project(self.path) if self.path else self.save_as()

    def save_project(self, path):
        try:
            self.doc.save_project(path)
        except HANDLED_ERRORS as exc:
            self.error(exc)
            return False
        self.path = path
        self.source_name = path.name
        self.refresh()
        return True

    def export(self):
        path = self.output_path("PNG mit Transparenz exportieren", ".png", "PNG (*.png)")
        if path:
            try:
                self.doc.export_png(path)
            except HANDLED_ERRORS as exc:
                self.error(exc)
            else:
                self.statusBar().showMessage("PNG gespeichert.", 4000)

    def closeEvent(self, event):
        event.setAccepted(self.confirm_discard())


def main():
    args = sys.argv[1:]
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Creative Art")
    app.setDesktopFileName("creative-art")
    app.setWindowIcon(QIcon.fromTheme("creative-art"))
    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in {
        QPalette.ColorRole.Window: "#1c2029",
        QPalette.ColorRole.WindowText: "#dce6ff",
        QPalette.ColorRole.Base: "#12151b",
        QPalette.ColorRole.AlternateBase: "#232836",
        QPalette.ColorRole.Text: "#dce6ff",
        QPalette.ColorRole.Button: "#232836",
        QPalette.ColorRole.ButtonText: "#dce6ff",
        QPalette.ColorRole.Highlight: "#8fb3ff",
        QPalette.ColorRole.HighlightedText: "#12151b",
    }.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    window = Window()
    window.show()
    if args == ["--selftest"]:
        app.processEvents()
        return 0
    if args:
        window.open_path(Path(args[0]))
    else:
        QTimer.singleShot(0, window.fit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
