"""Bedienlogik des Creative Calculator: Tasten, Anzeige, Verlauf."""

import json
import os
import re
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from .engine import CalcError, evaluate, format_number

OPERATORS = "+−×÷"
TRAILING_NUMBER = re.compile(r"(\(−)?([0-9,]+)(\))?$")


def _history_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "calculator.json"


class Calculator(QObject):
    changed = Signal()
    historyChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expr = ""
        self._result = ""          # nach „=“
        self._done = False         # letzte Aktion war „=“
        self._error = ""
        self._history = []
        try:
            data = json.loads(_history_file().read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._history = [h for h in data if isinstance(h, dict) and "expr" in h and "result" in h][:50]
        except (OSError, ValueError):
            pass

    # ---- Anzeige ---------------------------------------------------------------------
    def _preview(self):
        if self._done or not self._expr or self._error:
            return ""
        expr = self._expr.rstrip(OPERATORS + "(")
        if not expr or not any(op in expr for op in "+−×÷%^√") and "(" not in expr:
            return ""
        try:
            return format_number(evaluate(expr, partial=True))
        except CalcError:
            return ""

    def _display(self):
        if self._error:
            return self._error
        if self._done:
            return self._result
        return self._expr or "0"

    def _last(self):
        return self._expr[-1] if self._expr else " "        # nie "" (wäre in jedem String enthalten)

    # ---- Eingabe --------------------------------------------------------------------------
    def _start_fresh_if_done(self, continue_with_result):
        if self._done:
            self._expr = self._result.replace(" ", "").replace("-", "−") if continue_with_result else ""
            if " × 10^" in self._expr:                       # wissenschaftliche Anzeige weiterrechnen
                mant, exp = self._expr.split(" × 10^")
                self._expr = f"{mant}×10^{exp}"
            self._done = False
        self._error = ""

    @Slot(str)
    def press(self, key):
        if key in "0123456789":
            self._start_fresh_if_done(False)
            last = self._last()
            if last in (")", "%"):
                self._expr += "×"
            # „05“ → „5“
            m = re.search(r"(^|[^0-9,])0$", self._expr)
            if m and key != ",":
                self._expr = self._expr[:-1]
            self._expr += key
        elif key in (",", "."):
            self._start_fresh_if_done(False)
            m = re.search(r"[0-9,]*$", self._expr)
            if "," in m.group(0):
                return
            if not m.group(0):
                if self._last() in (")", "%"):
                    self._expr += "×"
                self._expr += "0"
            self._expr += ","
        elif key in OPERATORS or key in "+-*/":
            key = {"-": "−", "*": "×", "/": "÷"}.get(key, key)
            self._start_fresh_if_done(True)
            if not self._expr:
                if key == "−":
                    self._expr = "−"
                else:
                    self._expr = "0" + key
            elif self._expr[-1] in OPERATORS:
                # Vorzeichen nach × ÷ erlauben, sonst Operator tauschen
                if key == "−" and self._expr[-1] in "×÷":
                    self._expr += key
                else:
                    self._expr = self._expr.rstrip(OPERATORS) + key if self._expr.rstrip(OPERATORS) else ("−" if key == "−" else "")
            elif self._expr[-1] == "(":
                if key == "−":
                    self._expr += key
            elif self._expr[-1] == ",":
                self._expr = self._expr[:-1] + key
            else:
                self._expr += key
        elif key == "%":
            self._start_fresh_if_done(True)
            if self._expr and (self._expr[-1].isdigit() or self._expr[-1] == ")"):
                self._expr += "%"
        elif key == "()":
            self._start_fresh_if_done(False)
            opened = self._expr.count("(") - self._expr.count(")")
            last = self._last()
            if opened > 0 and (last.isdigit() or last in ")%"):
                self._expr += ")"
            else:
                if last.isdigit() or last in ")%":
                    self._expr += "×"
                self._expr += "("
        elif key in ("(", ")"):
            self._start_fresh_if_done(False)
            if key == "(":
                if self._last().isdigit() or self._last() in ")%":
                    self._expr += "×"
                self._expr += "("
            elif self._expr.count("(") > self._expr.count(")") and self._last() not in OPERATORS + "(":
                self._expr += ")"
        elif key == "±":
            self._start_fresh_if_done(True)
            m = TRAILING_NUMBER.search(self._expr)
            if not m:
                if not self._expr or self._expr[-1] in OPERATORS + "(":
                    self._expr += "(−"
            elif m.group(1) and m.group(3):                 # (−5) → 5
                self._expr = self._expr[:m.start()] + m.group(2)
            elif m.group(1):                                # (−5 → 5
                self._expr = self._expr[:m.start()] + m.group(2)
            elif self._expr[:m.start()].endswith("−") and (m.start() == 1 or self._expr[m.start() - 2:m.start() - 1] in OPERATORS + "("):
                self._expr = self._expr[:m.start() - 1] + m.group(2)   # vorangestelltes Minus weg
            else:
                self._expr = self._expr[:m.start()] + "(−" + m.group(2) + ")"
        elif key == "√":
            # wie bei Windows: Wurzel aus der Zahl, die gerade dasteht
            self._start_fresh_if_done(True)
            m = re.search(r"[0-9,]+$", self._expr)
            if m:
                self._expr = self._expr[:m.start()] + "√" + m.group(0)
            elif self._last() == ")":
                depth, i = 0, len(self._expr) - 1
                while i >= 0:
                    depth += {")": 1, "(": -1}.get(self._expr[i], 0)
                    if depth == 0:
                        break
                    i -= 1
                self._expr = self._expr[:max(i, 0)] + "√" + self._expr[max(i, 0):]
            else:
                self._expr += "√"
        elif key == "x²":
            self._start_fresh_if_done(True)
            if self._expr and (self._expr[-1].isdigit() or self._expr[-1] in ")%"):
                self._expr += "^2"
        elif key == "1/x":
            self._start_fresh_if_done(True)
            if self._expr and self._expr[-1] not in OPERATORS + "(":
                self._expr = "1÷(" + self._expr + ")"
        if len(self._expr) > 120:
            self._expr = self._expr[:120]
        self.changed.emit()

    @Slot()
    def backspace(self):
        if self._done or self._error:
            self._done = False
            self._error = ""
            self._expr = ""
        else:
            self._expr = self._expr[:-2] if self._expr.endswith("^2") else self._expr[:-1]
        self.changed.emit()

    @Slot()
    def clear(self):
        self._expr, self._result, self._done, self._error = "", "", False, ""
        self.changed.emit()

    @Slot()
    def equals(self):
        if self._done or not self._expr:
            return
        expr = self._expr.rstrip(OPERATORS + "(")
        expr += ")" * max(0, expr.count("(") - expr.count(")"))
        try:
            value = evaluate(expr)
        except CalcError as exc:
            self._error = str(exc)
            self.changed.emit()
            return
        self._result = format_number(value)
        self._history.insert(0, {"expr": expr, "result": self._result})
        del self._history[50:]
        self._save()
        self._last_expr = expr
        self._done = True
        self.changed.emit()
        self.historyChanged.emit()

    @Slot(int)
    def useHistory(self, index):
        if 0 <= index < len(self._history):
            self._result = self._history[index]["result"]
            self._last_expr = self._history[index]["expr"]
            self._done, self._error = True, ""
            self.changed.emit()

    @Slot()
    def clearHistory(self):
        self._history = []
        self._save()
        self.historyChanged.emit()

    @Slot()
    def copy(self):
        text = (self._result if self._done else (self._preview() or self._expr)).replace(" ", "")
        if text:
            QGuiApplication.clipboard().setText(text)

    @Slot()
    def paste(self):
        text = QGuiApplication.clipboard().text().strip()
        if not text or len(text) > 100:
            return
        for ch in text:
            if ch in "0123456789,.+-*/×÷−%()":
                self.press({"(": "(", ")": ")"}.get(ch, ch))

    def _save(self):
        path = _history_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._history, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _top_line(self):
        if self._done:
            return getattr(self, "_last_expr", "") + " ="
        return ""

    display = Property(str, _display, notify=changed)
    topLine = Property(str, _top_line, notify=changed)
    preview = Property(str, _preview, notify=changed)
    error = Property(bool, lambda self: bool(self._error), notify=changed)
    done = Property(bool, lambda self: self._done, notify=changed)
    history = Property("QVariantList", lambda self: list(self._history), notify=historyChanged)
