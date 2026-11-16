"""Editor-Box „Pausenmenü“: Titel, Ausrichtung, Farben, Abdunklung, Hintergrundbild und Knöpfe.

Die Werte landen in settings["pause"] und werden von runtime/pausemenu.gd gelesen.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFormLayout, QGridLayout, QLabel,
                               QLineEdit, QPushButton, QWidget)

from . import project as proj


def color_button(parent, target, key, title, on_change):
    b = QPushButton(target.get(key, "#ffffff"))

    def paint():
        c = QColor(target.get(key, "#ffffff"))
        fg = "#101318" if c.lightness() > 140 else "#ffffff"
        b.setText(c.name())
        b.setStyleSheet(f"QPushButton{{background:{c.name()};color:{fg};}}")

    def pick():
        c = QColorDialog.getColor(QColor(target.get(key, "#ffffff")), parent, title)
        if c.isValid():
            target[key] = c.name()
            paint()
            on_change()
    paint()
    b.clicked.connect(pick)
    return b


def pause_box(gs, lay, st):
    """gs = GameSettings (für spin/graphic/set), lay = Box-Layout, st = settings."""
    pause = st.setdefault("pause", proj.pause_default())
    for k, v in proj.pause_default().items():
        pause.setdefault(k, v)
    lay.addWidget(QLabel("PAUSENMENÜ", objectName="section"))
    form = QFormLayout()
    title = QLineEdit(pause.get("title", "Pause"))
    title.textEdited.connect(lambda t: gs.set(pause, "title", t))
    form.addRow("Überschrift", title)
    pos = QComboBox()
    for k, label in (("mitte", "Mitte"), ("links", "Links"), ("rechts", "Rechts")):
        pos.addItem(label, k)
    pos.setCurrentIndex(max(0, pos.findData(pause.get("position", "mitte"))))
    pos.currentIndexChanged.connect(lambda _i: gs.set(pause, "position", pos.currentData()))
    form.addRow("Ausrichtung", pos)
    form.addRow("Breite", gs.spin(pause, "width", 240, 900, 10, 360, 0, " px"))
    form.addRow("Schriftgröße", gs.spin(pause, "size", 14, 48, 1, 24, 0, " px"))
    form.addRow("Abdunklung", gs.spin(pause, "shade", 0, 1, 0.05, 0.55, 2))
    for key, label in (("panel", "Fläche"), ("accent", "Akzent / Auswahl"), ("text", "Schrift")):
        form.addRow(label, color_button(gs, pause, key, f"Farbe: {label}", gs.win.touched))
    form.addRow("Hintergrundbild", gs.graphic(pause, "image"))
    lay.addLayout(form)
    grid = QGridLayout()
    grid.setHorizontalSpacing(8)
    buttons = pause.setdefault("buttons", {})
    labels = pause.setdefault("labels", {})
    defaults = proj.pause_default()
    for row, key in enumerate(("weiter", "neustart", "steuerung", "menu")):
        show = QCheckBox()
        show.setChecked(bool(buttons.get(key, True)))
        show.setEnabled(key != "weiter")            # „Weiter“ muss es immer geben
        show.toggled.connect(lambda val, key=key: gs.set(buttons, key, val))
        name = QLineEdit(labels.get(key, defaults["labels"][key]))
        name.textEdited.connect(lambda t, key=key: gs.set(labels, key, t))
        grid.addWidget(show, row, 0)
        grid.addWidget(name, row, 1)
    lay.addWidget(QLabel("Knöpfe (Haken = anzeigen, Text frei wählbar)", objectName="sub"))
    holder = QWidget()
    holder.setLayout(grid)
    lay.addWidget(holder)
    tip = QLabel("Esc oder Start am Controller öffnet das Menü. Das Hintergrundbild (PNG) wird 9-teilig "
                 "gedehnt, die Ecken bleiben scharf.")
    tip.setWordWrap(True)
    tip.setObjectName("sub")
    lay.addWidget(tip)
