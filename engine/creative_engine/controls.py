"""Steuerung selbst festlegen: je Aktion zwei Tasten, eine Maustaste und zwei Controller-Eingaben."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import project as proj
from .style import C

QT_NAMES = {
    Qt.Key.Key_Shift: "Shift", Qt.Key.Key_Control: "Ctrl", Qt.Key.Key_Alt: "Alt", Qt.Key.Key_Space: "Space",
    Qt.Key.Key_Return: "Enter", Qt.Key.Key_Enter: "Enter", Qt.Key.Key_Tab: "Tab", Qt.Key.Key_Left: "Left",
    Qt.Key.Key_Right: "Right", Qt.Key.Key_Up: "Up", Qt.Key.Key_Down: "Down", Qt.Key.Key_Backspace: "BackSpace",
    Qt.Key.Key_Delete: "Delete", Qt.Key.Key_Insert: "Insert", Qt.Key.Key_Home: "Home", Qt.Key.Key_End: "End",
    Qt.Key.Key_PageUp: "PageUp", Qt.Key.Key_PageDown: "PageDown", Qt.Key.Key_CapsLock: "CapsLock",
}


def key_name(event):
    """Qt-Tastendruck → Godot-Tastenname (None, wenn die Taste nicht geht)."""
    k = event.key()
    if k in QT_NAMES:
        return QT_NAMES[k]
    if Qt.Key.Key_F1 <= k <= Qt.Key.Key_F12:
        return f"F{k - Qt.Key.Key_F1 + 1}"
    text = QKeySequence(k).toString()
    if len(text) == 1 and text.isascii() and text.isalnum():
        return text.upper()
    return None


class KeyButton(QPushButton):
    """Klicken, dann die gewünschte Taste drücken. Rechtsklick oder Entf leert das Feld, Esc bricht ab."""
    picked = Signal(str)

    def __init__(self, value):
        super().__init__()
        self.value = value
        self.listening = False
        self.setMinimumWidth(104)
        self.setToolTip("Klicken und Taste drücken · Rechtsklick leert")
        self.clicked.connect(self.listen)
        self.show_value()

    def show_value(self):
        self.setText(proj.binding_label("keys", self.value) if self.value else "—")
        self.setStyleSheet("" if not self.listening else f"QPushButton{{border:2px solid {C['accent']};}}")

    def listen(self):
        self.listening = True
        self.setText("Taste drücken …")
        self.setStyleSheet(f"QPushButton{{border:2px solid {C['accent']};}}")
        self.grabKeyboard()

    def stop(self):
        self.listening = False
        self.releaseKeyboard()
        self.show_value()

    def keyPressEvent(self, event):
        if not self.listening:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key.Key_Escape:
            self.stop()
            return
        if event.key() == Qt.Key.Key_Delete:
            self.value = ""
            self.stop()
            self.picked.emit("")
            return
        name = key_name(event)
        if name is None:
            self.setText("Taste geht nicht")
            return
        self.value = name
        self.stop()
        self.picked.emit(name)

    def focusOutEvent(self, event):
        if self.listening:
            self.stop()
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.value = ""
            if self.listening:
                self.stop()
            self.show_value()
            self.picked.emit("")
            return
        super().mousePressEvent(event)


class ControlsBox(QWidget):
    changed = Signal()

    def __init__(self, project):
        super().__init__()
        self.project = project
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("STEUERUNG", objectName="section")
        head.addWidget(title)
        head.addStretch(1)
        reset = QPushButton("Standard wiederherstellen")
        reset.clicked.connect(self.reset)
        head.addWidget(reset)
        v.addLayout(head)
        hint = QLabel("Für jede Aktion bis zu zwei Tasten, eine Maustaste und zwei Controller-Eingaben "
                      "(Xbox- und PlayStation-Controller). Taste ändern: Feld anklicken, Taste drücken. "
                      "Rechtsklick leert ein Feld.")
        hint.setWordWrap(True)
        hint.setObjectName("sub")
        v.addWidget(hint)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(5)
        v.addLayout(self.grid)
        self.conflicts = QLabel("")
        self.conflicts.setWordWrap(True)
        self.conflicts.setStyleSheet(f"color:{C['danger']}")
        v.addWidget(self.conflicts)
        if proj.is_space(project):
            extra = QLabel("Fest belegt: Waffen direkt mit 1–6. Die Maus lenkt das Schiff (abschaltbar unter "
                           "„Raumschiff“).")
            extra.setWordWrap(True)
            extra.setObjectName("sub")
            v.addWidget(extra)
        self.fill()

    def fill(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for col, text in enumerate(("Aktion", "Taste 1", "Taste 2", "Maus", "Controller 1", "Controller 2")):
            h = QLabel(text)
            h.setObjectName("sub")
            self.grid.addWidget(h, 0, col)
        current = proj.controls_for(self.project)
        for row, (action, label, _default) in enumerate(proj.control_actions(self.project), start=1):
            b = current[action]
            self.grid.addWidget(QLabel(label), row, 0)
            for i in range(2):
                keys = b["keys"]
                kb = KeyButton(keys[i] if i < len(keys) else "")
                kb.setAccessibleName(f"{label}: Taste {i + 1}")
                kb.picked.connect(lambda name, a=action, i=i: self.set_key(a, i, name))
                self.grid.addWidget(kb, row, 1 + i)
            mouse = self.combo([("", "—")] + proj.MOUSE_INPUTS, b["mouse"][0] if b["mouse"] else "")
            mouse.setAccessibleName(f"{label}: Maustaste")
            mouse.currentIndexChanged.connect(lambda _i, a=action, cb=mouse: self.set_list(a, "mouse", 0, cb.currentData()))
            self.grid.addWidget(mouse, row, 3)
            for i in range(2):
                pads = b["pad"]
                pad = self.combo([("", "—")] + proj.PAD_INPUTS, pads[i] if i < len(pads) else "")
                pad.setAccessibleName(f"{label}: Controller {i + 1}")
                pad.currentIndexChanged.connect(lambda _i, a=action, i=i, cb=pad: self.set_list(a, "pad", i, cb.currentData()))
                self.grid.addWidget(pad, row, 4 + i)
        self.grid.setColumnStretch(0, 2)
        self.show_conflicts()

    @staticmethod
    def combo(items, value):
        cb = QComboBox()
        for k, text in items:
            cb.addItem(text, k)
        cb.setCurrentIndex(max(0, cb.findData(value)))
        cb.setMinimumWidth(130)
        return cb

    def set_key(self, action, index, name):
        self.set_list(action, "keys", index, name)

    def set_list(self, action, kind, index, value):
        values = list(proj.controls_for(self.project)[action][kind])
        while len(values) <= index:
            values.append("")
        values[index] = value
        proj.set_binding(self.project, action, kind, [x for x in values if x])
        self.show_conflicts()
        self.changed.emit()

    def reset(self):
        proj.reset_controls(self.project)
        self.fill()
        self.changed.emit()

    def show_conflicts(self):
        problems = proj.control_conflicts(self.project)
        self.conflicts.setText("\n".join("⚠ " + p for p in problems))
        self.conflicts.setVisible(bool(problems))
