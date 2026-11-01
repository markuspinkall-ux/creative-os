"""Das Textfeld von Creative Notes: Zeilennummern, Syntaxfarben, Komfort-Tasten."""

import re

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextOption,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from . import lexer
from .style import C

BRACKETS = {"(": ")", "[": "]", "{": "}"}
CLOSERS = {v: k for k, v in BRACKETS.items()}


def _fmt(color, bold=False, italic=False, underline=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    if underline:
        f.setFontUnderline(True)
    return f


FORMATS = {
    "keyword": _fmt(C["accent"], bold=True),
    "constant": _fmt(C["purple"]),
    "type": _fmt(C["teal"]),
    "builtin": _fmt(C["teal"]),
    "number": _fmt(C["purple"]),
    "string": _fmt(C["flame"]),
    "comment": _fmt(C["comment"], italic=True),
    "decorator": _fmt(C["yellow"]),
    "function": _fmt(C["blue2"], bold=True),
    "call": _fmt(C["blue2"]),
    "tag": _fmt(C["accent"], bold=True),
    "attribute": _fmt(C["teal"]),
    "key": _fmt(C["teal"]),
    "heading": _fmt(C["accent"], bold=True),
    "bold": _fmt(C["text"], bold=True),
    "italic": _fmt(C["text"], italic=True),
    "link": _fmt(C["teal"], underline=True),
}


class Highlighter(QSyntaxHighlighter):
    def __init__(self, document, lang="text"):
        super().__init__(document)
        self.lang = lang

    def set_language(self, lang):
        if lang != self.lang:
            self.lang = lang
            self.rehighlight()

    def highlightBlock(self, text):
        if self.lang == "text":
            self.setCurrentBlockState(0)
            return
        prev = self.previousBlockState()
        spans, state = lexer.highlight_line(self.lang, text, prev if prev > 0 else 0)
        for start, length, kind in spans:
            fmt = FORMATS.get(kind)
            if fmt is not None:
                self.setFormat(start, length, fmt)
        self.setCurrentBlockState(state)


class LineNumbers(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)

    def mousePressEvent(self, event):
        # Klick auf eine Zeilennummer markiert die ganze Zeile
        cur = self.editor.cursorForPosition(event.position().toPoint())
        cur.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cur.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        if not cur.atEnd():
            cur.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cur)


def mono_font(size):
    for family in ("JetBrains Mono", "Cascadia Code", "Source Code Pro", "Liberation Mono", "DejaVu Sans Mono", "Noto Sans Mono"):
        if family in QFontDatabase.families():
            f = QFont(family)
            break
    else:
        f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    f.setPointSizeF(size)
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setFixedPitch(True)
    return f


