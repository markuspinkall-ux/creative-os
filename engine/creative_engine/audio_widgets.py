"""Bausteine für Musik und Klänge im Editor (Datei wählen, Standard, Stille)."""

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QToolButton, QWidget

from . import icons, project as proj
from .style import C


def audio_row(host, target, key, empty, on_change):
    """Eigene Musik/Klang-Datei (OGG, MP3, WAV) wählen; × setzt auf Standard zurück."""
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    b = QPushButton(Path(target.get(key, "")).name or empty)
    b.setIcon(icons.icon("music", C["text"]))
    b.setToolTip("Musik oder Klang als OGG, MP3 oder WAV")

    def pick():
        rel = host.import_file("Musik oder Klang wählen", proj.AUDIO_FILTER)
        if rel:
            target[key] = rel
            b.setText(Path(rel).name)
            on_change()
    b.clicked.connect(pick)
    x = QToolButton()
    x.setIcon(icons.icon("close", C["muted"]))
    x.setToolTip(empty)

    def clear():
        target[key] = ""
        b.setText(empty)
        on_change()
    x.clicked.connect(clear)
    h.addWidget(b, 1)
    h.addWidget(x)
    return row


def level_music(host, level, on_change):
    """Musik eines Levels: wie im Spiel eingestellt, keine Musik oder eine eigene Datei."""
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    combo = QComboBox()

    def fill():
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Wie in den Spieleinstellungen", "")
        combo.addItem("Keine Musik", "aus")
        own = level.get("music", "")
        if own and own != "aus":
            combo.addItem(Path(own).name, own)
        combo.setCurrentIndex(max(0, combo.findData(own)))
        combo.blockSignals(False)

    def changed(_i):
        level["music"] = combo.currentData()
        on_change()

    def pick():
        rel = host.import_file("Musik für dieses Level", proj.AUDIO_FILTER)
        if rel:
            level["music"] = rel
            fill()
            on_change()
    fill()
    combo.currentIndexChanged.connect(changed)
    b = QToolButton()
    b.setIcon(icons.icon("music", C["text"]))
    b.setToolTip("Eigene Musik für dieses Level wählen …")
    b.clicked.connect(pick)
    h.addWidget(combo, 1)
    h.addWidget(b)
    return row
