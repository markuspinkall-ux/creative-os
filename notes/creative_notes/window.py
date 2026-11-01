"""Hauptfenster von Creative Notes – Reiter, Menüs, Suchen, Sitzung."""

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QEvent, QFileSystemWatcher, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import fileio, lexer
from .editor import CodeEditor
from .style import icon_path


def _data_dir():
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    d = Path(base) / "creative-notes"
    (d / "backup").mkdir(parents=True, exist_ok=True)
    return d


def _config_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "creative-os" / "notes.json"


def icon(name):
    p = icon_path(name)
    return QIcon(p) if p else QIcon()


# ---- Ein geöffnetes Dokument ----------------------------------------------------------------
class Doc:
    def __init__(self, editor, path=None, untitled=None):
        self.editor = editor
        self.path = path
        self.untitled = untitled           # „Neu 1“ …
        self.encoding = "utf-8"
        self.eol = "lf"
        self.backup_id = uuid.uuid4().hex[:12]
        self.mtime = 0.0
        self.readonly = False

    @property
    def title(self):
        return Path(self.path).name if self.path else (self.untitled or "Neu")

    @property
    def modified(self):
        return self.editor.document().isModified()


# ---- Suchleiste --------------------------------------------------------------------------------
class FindBar(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("findbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        g = QGridLayout(self)
        g.setContentsMargins(14, 10, 14, 10)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(8)

        self.find = QLineEdit()
        self.find.setPlaceholderText("Suchen …")
        self.find.setClearButtonEnabled(True)
        self.replace = QLineEdit()
        self.replace.setPlaceholderText("Ersetzen durch …")
        self.count = QLabel("")
        self.count.setObjectName("count")
        self.count.setMinimumWidth(110)

        self.case = QCheckBox("Groß/klein")
        self.word = QCheckBox("Ganzes Wort")
        self.regex = QCheckBox("Regulärer Ausdruck")
        self.wrap = QCheckBox("Rundum")
        self.wrap.setChecked(True)

        prev = QPushButton("Zurück")
        nxt = QPushButton("Weiter")
        nxt.setProperty("primary", True)
        mark = QPushButton("Alle in allen Reitern")
        mark.setToolTip("Zählt die Treffer in allen geöffneten Dateien")
        rep = QPushButton("Ersetzen")
        rep_all = QPushButton("Alle ersetzen")
        close = QToolButton()
        close.setIcon(icon("close"))
        close.setIconSize(QSize(14, 14))
        close.setToolTip("Schließen (Esc)")

        g.addWidget(self.find, 0, 0)
        g.addWidget(prev, 0, 1)
        g.addWidget(nxt, 0, 2)
        g.addWidget(self.count, 0, 3)
        opts = QHBoxLayout()
        opts.setSpacing(14)
        for cb in (self.case, self.word, self.regex, self.wrap):
            opts.addWidget(cb)
        opts.addStretch(1)
        g.addLayout(opts, 0, 4)
        g.addWidget(close, 0, 5)

        self.rep_row = [self.replace, rep, rep_all, mark]
        g.addWidget(self.replace, 1, 0)
        g.addWidget(rep, 1, 1)
        g.addWidget(rep_all, 1, 2)
        g.addWidget(mark, 1, 3, 1, 2, Qt.AlignmentFlag.AlignLeft)
        g.setColumnStretch(0, 3)
        g.setColumnStretch(4, 2)

        self.find.textChanged.connect(self.live)
        for cb in (self.case, self.word, self.regex):
            cb.toggled.connect(self.live)
        self.find.returnPressed.connect(lambda: self.go(True))
        self.replace.returnPressed.connect(self.replace_one)
        nxt.clicked.connect(lambda: self.go(True))
        prev.clicked.connect(lambda: self.go(False))
        rep.clicked.connect(self.replace_one)
        rep_all.clicked.connect(self.replace_all)
        mark.clicked.connect(self.count_all_tabs)
        close.clicked.connect(self.hide_bar)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._mark)
        self.hide()

    # ---- Anzeigen ------------------------------------------------------------------------------
    def open_bar(self, with_replace):
        for w in self.rep_row:
            w.setVisible(with_replace)
        self.show()
        ed = self.win.editor()
        if ed:
            sel = ed.textCursor().selectedText()
            if sel and " " not in sel and len(sel) < 200:
                self.find.setText(sel)
        (self.replace if with_replace and self.find.text() else self.find).setFocus()
        self.find.selectAll()
        self.live()

    def hide_bar(self):
        self.hide()
        ed = self.win.editor()
        if ed:
            ed.search_hits = []
            ed.refresh_selections()
            ed.setFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide_bar()
            return
        super().keyPressEvent(e)

    # ---- Suchen --------------------------------------------------------------------------------
    def pattern(self):
        text = self.find.text()
        if not text:
            return None
        flags = 0 if self.case.isChecked() else re.IGNORECASE
        src = text if self.regex.isChecked() else re.escape(text)
        if self.word.isChecked():
            src = r"\b" + src + r"\b"
        try:
            rx = re.compile(src, flags | re.MULTILINE)
        except re.error:
            return False
        return rx

    def _matches(self, text, rx, limit=100000):
        out = []
        for m in rx.finditer(text):
            if m.end() == m.start():
                continue
            out.append((m.start(), m.end()))
            if len(out) >= limit:
                break
        return out

    def live(self):
        self._timer.start()

    def _mark(self):
        ed = self.win.editor()
        if not ed:
            return
        rx = self.pattern()
        self.find.setProperty("bad", rx is False)
        self.find.style().unpolish(self.find)
        self.find.style().polish(self.find)
        if not rx or not self.isVisible():
            ed.search_hits = []
            ed.refresh_selections()
            self.count.setText("Ungültiger Ausdruck" if rx is False else "")
            return
        text = ed.toPlainText()
        hits = self._matches(text, rx)
        doc = ed.document()
        cursors = []
        for a, b in hits[:5000]:
            c = QTextCursor(doc)
            c.setPosition(a)
            c.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
            cursors.append(c)
        ed.search_hits = cursors
        ed.refresh_selections()
        self._hits = hits
        self._update_count(ed)

    def _update_count(self, ed):
        hits = getattr(self, "_hits", [])
        if not hits:
            self.count.setText("Keine Treffer")
            return
        pos = ed.textCursor().selectionStart()
        idx = next((i for i, (a, b) in enumerate(hits) if a == pos), None)
        n = f"{len(hits)}+" if len(hits) >= 100000 else str(len(hits))
        self.count.setText(f"{idx + 1} von {n}" if idx is not None else f"{n} Treffer")

    def go(self, forward=True):
        ed = self.win.editor()
        rx = self.pattern()
        if not ed or not rx:
            return
        text = ed.toPlainText()
        cur = ed.textCursor()
        hits = self._matches(text, rx)
        self._hits = hits
        if not hits:
            self.count.setText("Keine Treffer")
            return
        if forward:
            start = cur.selectionEnd() if cur.hasSelection() else cur.position()
            nxt = next(((a, b) for a, b in hits if a >= start and (a, b) != (cur.selectionStart(), cur.selectionEnd())), None)
            if nxt is None and self.wrap.isChecked():
                nxt = hits[0]
        else:
            start = cur.selectionStart()
            nxt = next(((a, b) for a, b in reversed(hits) if a < start), None)
            if nxt is None and self.wrap.isChecked():
                nxt = hits[-1]
        if nxt is None:
            self.win.flash("Ende erreicht")
            return
        c = QTextCursor(ed.document())
        c.setPosition(nxt[0])
        c.setPosition(nxt[1], QTextCursor.MoveMode.KeepAnchor)
        ed.setTextCursor(c)
        ed.centerCursor()
        self._update_count(ed)

    def _replacement(self, match):
        if self.regex.isChecked():
            try:
                return match.expand(self.replace.text().replace("$", "\\"))
            except (re.error, IndexError):
                return self.replace.text()
        return self.replace.text()

    def replace_one(self):
        ed = self.win.editor()
        rx = self.pattern()
        if not ed or not rx:
            return
        cur = ed.textCursor()
        sel = cur.selectedText()
        if sel:
            m = rx.fullmatch(sel)
            if m:
                cur.insertText(self._replacement(m))
        self.go(True)
        self.live()

    def replace_all(self):
        ed = self.win.editor()
        rx = self.pattern()
        if not ed or not rx:
            return
        text = ed.toPlainText()
        count = [0]

        def sub(m):
            count[0] += 1
            return self._replacement(m)
        new = rx.sub(sub, text)
        if count[0]:
            cur = QTextCursor(ed.document())
            cur.beginEditBlock()
            cur.select(QTextCursor.SelectionType.Document)
            pos = ed.textCursor().position()
            cur.insertText(new)
            cur.endEditBlock()
            c = ed.textCursor()
            c.setPosition(min(pos, len(new)))
            ed.setTextCursor(c)
        self.win.flash(f"{count[0]} ersetzt" if count[0] else "Nichts zu ersetzen")
        self.live()

    def count_all_tabs(self):
        rx = self.pattern()
        if not rx:
            return
        parts = []
        total = 0
        for d in self.win.docs():
            n = len(self._matches(d.editor.toPlainText(), rx))
            if n:
                parts.append(f"{d.title}: {n}")
                total += n
        QMessageBox.information(self.win, "Treffer in allen Reitern",
                                (f"{total} Treffer\n\n" + "\n".join(parts)) if total else "Keine Treffer in den geöffneten Dateien.")


# ---- Hauptfenster -------------------------------------------------------------------------------------
class NotesWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Creative Notes")
        self.setWindowIcon(QIcon.fromTheme("creative-notes", icon("notes")))
        self.resize(1180, 760)
        self.setAcceptDrops(True)
        self.cfg = {"wrap": False, "whitespace": False, "zoom": 0, "recent": [], "lastDir": str(Path.home()),
                    "tabWidth": 4, "spaces": True, "geometry": None}
        try:
            stored = json.loads(_config_file().read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                self.cfg.update({k: v for k, v in stored.items() if k in self.cfg})
        except (OSError, ValueError):
            pass
        self._untitled = 0
        self._closed = []                    # zuletzt geschlossene Dateien (Strg+Umschalt+T)
        self._ignore_change = set()
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._file_changed)

        central = QWidget()
        central.setObjectName("central")
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_toolbar())

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabBarDoubleClicked.connect(lambda i: self.new_doc() if i < 0 else None)
        self.tabs.tabBar().installEventFilter(self)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._tab_menu)
        plus = QToolButton()
        plus.setObjectName("plus")
        plus.setIcon(icon("file-plus"))
        plus.setIconSize(QSize(15, 15))
        plus.setToolTip("Neuer Reiter (Strg+N)")
        plus.clicked.connect(self.new_doc)
        self.tabs.setCornerWidget(plus, Qt.Corner.TopRightCorner)
        lay.addWidget(self.tabs, 1)

        self.findbar = FindBar(self)
        lay.addWidget(self.findbar)
        self.setCentralWidget(central)

        self._build_menus()
        self._build_status()

        self._autosave = QTimer(self)
        self._autosave.setInterval(15000)
        self._autosave.timeout.connect(self.save_session)
        self._autosave.start()

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(lambda: self.st_msg.setText(""))

        if self.cfg.get("geometry"):
            try:
                x, y, w, h = self.cfg["geometry"]
                self.resize(w, h)
            except (TypeError, ValueError):
                pass

    # ---- Aufbau: Werkzeugleiste ------------------------------------------------------------------
    def _build_toolbar(self):
        bar = QWidget()
        bar.setObjectName("toolbar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(bar)
        h.setContentsMargins(10, 4, 10, 4)
        h.setSpacing(2)
        self._tb = {}

        def btn(key, ico, tip, slot, checkable=False):
            b = QToolButton()
            b.setIcon(icon(ico))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.clicked.connect(slot)
            h.addWidget(b)
            self._tb[key] = b
            return b

        def sep():
            f = QFrame()
            f.setObjectName("tsep")
            f.setFixedSize(1, 20)
            h.addSpacing(6)
            h.addWidget(f)
            h.addSpacing(6)

        btn("new", "file-plus", "Neu (Strg+N)", self.new_doc)
        btn("open", "open", "Öffnen (Strg+O)", self.open_dialog)
        btn("save", "save", "Speichern (Strg+S)", lambda: self.save())
        btn("saveall", "save-all", "Alle speichern (Strg+Umschalt+S)", self.save_all)
        sep()
        btn("undo", "undo", "Rückgängig (Strg+Z)", lambda: self.editor() and self.editor().undo())
        btn("redo", "redo", "Wiederholen (Strg+Y)", lambda: self.editor() and self.editor().redo())
        sep()
        btn("cut", "cut", "Ausschneiden (Strg+X)", lambda: self.editor() and self.editor().cut())
        btn("copy", "copy", "Kopieren (Strg+C)", lambda: self.editor() and self.editor().copy())
        btn("paste", "paste", "Einfügen (Strg+V)", lambda: self.editor() and self.editor().paste())
        sep()
        btn("find", "search", "Suchen (Strg+F)", lambda: self.findbar.open_bar(False))
        btn("replace", "replace", "Ersetzen (Strg+H)", lambda: self.findbar.open_bar(True))
        sep()
        btn("wrap", "wrap", "Automatischer Zeilenumbruch", lambda c: self.set_wrap(c), True)
        btn("ws", "whitespace", "Leerzeichen und Tabs anzeigen", lambda c: self.set_whitespace(c), True)
        sep()
        btn("zout", "zoom-out", "Verkleinern (Strg+−)", lambda: self.zoom_by(-1))
        btn("zin", "zoom-in", "Vergrößern (Strg++)", lambda: self.zoom_by(1))
        h.addStretch(1)
        self._tb["wrap"].setChecked(bool(self.cfg["wrap"]))
        self._tb["ws"].setChecked(bool(self.cfg["whitespace"]))
        return bar

    # ---- Aufbau: Menüs ---------------------------------------------------------------------------------
    def _act(self, menu, text, slot, shortcut=None, checkable=False, checked=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
            a.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        a.setCheckable(checkable)
        if checkable:
            a.setChecked(checked)
            a.toggled.connect(slot)
        else:
            a.triggered.connect(lambda *_: slot())
        menu.addAction(a)
        return a

    def _build_menus(self):
        mb = self.menuBar()
        ed = lambda: self.editor()          # noqa: E731

        m = mb.addMenu("&Datei")
        self._act(m, "Neu", self.new_doc, "Ctrl+N")
        self._act(m, "Öffnen …", self.open_dialog, "Ctrl+O")
        self.recent_menu = m.addMenu("Zuletzt geöffnet")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        self._act(m, "Neu laden", self.reload_current, "F5")
        m.addSeparator()
        self._act(m, "Speichern", lambda: self.save(), "Ctrl+S")
        self._act(m, "Speichern unter …", lambda: self.save(as_new=True), "Ctrl+Alt+S")
        self._act(m, "Alle speichern", self.save_all, "Ctrl+Shift+S")
        m.addSeparator()
        self._act(m, "Im Ordner zeigen", self.show_in_folder)
        self._act(m, "Pfad kopieren", self.copy_path)
        m.addSeparator()
        self._act(m, "Reiter schließen", lambda: self.close_tab(self.tabs.currentIndex()), "Ctrl+W")
        self._act(m, "Alle schließen", self.close_all, "Ctrl+Shift+W")
        self._act(m, "Geschlossenen Reiter wieder öffnen", self.reopen_closed, "Ctrl+Shift+T")
        m.addSeparator()
        self._act(m, "Beenden", self.close, "Ctrl+Q")

        m = mb.addMenu("&Bearbeiten")
        self._act(m, "Rückgängig", lambda: ed() and ed().undo(), QKeySequence.StandardKey.Undo)
        self._act(m, "Wiederholen", lambda: ed() and ed().redo(), "Ctrl+Y")
        m.addSeparator()
        self._act(m, "Ausschneiden", lambda: ed() and ed().cut(), QKeySequence.StandardKey.Cut)
        self._act(m, "Kopieren", lambda: ed() and ed().copy(), QKeySequence.StandardKey.Copy)
        self._act(m, "Einfügen", lambda: ed() and ed().paste(), QKeySequence.StandardKey.Paste)
        self._act(m, "Alles markieren", lambda: ed() and ed().selectAll(), QKeySequence.StandardKey.SelectAll)
        m.addSeparator()
        lines = m.addMenu("Zeilen")
        self._act(lines, "Zeile duplizieren\tStrg+D", lambda: ed() and ed().duplicate_line())
        self._act(lines, "Zeile löschen\tStrg+L", lambda: ed() and ed().delete_line())
        self._act(lines, "Nach oben verschieben\tStrg+Umschalt+↑", lambda: ed() and ed().move_lines(-1))
        self._act(lines, "Nach unten verschieben\tStrg+Umschalt+↓", lambda: ed() and ed().move_lines(1))
        lines.addSeparator()
        self._act(lines, "Sortieren (A → Z)", lambda: self._lines(lambda t: "\n".join(sorted(t.split("\n"), key=str.casefold))))
        self._act(lines, "Sortieren (Z → A)", lambda: self._lines(lambda t: "\n".join(sorted(t.split("\n"), key=str.casefold, reverse=True))))
        self._act(lines, "Doppelte Zeilen entfernen", lambda: self._lines(lambda t: "\n".join(dict.fromkeys(t.split("\n")))))
        self._act(lines, "Leere Zeilen entfernen", lambda: self._lines(lambda t: "\n".join(l for l in t.split("\n") if l.strip())))
        self._act(lines, "Leerzeichen am Zeilenende entfernen", lambda: self._lines(lambda t: "\n".join(l.rstrip() for l in t.split("\n"))))
        case = m.addMenu("Groß-/Kleinschreibung")
        self._act(case, "GROSSBUCHSTABEN", lambda: ed() and ed().transform_selection(str.upper), "Ctrl+Shift+U")
        self._act(case, "kleinbuchstaben", lambda: ed() and ed().transform_selection(str.lower), "Ctrl+U")
        self._act(case, "Wörter Groß Schreiben", lambda: ed() and ed().transform_selection(lambda t: re.sub(r"\w+", lambda w: w.group(0)[:1].upper() + w.group(0)[1:].lower(), t)))
        self._act(case, "Satzanfang groß", lambda: ed() and ed().transform_selection(lambda t: re.sub(r"(^|[.!?]\s+)(\w)", lambda w: w.group(1) + w.group(2).upper(), t.lower())))
        self._act(case, "uMKEHREN", lambda: ed() and ed().transform_selection(str.swapcase))
        m.addSeparator()
        self._act(m, "Kommentar an/aus", lambda: ed() and ed().toggle_comment(), "Ctrl+/")
        self._act(m, "Einrücken", lambda: ed() and ed().indent_lines(1))
        self._act(m, "Ausrücken\tUmschalt+Tab", lambda: ed() and ed().indent_lines(-1))
        self._act(m, "Tabs in Leerzeichen umwandeln", lambda: self._lines(lambda t: t.expandtabs(self.cfg["tabWidth"])))
        self._act(m, "Datum und Uhrzeit einfügen", lambda: ed() and ed().insertPlainText(time.strftime("%d.%m.%Y %H:%M")), "F7")

        m = mb.addMenu("&Suchen")
        self._act(m, "Suchen …", lambda: self.findbar.open_bar(False), "Ctrl+F")
        self._act(m, "Ersetzen …", lambda: self.findbar.open_bar(True), "Ctrl+H")
        self._act(m, "Weitersuchen", lambda: self._find_step(True), "F3")
        self._act(m, "Rückwärts suchen", lambda: self._find_step(False), "Shift+F3")
        m.addSeparator()
        self._act(m, "Gehe zu Zeile …", self.goto_line, "Ctrl+G")
        self._act(m, "Passende Klammer", self.goto_bracket, "Ctrl+B")

        m = mb.addMenu("&Ansicht")
        self.a_wrap = self._act(m, "Automatischer Zeilenumbruch", self.set_wrap, "Alt+Z", checkable=True, checked=bool(self.cfg["wrap"]))
        self.a_ws = self._act(m, "Leerzeichen und Tabs anzeigen", self.set_whitespace, checkable=True, checked=bool(self.cfg["whitespace"]))
        m.addSeparator()
        self._act(m, "Vergrößern", lambda: self.zoom_by(1))
        self._act(m, "Verkleinern", lambda: self.zoom_by(-1))
        self._act(m, "Normale Größe", lambda: self.zoom_by(None))
        m.addSeparator()
        self._act(m, "Vollbild", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen(), "F11")
        self._act(m, "Nächster Reiter", lambda: self._cycle(1), "Ctrl+Tab")
        self._act(m, "Vorheriger Reiter", lambda: self._cycle(-1), "Ctrl+Shift+Tab")

        m = mb.addMenu("&Kodierung")
        self.enc_group = QActionGroup(self)
        self.enc_actions = {}
        for key, label, *_ in fileio.ENCODINGS:
            a = self._act(m, f"In {label} umwandeln", lambda k=key: self.set_encoding(k))
            a.setCheckable(True)
            self.enc_group.addAction(a)
            self.enc_actions[key] = a
        m.addSeparator()
        reread = m.addMenu("Neu lesen als …")
        for key, label, *_ in fileio.ENCODINGS:
            self._act(reread, label, lambda k=key: self.reread_as(k))
        m.addSeparator()
        self.eol_group = QActionGroup(self)
        self.eol_actions = {}
        for key, (_, label) in fileio.EOLS.items():
            a = self._act(m, f"Zeilenende: {label}", lambda k=key: self.set_eol(k))
            a.setCheckable(True)
            self.eol_group.addAction(a)
            self.eol_actions[key] = a
        m.addSeparator()
        tabs = m.addMenu("Einrückung")
        self.a_spaces = self._act(tabs, "Leerzeichen statt Tabs", self._set_spaces, checkable=True, checked=bool(self.cfg["spaces"]))
        tabs.addSeparator()
        self.tw_group = QActionGroup(self)
        for n in (2, 4, 8):
            a = self._act(tabs, f"Breite {n}", lambda k=n: self._set_tab_width(k))
            a.setCheckable(True)
            a.setChecked(n == self.cfg["tabWidth"])
            self.tw_group.addAction(a)

        m = mb.addMenu("S&prache")
        self.lang_group = QActionGroup(self)
        self.lang_actions = {}
        for key in sorted(lexer.LANGUAGES, key=lambda k: (k != "text", lexer.LANGUAGES[k]["name"].casefold())):
            a = self._act(m, lexer.LANGUAGES[key]["name"], lambda k=key: self.set_language(k))
            a.setCheckable(True)
            self.lang_group.addAction(a)
            self.lang_actions[key] = a
            if key == "text":
                m.addSeparator()

        m = mb.addMenu("&Hilfe")
        self._act(m, "Tastenkürzel", self.show_shortcuts, "F1")
        self._act(m, "Über Creative Notes", self.show_about)

    def _build_status(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.st_msg = QLabel("")
        self.st_pos = QLabel("")
        self.st_len = QLabel("")
        sb.addWidget(self.st_msg, 1)
        sb.addPermanentWidget(self.st_len)
        sb.addPermanentWidget(self.st_pos)

        def menu_button(menu_fill):
            b = QToolButton()
            b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            m = QMenu(b)
            m.aboutToShow.connect(lambda: menu_fill(m))
            b.setMenu(m)
            sb.addPermanentWidget(b)
            return b

        def fill_lang(m):
            m.clear()
            for key in sorted(lexer.LANGUAGES, key=lambda k: (k != "text", lexer.LANGUAGES[k]["name"].casefold())):
                a = m.addAction(lexer.LANGUAGES[key]["name"])
                a.triggered.connect(lambda *_, k=key: self.set_language(k))

        def fill_eol(m):
            m.clear()
            for key, (_, label) in fileio.EOLS.items():
                a = m.addAction(label)
                a.triggered.connect(lambda *_, k=key: self.set_eol(k))

        def fill_enc(m):
            m.clear()
            for key, label, *_ in fileio.ENCODINGS:
                a = m.addAction(f"In {label} umwandeln")
                a.triggered.connect(lambda *_, k=key: self.set_encoding(k))

        self.st_eol = menu_button(fill_eol)
        self.st_enc = menu_button(fill_enc)
        self.st_lang = menu_button(fill_lang)
        self.st_zoom = QLabel("")
        sb.addPermanentWidget(self.st_zoom)

    # ---- Zugriff --------------------------------------------------------------------------------
    def docs(self):
        return [self.tabs.widget(i).doc for i in range(self.tabs.count())]

    def doc(self):
        w = self.tabs.currentWidget()
        return w.doc if w is not None else None

    def editor(self):
        d = self.doc()
        return d.editor if d else None

    def flash(self, text, ms=3500):
        self.st_msg.setText(text)
        self._flash_timer.start(ms)

    # ---- Dokumente anlegen -----------------------------------------------------------------------
    def _make_editor(self):
        ed = CodeEditor()
        ed.tab_width = int(self.cfg["tabWidth"])
        ed.use_spaces = bool(self.cfg["spaces"])
        ed.zoom = int(self.cfg["zoom"])
        ed.apply_font()
        ed.set_wrap(bool(self.cfg["wrap"]))
        ed.set_show_whitespace(bool(self.cfg["whitespace"]))
        ed.cursorPositionChanged.connect(self._update_status)
        ed.selectionChanged.connect(self._update_status)
        ed.textChanged.connect(self._text_changed)
        ed.document().modificationChanged.connect(lambda *_: self._refresh_tab(ed))
        ed.zoomChanged.connect(self._zoom_changed)
        ed.filesDropped.connect(self.open_paths)
        ed.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        ed.customContextMenuRequested.connect(lambda pos, e=ed: self._editor_menu(e, pos))
        return ed

    def _add(self, doc, focus=True):
        doc.editor.doc = doc
        i = self.tabs.addTab(doc.editor, doc.title)
        self._refresh_tab(doc.editor)
        if focus:
            self.tabs.setCurrentIndex(i)
            doc.editor.setFocus()
        return i

    def new_doc(self, text="", focus=True):
        self._untitled += 1
        d = Doc(self._make_editor(), untitled=f"Neu {self._untitled}")
        if text:
            d.editor.setPlainText(text)
        d.editor.document().setModified(False)
        self._add(d, focus)
        return d

    def _blank_single(self):
        """Ein leerer, unveränderter „Neu“-Reiter wird beim Öffnen einer Datei ersetzt."""
        if self.tabs.count() == 1:
            d = self.docs()[0]
            if d.path is None and not d.modified and not d.editor.toPlainText():
                return d
        return None

    def open_paths(self, paths):
        last = None
        for p in paths:
            p = str(Path(p).expanduser())
            if os.path.isdir(p):
                continue
            last = self.open_file(p) or last
        return last

    def open_file(self, path, focus=True, quiet=False):
        path = os.path.abspath(path)
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i).doc
            if d.path and os.path.abspath(d.path) == path:
                if focus:
                    self.tabs.setCurrentIndex(i)
                return d
        if not os.path.exists(path):
            # Neue Datei mit diesem Namen anlegen (wie Notepad++)
            if quiet:
                return None
            r = QMessageBox.question(self, "Datei gibt es nicht",
                                     f"„{Path(path).name}“ gibt es noch nicht.\nSoll die Datei angelegt werden?")
            if r != QMessageBox.StandardButton.Yes:
                return None
            try:
                Path(path).touch()
            except OSError as exc:
                QMessageBox.warning(self, "Nicht möglich", f"Die Datei lässt sich nicht anlegen:\n{exc}")
                return None
        try:
            data = fileio.read_file(path)
        except fileio.FileTooBig as exc:
            if quiet:
                return None
            mb = int(exc.args[0]) // (1024 * 1024)
            if QMessageBox.question(self, "Sehr große Datei",
                                    f"Die Datei ist {mb} MB groß. Das Öffnen kann dauern.\nTrotzdem öffnen?") != QMessageBox.StandardButton.Yes:
                return None
            data = fileio.read_file(path, force=True)
        except fileio.BinaryFile:
            if quiet:
                return None
            if QMessageBox.question(self, "Keine Textdatei",
                                    f"„{Path(path).name}“ scheint keine Textdatei zu sein.\nTrotzdem als Text öffnen?") != QMessageBox.StandardButton.Yes:
                return None
            data = fileio.read_file(path, force=True)
        except OSError as exc:
            if not quiet:
                QMessageBox.warning(self, "Öffnen nicht möglich", f"„{Path(path).name}“ lässt sich nicht öffnen:\n{exc.strerror or exc}")
            return None

        blank = self._blank_single()
        d = Doc(self._make_editor(), path=path)
        d.encoding, d.eol = data["encoding"], data["eol"]
        d.editor.setPlainText(data["text"])
        d.editor.set_language(lexer.detect(path, data["text"].split("\n", 1)[0]))
        d.editor.document().setModified(False)
        d.mtime = os.path.getmtime(path)
        d.readonly = not os.access(path, os.W_OK)
        self._add(d, focus)
        if blank is not None:
            self._remove_tab(self.tabs.indexOf(blank.editor))
        self.watcher.addPath(path)
        self._add_recent(path)
        self.cfg["lastDir"] = str(Path(path).parent)
        return d

    def open_dialog(self):
        start = self.cfg.get("lastDir") or str(Path.home())
        d = self.doc()
        if d and d.path:
            start = str(Path(d.path).parent)
        paths, _ = QFileDialog.getOpenFileNames(self, "Öffnen", start, "Alle Dateien (*);;Textdateien (*.txt *.md *.log)")
        if paths:
            self.open_paths(paths)

    # ---- Speichern -----------------------------------------------------------------------------------
    def save(self, doc=None, as_new=False):
        d = doc or self.doc()
        if not d:
            return False
        path = d.path
        if as_new or not path:
            start = path or os.path.join(self.cfg.get("lastDir") or str(Path.home()), d.title if d.title.count(".") else d.title + ".txt")
            path, _ = QFileDialog.getSaveFileName(self, "Speichern unter", start, "Alle Dateien (*)")
            if not path:
                return False
        text = d.editor.toPlainText()
        if fileio.unencodable(text, d.encoding):
            r = QMessageBox.question(
                self, "Zeichen gehen verloren",
                f"Einige Zeichen passen nicht in {fileio.ENC[d.encoding][0]}.\nStattdessen als UTF-8 speichern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Cancel:
                return False
            if r == QMessageBox.StandardButton.Yes:
                d.encoding = "utf-8"
        self._ignore_change.add(path)
        try:
            fileio.write_file(path, text, d.encoding, d.eol)
        except PermissionError:
            r = QMessageBox.question(
                self, "Keine Berechtigung",
                f"„{Path(path).name}“ darf nur ein Administrator ändern.\nMit Administratorrechten speichern?")
            if r != QMessageBox.StandardButton.Yes:
                self._ignore_change.discard(path)
                return False
            try:
                fileio.write_file_as_admin(path, text, d.encoding, d.eol)
            except (PermissionError, OSError, subprocess.SubprocessError) as exc:
                self._ignore_change.discard(path)
                QMessageBox.warning(self, "Nicht gespeichert", f"Speichern hat nicht geklappt:\n{exc}")
                return False
        except OSError as exc:
            self._ignore_change.discard(path)
            QMessageBox.warning(self, "Nicht gespeichert", f"Speichern hat nicht geklappt:\n{exc.strerror or exc}")
            return False
        QTimer.singleShot(800, lambda p=path: self._ignore_change.discard(p))
        if d.path != path:
            if d.path:
                self.watcher.removePath(d.path)
            d.path = path
            d.untitled = None
            if d.editor.lang == "text":
                d.editor.set_language(lexer.detect(path, text.split("\n", 1)[0]))
        if path not in self.watcher.files():
            self.watcher.addPath(path)
        d.mtime = os.path.getmtime(path)
        d.readonly = False
        d.editor.document().setModified(False)
        self._add_recent(path)
        self.cfg["lastDir"] = str(Path(path).parent)
        self._refresh_tab(d.editor)
        self._update_status()
        self.flash(f"Gespeichert: {Path(path).name}")
        self.save_session()
        return True

    def save_all(self):
        for d in self.docs():
            if d.modified or not d.path and d.editor.toPlainText():
                i = self.tabs.indexOf(d.editor)
                self.tabs.setCurrentIndex(i)
                if not self.save(d):
                    return False
        return True

    # ---- Schließen -------------------------------------------------------------------------------------
    def _ask_save(self, d):
        r = QMessageBox.question(
            self, "Änderungen speichern?", f"„{d.title}“ wurde geändert.\nMöchtest du die Änderungen speichern?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if r == QMessageBox.StandardButton.Save:
            return self.save(d)
        return r == QMessageBox.StandardButton.Discard

    def close_tab(self, index):
        if index < 0:
            return
        d = self.tabs.widget(index).doc
        if d.modified and (d.path or d.editor.toPlainText()):
            self.tabs.setCurrentIndex(index)
            if not self._ask_save(d):
                return
        if d.path:
            self._closed.append(d.path)
            del self._closed[:-20]
        self._remove_tab(index)
        if self.tabs.count() == 0:
            self.new_doc()

    def _remove_tab(self, index):
        w = self.tabs.widget(index)
        d = w.doc
        if d.path and d.path in self.watcher.files() and not any(o is not d and o.path == d.path for o in self.docs()):
            self.watcher.removePath(d.path)
        try:
            (_data_dir() / "backup" / f"{d.backup_id}.txt").unlink()
        except OSError:
            pass
        self.tabs.removeTab(index)
        w.deleteLater()

    def close_all(self):
        for i in reversed(range(self.tabs.count())):
            before = self.tabs.count()
            self.close_tab(i)
            if self.tabs.count() == before and before > 0 and self.tabs.widget(min(i, self.tabs.count() - 1)).doc.modified:
                return

    def close_others(self, keep):
        for i in reversed(range(self.tabs.count())):
            if i != keep:
                self.close_tab(i)

    def reopen_closed(self):
        while self._closed:
            p = self._closed.pop()
            if os.path.exists(p):
                self.open_file(p)
                return

    def closeEvent(self, e):
        # Wie Notepad++: nichts geht verloren – auch ungespeicherte Texte
        # kommen beim nächsten Start wieder.
        self.save_session()
        self.cfg["geometry"] = [self.x(), self.y(), self.width(), self.height()]
        self._save_cfg()
        e.accept()

    # ---- Sitzung ----------------------------------------------------------------------------------------
    def save_session(self):
        data_dir = _data_dir()
        tabs, keep = [], set()
        for d in self.docs():
            ed = d.editor
            entry = {"path": d.path, "untitled": d.untitled, "encoding": d.encoding, "eol": d.eol,
                     "lang": ed.lang, "cursor": ed.textCursor().position(),
                     "scroll": ed.verticalScrollBar().value(), "mtime": d.mtime}
            if d.modified or (not d.path and ed.toPlainText()):
                entry["backup"] = d.backup_id
                keep.add(d.backup_id)
                try:
                    (data_dir / "backup" / f"{d.backup_id}.txt").write_text(ed.toPlainText(), encoding="utf-8")
                except OSError:
                    pass
            tabs.append(entry)
        session = {"tabs": tabs, "current": self.tabs.currentIndex(), "untitled": self._untitled}
        try:
            tmp = data_dir / "session.json.tmp"
            tmp.write_text(json.dumps(session, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(data_dir / "session.json")
        except OSError:
            pass
        for f in (data_dir / "backup").glob("*.txt"):
            if f.stem not in keep:
                try:
                    f.unlink()
                except OSError:
                    pass

    def restore_session(self):
        data_dir = _data_dir()
        try:
            session = json.loads((data_dir / "session.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        self._untitled = int(session.get("untitled") or 0)
        for t in session.get("tabs", []):
            backup = None
            if t.get("backup"):
                try:
                    backup = (data_dir / "backup" / f"{t['backup']}.txt").read_text(encoding="utf-8")
                except OSError:
                    backup = None
            d = None
            if t.get("path"):
                if os.path.exists(t["path"]):
                    d = self.open_file(t["path"], focus=False, quiet=True)
                elif backup is None:
                    continue
                if d is None:
                    d = Doc(self._make_editor(), path=t["path"])
                    self._add(d, focus=False)
            else:
                if backup is None:
                    continue
                d = Doc(self._make_editor(), untitled=t.get("untitled") or "Neu")
                self._add(d, focus=False)
            d.encoding = t.get("encoding") or d.encoding
            d.eol = t.get("eol") or d.eol
            if backup is not None:
                d.editor.setPlainText(backup)
                d.editor.document().setModified(True)
                if t.get("backup"):
                    d.backup_id = t["backup"]
            if t.get("lang") in lexer.LANGUAGES:
                d.editor.set_language(t["lang"])
            c = d.editor.textCursor()
            c.setPosition(min(int(t.get("cursor") or 0), d.editor.document().characterCount() - 1))
            d.editor.setTextCursor(c)
            QTimer.singleShot(0, lambda e=d.editor, v=int(t.get("scroll") or 0): e.verticalScrollBar().setValue(v))
            self._refresh_tab(d.editor)
        if self.tabs.count():
            self.tabs.setCurrentIndex(max(0, min(int(session.get("current") or 0), self.tabs.count() - 1)))
            return True
        return False

    def _save_cfg(self):
        p = _config_file()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    # ---- Zuletzt geöffnet ---------------------------------------------------------------------------------
    def _add_recent(self, path):
        r = [p for p in self.cfg["recent"] if p != path]
        r.insert(0, path)
        self.cfg["recent"] = r[:15]
        self._save_cfg()

    def _fill_recent(self):
        self.recent_menu.clear()
        recent = [p for p in self.cfg["recent"] if os.path.exists(p)]
        for p in recent:
            a = self.recent_menu.addAction(f"{Path(p).name}   —   {Path(p).parent}")
            a.triggered.connect(lambda *_, x=p: self.open_file(x))
        if not recent:
            a = self.recent_menu.addAction("Noch nichts geöffnet")
            a.setEnabled(False)
        else:
            self.recent_menu.addSeparator()
            a = self.recent_menu.addAction("Liste leeren")
            a.triggered.connect(lambda: (self.cfg.update(recent=[]), self._save_cfg()))

    # ---- Datei von außen geändert ------------------------------------------------------------------------
    def _file_changed(self, path):
        QTimer.singleShot(300, lambda: self._check_external(path))

    def _check_external(self, path):
        if path in self._ignore_change:
            if os.path.exists(path) and path not in self.watcher.files():
                self.watcher.addPath(path)
            return
        for d in self.docs():
            if d.path != path:
                continue
            if not os.path.exists(path):
                self.flash(f"„{d.title}“ wurde gelöscht oder verschoben – der Text bleibt hier erhalten.", 8000)
                d.editor.document().setModified(True)
                continue
            if path not in self.watcher.files():
                self.watcher.addPath(path)
            mtime = os.path.getmtime(path)
            if abs(mtime - d.mtime) < 0.001:
                continue
            d.mtime = mtime
            if not d.modified:
                self._reload(d)
                self.flash(f"„{d.title}“ wurde von außen geändert und neu geladen.")
            else:
                i = self.tabs.indexOf(d.editor)
                self.tabs.setCurrentIndex(i)
                r = QMessageBox.question(self, "Datei wurde geändert",
                                         f"„{d.title}“ wurde von einem anderen Programm geändert.\n"
                                         "Neu laden? Deine ungespeicherten Änderungen gehen dabei verloren.")
                if r == QMessageBox.StandardButton.Yes:
                    self._reload(d)

    def _reload(self, d, encoding=None):
        try:
            if encoding:
                text = fileio.reinterpret(d.path, encoding)
                d.encoding = encoding
            else:
                data = fileio.read_file(d.path, force=True)
                text, d.encoding, d.eol = data["text"], data["encoding"], data["eol"]
        except OSError as exc:
            QMessageBox.warning(self, "Neu laden nicht möglich", str(exc))
            return
        ed = d.editor
        pos, scroll = ed.textCursor().position(), ed.verticalScrollBar().value()
        cur = QTextCursor(ed.document())
        cur.beginEditBlock()
        cur.select(QTextCursor.SelectionType.Document)
        cur.insertText(text)
        cur.endEditBlock()
        c = ed.textCursor()
        c.setPosition(min(pos, ed.document().characterCount() - 1))
        ed.setTextCursor(c)
        ed.verticalScrollBar().setValue(scroll)
        ed.document().setModified(False)
        d.mtime = os.path.getmtime(d.path)
        self._update_status()

    def reload_current(self):
        d = self.doc()
        if not d or not d.path:
            return
        if d.modified and QMessageBox.question(self, "Neu laden", "Ungespeicherte Änderungen verwerfen und neu laden?") != QMessageBox.StandardButton.Yes:
            return
        self._reload(d)

    # ---- Einstellungen ---------------------------------------------------------------------------------------
    def set_wrap(self, on):
        on = bool(on)
        self.cfg["wrap"] = on
        for d in self.docs():
            d.editor.set_wrap(on)
        self._sync_toggle(self.a_wrap if hasattr(self, "a_wrap") else None, self._tb["wrap"], on)
        self._save_cfg()

    def set_whitespace(self, on):
        on = bool(on)
        self.cfg["whitespace"] = on
        for d in self.docs():
            d.editor.set_show_whitespace(on)
        self._sync_toggle(self.a_ws if hasattr(self, "a_ws") else None, self._tb["ws"], on)
        self._save_cfg()

    @staticmethod
    def _sync_toggle(action, button, on):
        for w in (action, button):
            if w is not None and w.isChecked() != on:
                w.blockSignals(True)
                w.setChecked(on)
                w.blockSignals(False)

    def zoom_by(self, delta):
        ed = self.editor()
        if ed:
            ed.set_zoom(0 if delta is None else ed.zoom + delta)

    def _zoom_changed(self, z):
        self.cfg["zoom"] = z
        for d in self.docs():
            if d.editor.zoom != z:
                d.editor.blockSignals(True)
                d.editor.set_zoom(z)
                d.editor.blockSignals(False)
        self._save_cfg()
        self._update_status()

    def _set_spaces(self, on):
        self.cfg["spaces"] = bool(on)
        for d in self.docs():
            d.editor.use_spaces = bool(on)
        self._save_cfg()

    def _set_tab_width(self, n):
        self.cfg["tabWidth"] = n
        for d in self.docs():
            d.editor.tab_width = n
            d.editor.apply_font()
        self._save_cfg()

    def set_language(self, key):
        d = self.doc()
        if d:
            d.editor.set_language(key)
            self._update_status()

    def set_encoding(self, key):
        d = self.doc()
        if d and d.encoding != key:
            d.encoding = key
            d.editor.document().setModified(True)
            self._update_status()
            self.flash(f"Wird beim Speichern als {fileio.ENC[key][0]} geschrieben")

    def reread_as(self, key):
        d = self.doc()
        if not d or not d.path:
            return
        if d.modified and QMessageBox.question(self, "Neu lesen", "Ungespeicherte Änderungen verwerfen?") != QMessageBox.StandardButton.Yes:
            return
        self._reload(d, encoding=key)

    def set_eol(self, key):
        d = self.doc()
        if d and d.eol != key:
            d.eol = key
            d.editor.document().setModified(True)
            self._update_status()

    # ---- Bearbeiten-Helfer ------------------------------------------------------------------------------------
    def _lines(self, fn):
        ed = self.editor()
        if ed:
            ed.transform_selection(fn, whole_lines=True)

    def _find_step(self, forward):
        if not self.findbar.find.text():
            ed = self.editor()
            sel = ed.textCursor().selectedText() if ed else ""
            if not sel:
                self.findbar.open_bar(False)
                return
            self.findbar.find.setText(sel)
        self.findbar.go(forward)

    def goto_line(self):
        ed = self.editor()
        if not ed:
            return
        n, ok = QInputDialog.getInt(self, "Gehe zu Zeile", f"Zeile (1 – {ed.blockCount()}):",
                                    ed.textCursor().blockNumber() + 1, 1, ed.blockCount())
        if ok:
            block = ed.document().findBlockByNumber(n - 1)
            c = ed.textCursor()
            c.setPosition(block.position())
            ed.setTextCursor(c)
            ed.centerCursor()
            ed.setFocus()

    def goto_bracket(self):
        ed = self.editor()
        if not ed:
            return
        doc = ed.document()
        pos = ed.textCursor().position()
        for p in (pos, pos - 1):
            ch = doc.characterAt(p) if p >= 0 else ""
            if ch in "()[]{}":
                other = ed._match_bracket(p, ch)
                if other is not None:
                    c = ed.textCursor()
                    c.setPosition(other + (1 if ch in "([{" else 0))
                    ed.setTextCursor(c)
                return

    def show_in_folder(self):
        d = self.doc()
        if d and d.path:
            subprocess.Popen(["creative-files", str(Path(d.path).parent)], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def copy_path(self):
        d = self.doc()
        if d and d.path:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(d.path)
            self.flash("Pfad kopiert")

    def _cycle(self, step):
        n = self.tabs.count()
        if n > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % n)

    # ---- Kontextmenüs -------------------------------------------------------------------------------------------
    def _editor_menu(self, ed, pos):
        m = QMenu(ed)
        has = ed.textCursor().hasSelection()
        for text, slot, enabled in (("Rückgängig", ed.undo, ed.document().isUndoAvailable()),
                                    ("Wiederholen", ed.redo, ed.document().isRedoAvailable()),
                                    (None, None, None),
                                    ("Ausschneiden", ed.cut, has), ("Kopieren", ed.copy, has), ("Einfügen", ed.paste, ed.canPaste()),
                                    ("Löschen", lambda: ed.textCursor().removeSelectedText(), has),
                                    (None, None, None),
                                    ("Alles markieren", ed.selectAll, True),
                                    ("Kommentar an/aus", ed.toggle_comment, lexer.COMMENT_PREFIX.get(ed.lang) is not None or ed.lang in lexer.BLOCK_COMMENT),
                                    ("GROSS", lambda: ed.transform_selection(str.upper), has),
                                    ("klein", lambda: ed.transform_selection(str.lower), has)):
            if text is None:
                m.addSeparator()
                continue
            a = m.addAction(text)
            a.setEnabled(bool(enabled))
            a.triggered.connect(lambda *_, s=slot: s())
        if has:
            m.addSeparator()
            a = m.addAction("Im Internet suchen")
            sel = ed.textCursor().selectedText()[:200]
            a.triggered.connect(lambda: subprocess.Popen(["xdg-open", "https://search.brave.com/search?q=" + __import__("urllib.parse").parse.quote(sel)],
                                                         start_new_session=True))
        m.exec(ed.viewport().mapToGlobal(pos))

    def _tab_menu(self, pos):
        bar = self.tabs.tabBar()
        i = bar.tabAt(pos)
        if i < 0:
            return
        d = self.tabs.widget(i).doc
        m = QMenu(self)
        m.addAction("Speichern").triggered.connect(lambda: self.save(d))
        m.addAction("Speichern unter …").triggered.connect(lambda: self.save(d, as_new=True))
        m.addSeparator()
        a = m.addAction("Im Ordner zeigen")
        a.setEnabled(bool(d.path))
        a.triggered.connect(lambda: (self.tabs.setCurrentIndex(i), self.show_in_folder()))
        a = m.addAction("Pfad kopieren")
        a.setEnabled(bool(d.path))
        a.triggered.connect(lambda: (self.tabs.setCurrentIndex(i), self.copy_path()))
        m.addSeparator()
        m.addAction("Schließen").triggered.connect(lambda: self.close_tab(i))
        m.addAction("Alle anderen schließen").triggered.connect(lambda: self.close_others(i))
        m.exec(bar.mapToGlobal(pos))

    def eventFilter(self, obj, ev):
        # Mittlere Maustaste auf einem Reiter schließt ihn
        if obj is self.tabs.tabBar() and ev.type() == QEvent.Type.MouseButtonRelease and ev.button() == Qt.MouseButton.MiddleButton:
            i = obj.tabAt(ev.position().toPoint())
            if i >= 0:
                self.close_tab(i)
                return True
        return super().eventFilter(obj, ev)

    # ---- Ziehen & Ablegen aufs Fenster ------------------------------------------------------------------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.open_paths(paths)

    # ---- Anzeige aktualisieren ------------------------------------------------------------------------------------------
    def _refresh_tab(self, ed):
        i = self.tabs.indexOf(ed)
        if i < 0 or not hasattr(ed, "doc"):
            return
        d = ed.doc
        mark = "● " if d.modified else ""
        self.tabs.setTabText(i, mark + d.title)
        self.tabs.setTabToolTip(i, d.path or "Noch nicht gespeichert")
        self.tabs.setTabIcon(i, QIcon())
        if ed is self.editor():
            self._update_title()

    def _update_title(self):
        d = self.doc()
        if not d:
            self.setWindowTitle("Creative Notes")
            return
        mark = "● " if d.modified else ""
        ro = "  [schreibgeschützt]" if d.readonly else ""
        self.setWindowTitle(f"{mark}{d.title}{ro} – Creative Notes")

    def _tab_changed(self, _):
        self._update_status()
        self._update_title()
        if self.findbar.isVisible():
            for d in self.docs():
                if d.editor is not self.editor() and d.editor.search_hits:
                    d.editor.search_hits = []
                    d.editor.refresh_selections()
            self.findbar.live()

    def _text_changed(self):
        self._update_status()
        if self.findbar.isVisible():
            self.findbar.live()

    def _update_status(self):
        d = self.doc()
        if not d:
            return
        ed = d.editor
        c = ed.textCursor()
        line, col = c.blockNumber() + 1, c.positionInBlock() + 1
        sel = c.selectionEnd() - c.selectionStart()
        pos = f"Zeile {line}, Spalte {col}"
        if sel:
            lines = c.selectedText().count(" ") + 1
            pos += f"   ·   {sel} markiert" + (f" ({lines} Zeilen)" if lines > 1 else "")
        self.st_pos.setText(pos)
        self.st_len.setText(f"{ed.document().characterCount() - 1:,} Zeichen · {ed.blockCount():,} Zeilen".replace(",", "."))
        self.st_lang.setText(lexer.LANGUAGES.get(ed.lang, {}).get("name", "Text"))
        self.st_eol.setText(fileio.EOLS[d.eol][1].split(" (")[1].rstrip(")") if d.eol in fileio.EOLS else "LF")
        self.st_enc.setText(fileio.ENC[d.encoding][0])
        z = ed.zoom
        self.st_zoom.setText(f"{round(100 * (ed.BASE_SIZE + z) / ed.BASE_SIZE)} %")
        a = self.lang_actions.get(ed.lang)
        if a:
            a.setChecked(True)
        a = self.enc_actions.get(d.encoding)
        if a:
            a.setChecked(True)
        a = self.eol_actions.get(d.eol)
        if a:
            a.setChecked(True)

    # ---- Hilfe -----------------------------------------------------------------------------------------------------------
    def show_shortcuts(self):
        QMessageBox.information(self, "Tastenkürzel", "\n".join([
            "Strg+N  Neu            Strg+O  Öffnen         Strg+S  Speichern",
            "Strg+W  Reiter zu      Strg+Umschalt+T  Reiter wieder öffnen",
            "Strg+F  Suchen         Strg+H  Ersetzen       F3  Weitersuchen",
            "Strg+G  Gehe zu Zeile  Strg+B  Passende Klammer",
            "Strg+D  Zeile duplizieren        Strg+L  Zeile löschen",
            "Strg+Umschalt+↑/↓  Zeilen verschieben",
            "Strg+/  Kommentar an/aus         Tab / Umschalt+Tab  Ein-/Ausrücken",
            "Strg+U  klein   Strg+Umschalt+U  GROSS",
            "Strg+Mausrad / Strg++ / Strg+−  Zoom   Strg+0  Normale Größe",
            "Alt+Z  Zeilenumbruch   F7  Datum einfügen   F11  Vollbild",
        ]))

    def show_about(self):
        from . import __version__
        QMessageBox.about(self, "Über Creative Notes",
                          f"<b>Creative Notes {__version__}</b><br>Der Texteditor von Creative OS.<br><br>"
                          "Reiter, Syntaxfarben für viele Sprachen, Suchen und Ersetzen<br>"
                          "(auch mit regulären Ausdrücken) – und nichts geht verloren:<br>"
                          "ungespeicherte Texte sind beim nächsten Start wieder da.")