class CodeEditor(QPlainTextEdit):
    zoomChanged = Signal(int)
    filesDropped = Signal(list)

    BASE_SIZE = 11.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lang = "text"
        self.zoom = 0
        self.tab_width = 4
        self.use_spaces = True
        self.search_hits = []            # QTextCursor-Liste der Suchtreffer
        self.highlighter = Highlighter(self.document())
        self.gutter = LineNumbers(self)
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setCursorWidth(2)
        self.setAcceptDrops(True)
        self.apply_font()
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self.refresh_selections)
        self.selectionChanged.connect(self.refresh_selections)
        self._update_gutter_width()
        self.refresh_selections()

    # ---- Schrift / Zoom ----------------------------------------------------------------
    def apply_font(self):
        f = mono_font(max(5.0, self.BASE_SIZE + self.zoom))
        self.setFont(f)
        self.document().setDefaultFont(f)
        self.setTabStopDistance(QFontMetricsF(f).horizontalAdvance(" ") * self.tab_width)
        self._update_gutter_width()

    def set_zoom(self, z):
        z = max(-6, min(30, int(z)))
        if z != self.zoom:
            self.zoom = z
            self.apply_font()
            self.zoomChanged.emit(z)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            d = event.angleDelta().y()
            if d:
                self.set_zoom(self.zoom + (1 if d > 0 else -1))
            event.accept()
            return
        super().wheelEvent(event)

    def set_language(self, lang):
        self.lang = lang
        self.highlighter.set_language(lang)

    def set_wrap(self, on):
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if on else QPlainTextEdit.LineWrapMode.NoWrap)

    def set_show_whitespace(self, on):
        opt = self.document().defaultTextOption()
        flags = opt.flags()
        if on:
            flags |= QTextOption.Flag.ShowTabsAndSpaces | QTextOption.Flag.ShowLineAndParagraphSeparators
        else:
            flags &= ~(QTextOption.Flag.ShowTabsAndSpaces | QTextOption.Flag.ShowLineAndParagraphSeparators)
        opt.setFlags(flags)
        self.document().setDefaultTextOption(opt)

    # ---- Zeilennummern ---------------------------------------------------------------------
    def gutter_width(self):
        digits = max(3, len(str(max(1, self.blockCount()))))
        return int(22 + self.fontMetrics().horizontalAdvance("9") * digits)

    def _update_gutter_width(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        p = QPainter(self.gutter)
        p.fillRect(event.rect(), QColor(C["gutter"]))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        current = self.textCursor().blockNumber()
        f = self.font()
        p.setFont(f)
        w = self.gutter.width() - 12
        lh = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.setPen(QColor(C["text"] if num == current else C["linenum"]))
                p.drawText(0, top, w, lh, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num += 1
        p.end()

    # ---- Hervorhebungen: aktuelle Zeile, Klammerpaar, Suchtreffer, gleiches Wort -------------
    def refresh_selections(self):
        sels = []
        line = QTextEdit.ExtraSelection()
        line.format.setBackground(QColor(C["curline"]))
        line.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        line.cursor = self.textCursor()
        line.cursor.clearSelection()
        sels.append(line)

        for cur in self.search_hits[:5000]:
            s = QTextEdit.ExtraSelection()
            s.format.setBackground(QColor(C["hit"]))
            s.cursor = cur
            sels.append(s)

        # Gleiches Wort überall markieren (wie Notepad++ „Smart Highlighting“)
        tc = self.textCursor()
        if tc.hasSelection() and not self.search_hits:
            word = tc.selectedText()
            if 2 <= len(word) <= 80 and re.fullmatch(r"\w+", word):
                doc = self.document()
                c = doc.find(word, 0, QTextDocument.FindFlag.FindCaseSensitively | QTextDocument.FindFlag.FindWholeWords)
                count = 0
                while not c.isNull() and count < 2000:
                    if c.selectionStart() != tc.selectionStart():
                        s = QTextEdit.ExtraSelection()
                        s.format.setBackground(QColor(C["same"]))
                        s.cursor = c
                        sels.append(s)
                    c = doc.find(word, c, QTextDocument.FindFlag.FindCaseSensitively | QTextDocument.FindFlag.FindWholeWords)
                    count += 1

        sels.extend(self._bracket_selections())
        self.setExtraSelections(sels)

    def _bracket_selections(self):
        doc = self.document()
        pos = self.textCursor().position()
        for p in (pos, pos - 1):
            ch = doc.characterAt(p) if p >= 0 else ""
            if ch in BRACKETS or ch in CLOSERS:
                other = self._match_bracket(p, ch)
                out = []
                for q in ([p, other] if other is not None else [p]):
                    s = QTextEdit.ExtraSelection()
                    s.format.setBackground(QColor(C["bracket"] if other is not None else C["badbracket"]))
                    s.format.setForeground(QColor(C["text"]))
                    c = QTextCursor(doc)
                    c.setPosition(q)
                    c.setPosition(q + 1, QTextCursor.MoveMode.KeepAnchor)
                    s.cursor = c
                    out.append(s)
                return out
        return []

    def _match_bracket(self, p, ch, limit=200000):
        doc = self.document()
        if ch in BRACKETS:
            want, step = BRACKETS[ch], 1
        else:
            want, step = CLOSERS[ch], -1
        depth, q, n = 0, p, doc.characterCount()
        for _ in range(limit):
            c = doc.characterAt(q)
            if c == ch:
                depth += 1
            elif c == want:
                depth -= 1
                if depth == 0:
                    return q
            q += step
            if q < 0 or q >= n:
                return None
        return None

    # ---- Tasten ------------------------------------------------------------------------------
    def indent_unit(self):
        return " " * self.tab_width if self.use_spaces else "\t"

    def keyPressEvent(self, e):
        key, mods = e.key(), e.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        cur = self.textCursor()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not ctrl:
            block = cur.block().text()
            col = cur.positionInBlock()
            indent = re.match(r"[ \t]*", block).group(0)
            before = block[:col].rstrip()
            extra = self.indent_unit() if before.endswith((":", "{", "[", "(")) and self.lang not in ("text", "markdown") else ""
            after = block[col:].lstrip()
            cur.beginEditBlock()
            cur.insertText("\n" + indent + extra)
            if extra and after[:1] in ("}", "]", ")") and before[-1:] in "{[(":
                pos = cur.position()
                cur.insertText("\n" + indent)
                cur.setPosition(pos)
            cur.endEditBlock()
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            return
        if key == Qt.Key.Key_Tab and not ctrl:
            if cur.hasSelection() and " " in cur.selectedText():
                self.indent_lines(1)
            else:
                if self.use_spaces:
                    col = cur.positionInBlock()
                    cur.insertText(" " * (self.tab_width - col % self.tab_width))
                else:
                    cur.insertText("\t")
            return
        if key == Qt.Key.Key_Backtab:
            self.indent_lines(-1)
            return
        if key == Qt.Key.Key_Backspace and not cur.hasSelection() and self.use_spaces and not ctrl:
            # Rücktaste in der Einrückung löscht eine ganze Stufe
            text = cur.block().text()[:cur.positionInBlock()]
            if len(text) > 1 and not text.strip(" "):
                n = min(len(text) % self.tab_width or self.tab_width, len(text))
                cur.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, n)
                cur.removeSelectedText()
                return
        if key == Qt.Key.Key_Home and not ctrl:
            # Pos1: erst zum ersten Zeichen, dann an den Zeilenanfang
            text = cur.block().text()
            first = len(text) - len(text.lstrip())
            mode = QTextCursor.MoveMode.KeepAnchor if shift else QTextCursor.MoveMode.MoveAnchor
            target = 0 if cur.positionInBlock() == first else first
            cur.setPosition(cur.block().position() + target, mode)
            self.setTextCursor(cur)
            return
        if ctrl and shift and key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.move_lines(-1 if key == Qt.Key.Key_Up else 1)
            return
        if alt and key in (Qt.Key.Key_Up, Qt.Key.Key_Down) and not ctrl:
            self.move_lines(-1 if key == Qt.Key.Key_Up else 1)
            return
        if ctrl and not shift and key == Qt.Key.Key_D:
            self.duplicate_line()
            return
        if ctrl and not shift and key == Qt.Key.Key_L:
            self.delete_line()
            return
        if ctrl and key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.set_zoom(self.zoom + 1)
            return
        if ctrl and key == Qt.Key.Key_Minus:
            self.set_zoom(self.zoom - 1)
            return
        if ctrl and key == Qt.Key.Key_0:
            self.set_zoom(0)
            return
        super().keyPressEvent(e)

    # ---- Zeilen-Werkzeuge ----------------------------------------------------------------------
    def _line_range(self):
        cur = self.textCursor()
        doc = self.document()
        start = doc.findBlock(cur.selectionStart())
        end = doc.findBlock(cur.selectionEnd())
        if cur.hasSelection() and end.position() == cur.selectionEnd() and end != start:
            end = end.previous()
        return start, end

    def _select_lines(self, start, end):
        cur = QTextCursor(self.document())
        cur.setPosition(start.position())
        cur.setPosition(end.position() + end.length() - 1, QTextCursor.MoveMode.KeepAnchor)
        return cur

    def indent_lines(self, direction):
        start, end = self._line_range()
        unit = self.indent_unit()
        cur = QTextCursor(self.document())
        cur.beginEditBlock()
        block = start
        while True:
            c = QTextCursor(block)
            text = block.text()
            if direction > 0:
                if text.strip():
                    c.insertText(unit)
            else:
                lead = len(text) - len(text.lstrip(" \t"))
                if text.startswith("\t"):
                    n = 1
                else:
                    n = min(lead, self.tab_width)
                if n:
                    c.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor, n)
                    c.removeSelectedText()
            if block == end:
                break
            block = block.next()
        cur.endEditBlock()
        self.setTextCursor(self._select_lines(start, end))

    def duplicate_line(self):
        cur = self.textCursor()
        if cur.hasSelection():
            text = cur.selectedText()
            pos = cur.selectionEnd()
            c = QTextCursor(self.document())
            c.setPosition(pos)
            c.insertText(text.replace(" ", "\n"))
            return
        block = cur.block()
        c = QTextCursor(block)
        c.movePosition(QTextCursor.MoveOperation.EndOfBlock)
        c.insertText("\n" + block.text())
        cur.movePosition(QTextCursor.MoveOperation.Down)
        self.setTextCursor(cur)

    def delete_line(self):
        start, end = self._line_range()
        c = QTextCursor(self.document())
        c.setPosition(start.position())
        last = end.position() + end.length()
        if last > self.document().characterCount() - 1:
            # letzte Zeile: Zeilenumbruch davor mitnehmen
            last = self.document().characterCount() - 1
            if start.position() > 0:
                c.setPosition(start.position() - 1)
        c.setPosition(last, QTextCursor.MoveMode.KeepAnchor)
        c.removeSelectedText()

    def move_lines(self, direction):
        start, end = self._line_range()
        doc = self.document()
        if direction < 0 and not start.previous().isValid():
            return
        if direction > 0 and not end.next().isValid():
            return
        cur = self.textCursor()
        rel_a = cur.anchor() - start.position()
        rel_p = cur.position() - start.position()
        lines = self._select_lines(start, end).selectedText().replace(" ", "\n")
        c = QTextCursor(doc)
        c.beginEditBlock()
        if direction < 0:
            prev = start.previous()
            other = prev.text()
            c.setPosition(prev.position())
            c.setPosition(end.position() + end.length() - 1, QTextCursor.MoveMode.KeepAnchor)
            c.insertText(lines + "\n" + other)
            new_start = prev.position()
        else:
            nxt = end.next()
            other = nxt.text()
            c.setPosition(start.position())
            c.setPosition(nxt.position() + nxt.length() - 1, QTextCursor.MoveMode.KeepAnchor)
            c.insertText(other + "\n" + lines)
            new_start = start.position() + len(other) + 1
        c.endEditBlock()
        nc = QTextCursor(doc)
        nc.setPosition(new_start + rel_a)
        nc.setPosition(new_start + rel_p, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(nc)

    def toggle_comment(self):
        prefix = lexer.COMMENT_PREFIX.get(self.lang)
        if prefix is None:
            pair = lexer.BLOCK_COMMENT.get(self.lang)
            if not pair:
                return
            start, end = self._line_range()
            c = self._select_lines(start, end)
            text = c.selectedText().replace(" ", "\n")
            stripped = text.strip()
            if stripped.startswith(pair[0].strip()) and stripped.endswith(pair[1].strip()):
                inner = stripped[len(pair[0].strip()):-len(pair[1].strip())].strip(" ")
                lead = text[:len(text) - len(text.lstrip())]
                c.insertText(lead + inner)
            else:
                lead = text[:len(text) - len(text.lstrip())]
                c.insertText(lead + pair[0] + text.strip() + pair[1])
            return
        start, end = self._line_range()
        bare = prefix.strip()
        blocks, b = [], start
        while True:
            blocks.append(b)
            if b == end:
                break
            b = b.next()
        filled = [x for x in blocks if x.text().strip()]
        all_commented = filled and all(x.text().lstrip().startswith(bare) for x in filled)
        indent = min((len(x.text()) - len(x.text().lstrip()) for x in filled), default=0)
        cur = QTextCursor(self.document())
        cur.beginEditBlock()
        for x in blocks:
            text = x.text()
            if not text.strip():
                continue
            c = QTextCursor(x)
            if all_commented:
                i = text.index(bare)
                n = len(prefix) if text[i:i + len(prefix)] == prefix else len(bare)
                c.setPosition(x.position() + i)
                c.setPosition(x.position() + i + n, QTextCursor.MoveMode.KeepAnchor)
                c.removeSelectedText()
            else:
                c.setPosition(x.position() + indent)
                c.insertText(prefix)
        cur.endEditBlock()
        self.setTextCursor(self._select_lines(start, end))

    def transform_selection(self, fn, whole_lines=False):
        """Wendet fn(text) auf die Auswahl (oder ganze Zeilen) an."""
        cur = self.textCursor()
        if whole_lines or not cur.hasSelection():
            if whole_lines and not cur.hasSelection():
                cur = QTextCursor(self.document())
                cur.select(QTextCursor.SelectionType.Document)
            elif whole_lines:
                cur = self._select_lines(*self._line_range())
            else:
                cur.select(QTextCursor.SelectionType.WordUnderCursor)
        text = cur.selectedText().replace(" ", "\n")
        new = fn(text)
        if new != text:
            start = cur.selectionStart()
            cur.insertText(new)
            cur.setPosition(start)
            cur.setPosition(start + len(new), QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cur)

    # ---- Dateien hineinziehen -------------------------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.filesDropped.emit(paths)
                e.acceptProposedAction()
                return
        super().dropEvent(e)
